"""Bundled NAS MCP, scoped to each user's verified native DSM session."""

from __future__ import annotations

import asyncio
import contextvars
import hmac
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

import httpx
from mcp.server.fastmcp.exceptions import ToolError

from octop._vendor.nas_local_mcp import nas_mcp as runtime
from octop._vendor.nas_local_mcp import notes as note_operations
from octop.i18n import tr
from octop.infra.agents.experts.catalog import (
    ExpertCatalog,
    build_create_spec_from_expert,
    resolve_expert_agent_name,
)
from octop.infra.agents.manager import AgentManager
from octop.infra.auth import dsm as dsm_auth
from octop.infra.auth.dsm import DsmIdentity, DsmRequest
from octop.infra.connectors.builder import mcp_server_name
from octop.infra.connectors.service import ConnectorService
from octop.infra.db.services import SharedServices
from octop.infra.errors import ErrorCode, OctopError
from octop.infra.users.identity import User
from octop.infra.utils.ulid import new_ulid

KIND = "synology-nas"


@dataclass(frozen=True, repr=False)
class _Session:
    identity: DsmIdentity
    request: DsmRequest


class _NativeTransport(httpx.AsyncBaseTransport):
    def __init__(self, request: DsmRequest) -> None:
        self.request = request
        # This connection never leaves the NAS. Its public certificate may not
        # contain 127.0.0.1; use the same loopback TLS rule as internal MCP.
        self.transport = httpx.AsyncHTTPTransport(verify=False)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        context = self.request
        headers = httpx.Headers(request.headers)
        headers.update(
            {
                "Host": context.host,
                "Cookie": f"id={context.session_id()}",
                "X-SYNO-TOKEN": context.syno_token,
                "Origin": f"{context.scheme}://{context.host}",
                "Referer": f"{context.scheme}://{context.host}/",
            }
        )
        forwarded = httpx.Request(
            request.method,
            request.url.copy_with(host="127.0.0.1", port=int(context.server_port)),
            headers=headers,
            stream=request.stream,
            extensions=request.extensions,
        )
        return await self.transport.handle_async_request(forwarded)

    async def aclose(self) -> None:
        await self.transport.aclose()


class NativeSynologyService:
    def __init__(
        self,
        services: SharedServices,
        registry: AgentManager,
        catalog: ExpertCatalog,
    ) -> None:
        self.services = services
        self.registry = registry
        self.catalog = catalog
        self._sessions: OrderedDict[int, _Session] = OrderedDict()
        self._provision_lock = asyncio.Lock()

    def remember(self, user: User, identity: DsmIdentity, context: DsmRequest) -> None:
        self._sessions[user.id] = _Session(identity, context)
        self._sessions.move_to_end(user.id)
        if len(self._sessions) > 256:
            self._sessions.popitem(last=False)

    def forget(self, context: DsmRequest) -> None:
        for user_id, session in list(self._sessions.items()):
            if session.request.cookie == context.cookie:
                self._sessions.pop(user_id, None)

    async def _session(self, user_id: int) -> _Session:
        session = self._sessions.get(user_id)
        row = self.services.user_repo.get(user_id)
        if session is None or row is None or row.disabled:
            raise OctopError(
                ErrorCode.AUTH_FAILED,
                tr("synology.session_unavailable", row.locale if row is not None else "en"),
            )
        try:
            identity = await asyncio.get_running_loop().run_in_executor(
                None, dsm_auth.verify_session, session.request
            )
            if not hmac.compare_digest(
                identity.subject.encode(), session.identity.subject.encode()
            ):
                raise OctopError(ErrorCode.AUTH_FAILED, tr("synology.session_unavailable"))
        except OctopError:
            if self._sessions.get(user_id) is session:
                self._sessions.pop(user_id, None)
            raise
        return session

    async def ensure_defaults(self, user: User) -> None:
        """Create one private connector and expert once, retaining later user edits."""
        key = f"synology.defaults.{user.id}"
        async with self._provision_lock:
            if self.services.settings_repo.get(key) == "1":
                return
            await self._session(user.id)
            repo = self.services.repos.connector_repo
            instance = repo.get_by_user_kind(user.id, KIND)
            if instance is None:
                instance_id = new_ulid()
                repo.create(
                    instance_id=instance_id,
                    user_id=user.id,
                    kind=KIND,
                    display_name=tr("synology.connector_name", user.locale),
                    mcp_server_name=mcp_server_name(KIND, instance_id),
                    shared=False,
                )
                connector = ConnectorService(
                    repo=repo,
                    secret_repo=self.services.secret_repo,
                    settings_repo=self.services.settings_repo,
                    config=self.services.config,
                )
                # execute=false remains the default for every write-capable tool.
                connector.encrypt_and_store(instance_id=instance_id, payload={"allow_writes": True})
                instance = repo.get(instance_id)
            assert instance is not None
            owned = [row for row in self.registry.list_rows() if row.user_id == user.id]
            if not any(row.template_name == KIND for row in owned):
                expert = self.catalog.get(KIND)
                if expert is None:
                    raise OctopError(ErrorCode.NOT_FOUND, "synology-nas template missing")
                base_name = resolve_expert_agent_name(expert, KIND, locale=user.locale)
                names = {row.name for row in owned}
                name = base_name
                suffix = 2
                while name in names:
                    name = f"{base_name} ({suffix})"
                    suffix += 1
                model = next((row.default_model for row in owned if row.default_model), None)
                spec = build_create_spec_from_expert(
                    expert_id=KIND,
                    expert=expert,
                    user_id=user.id,
                    name=name,
                    locale=user.locale,
                    default_model=model,
                    mcp_servers=[instance.mcp_server_name],
                )
                await self.registry.create(spec, defer_bootstrap=True)
            self.services.settings_repo.set(key, "1")

    async def handle(
        self, user_id: int, credentials: dict[str, Any], body: dict[str, Any]
    ) -> dict[str, Any]:
        method = body.get("method")
        request_id = body.get("id")
        row = self.services.user_repo.get(user_id)
        locale = row.locale if row is not None else "en"
        result: dict[str, Any]
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                "serverInfo": {"name": "octop-synology-nas", "version": "0.1.0"},
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            tools = await runtime.mcp.list_tools()
            result = {
                "tools": [
                    {
                        **tool.model_dump(mode="json", by_alias=True, exclude_none=True),
                        "description": tr(f"synology.tools.{tool.name}", locale),
                    }
                    for tool in tools
                ]
            }
        elif method == "resources/list":
            resources = await runtime.mcp.list_resources()
            result = {"resources": [resource.model_dump(mode="json") for resource in resources]}
        elif method == "resources/read":
            if body.get("params") != {"uri": "nas://capabilities"}:
                return self._error(request_id, -32602, "Unknown resource")
            result = {
                "contents": [
                    {
                        "uri": "nas://capabilities",
                        "mimeType": "application/json",
                        "text": runtime.capabilities(),
                    }
                ]
            }
        elif method == "prompts/list":
            prompts = await runtime.mcp.list_prompts()
            result = {"prompts": [prompt.model_dump(mode="json") for prompt in prompts]}
        elif method == "prompts/get":
            params = body.get("params")
            if not isinstance(params, dict) or params.get("name") != "nas_health_check":
                return self._error(request_id, -32602, "Unknown prompt")
            result = {
                "messages": [
                    {
                        "role": "user",
                        "content": {"type": "text", "text": runtime.nas_health_check()},
                    }
                ]
            }
        elif method == "tools/call":
            params = body.get("params")
            if not isinstance(params, dict) or not isinstance(params.get("arguments", {}), dict):
                return self._error(request_id, -32602, "Invalid tool arguments")
            name = str(params.get("name") or "")
            arguments = params.get("arguments") or {}
            try:
                session = await self._session(user_id)
                context = session.request
                config = runtime.Config(
                    url=f"{context.scheme}://{context.host}",
                    username=session.identity.username,
                    sid=context.session_id(),
                    synotoken=context.syno_token,
                    session_source="client",
                    allow_http=context.scheme == "http",
                    allow_writes=credentials.get("allow_writes") is True,
                    transfer_dir=str(
                        self.services.paths.root / "synology" / str(user_id) / "transfers"
                    ),
                )
                config._credentials = runtime.Credentials(
                    username=config.username, sid=config.sid, synotoken=config.synotoken
                )
                config._credential_source = "dsm"
                config_token = runtime.EMBEDDED_CONFIG.set(config)
                transport_token = runtime.EMBEDDED_TRANSPORT.set(lambda: _NativeTransport(context))
                locale_token = note_operations.LOCALE.set(locale)
                try:
                    call_context = contextvars.copy_context()
                    response: Any = await asyncio.get_running_loop().run_in_executor(
                        None,
                        lambda: call_context.run(
                            asyncio.run, runtime.mcp.call_tool(name, arguments)
                        ),
                    )
                finally:
                    runtime.EMBEDDED_TRANSPORT.reset(transport_token)
                    runtime.EMBEDDED_CONFIG.reset(config_token)
                    note_operations.LOCALE.reset(locale_token)
                if isinstance(response, tuple):
                    content, structured = response
                    result = {"content": [item.model_dump(exclude_none=True) for item in content]}
                    if structured is not None:
                        result["structuredContent"] = structured
                else:
                    result = {"content": [item.model_dump(exclude_none=True) for item in response]}
                result["isError"] = False
            except OctopError:
                result = self._tool_error(tr("synology.session_unavailable", locale))
            except (ValueError, ToolError):
                # The upstream runtime sanitizes DSM errors; do not propagate a
                # framework traceback, request headers or a credential-bearing URL.
                result = self._tool_error(tr("synology.operation_failed", locale))
        else:
            return self._error(request_id, -32601, "Method not found")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    async def probe(self, user_id: int, credentials: dict[str, Any]) -> dict[str, Any]:
        response = await self.handle(
            user_id,
            credentials,
            {"id": 1, "method": "tools/call", "params": {"name": "nas_status"}},
        )
        result = response["result"]
        if result.get("isError"):
            return {"ok": False, "error": result["content"][0]["text"]}
        status = result.get("structuredContent")
        if not isinstance(status, dict):
            import json

            status = json.loads(result["content"][0]["text"])
        if status.get("authenticated") is not True:
            return {"ok": False, "error": tr("synology.session_unavailable")}
        tools = await runtime.mcp.list_tools()
        return {
            "ok": True,
            "tool_count": len(tools),
            "tools": [{"name": tool.name, "description": tool.description or ""} for tool in tools],
        }

    @staticmethod
    def _tool_error(message: str) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": message}], "isError": True}

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
