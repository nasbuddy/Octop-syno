"""DSM session gate for HTTP and long-lived connections in the native package."""

from __future__ import annotations

import asyncio
import contextlib
import hmac
from typing import Any
from urllib.parse import parse_qs

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from octop.infra.auth.dsm import DsmAuthService, DsmIdentity, DsmRequest
from octop.infra.auth.tokens import InvalidToken, decode_token
from octop.infra.errors import ErrorCode, OctopError
from octop.infra.utils.locale import resolve_request_locale

_RECHECK_SECONDS = 5.0
_OAUTH_CALLBACK = "/api/connectors/oauth/callback"
_COOKIE_ONLY = frozenset(
    {
        "/api/auth/dsm/session",
        "/api/setup/status",
        "/api/docs",
        "/api/openapi.json",
        _OAUTH_CALLBACK,
    }
)
_PUBLIC = frozenset({"/api/health", "/api/i18n/tools", "/api/i18n/skills"})


def _context(scope: Scope) -> DsmRequest:
    headers = Headers(scope=scope)
    return DsmRequest(
        cookie=headers.get("cookie", ""),
        remote_addr=headers.get("x-octop-dsm-remote-addr", ""),
        server_addr=headers.get("x-octop-dsm-server-addr", ""),
        server_port=headers.get("x-octop-dsm-server-port", ""),
        host=headers.get("host", ""),
        scheme=headers.get("x-octop-dsm-scheme", ""),
        syno_token=headers.get("x-syno-token", ""),
    )


def _check_origin(scope: Scope, context: DsmRequest) -> None:
    # OAuth redirects use a one-time state; the handler also checks its DSM owner.
    if scope["path"] == _OAUTH_CALLBACK and scope.get("method") == "GET":
        return
    headers = Headers(scope=scope)
    origin = headers.get("origin")
    expected = f"{context.scheme}://{context.host}"
    if origin is not None and origin != expected:
        raise OctopError(ErrorCode.AUTH_FAILED, "DSM request origin mismatch")
    if headers.get("sec-fetch-site") == "cross-site":
        raise OctopError(ErrorCode.AUTH_FAILED, "cross-site DSM request")
    if (scope["type"] == "websocket" or scope.get("method") not in {"GET", "HEAD"}) and (
        origin != expected
    ):
        raise OctopError(ErrorCode.AUTH_FAILED, "DSM request origin is required")


def _token(scope: Scope) -> str | None:
    authorization = Headers(scope=scope).get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    query: dict[str, list[str]] = parse_qs(scope.get("query_string", b"").decode("latin-1"))
    key = "token" if scope["type"] == "websocket" else "access_token"
    values = query.get(key)
    return values[0] if values else None


class DsmAuthMiddleware:
    def __init__(self, app: ASGIApp, server: Any) -> None:
        self.app = app
        self.server = server
        self.service: DsmAuthService | None = None

    def _service(self) -> DsmAuthService:
        if self.server.services is None or self.server.user_manager is None:
            raise OctopError(ErrorCode.SETUP_REQUIRED, "DSM database is unavailable", status=503)
        if self.service is None:
            self.service = DsmAuthService(self.server.services, self.server.user_manager)
        return self.service

    async def _authenticate(self, scope: Scope, context: DsmRequest) -> DsmIdentity:
        _check_origin(scope, context)
        service = self._service()
        identity = await service.authenticate(context)
        binding = service.session_binding(context, identity)
        # A cookie for another DSM account must not execute a stale tab's request.
        raw = _token(scope)
        requires_token = scope["path"] not in _COOKIE_ONLY and not scope["path"].startswith(
            "/api/downloads/link/"
        )
        if requires_token:
            if not raw:
                raise OctopError(ErrorCode.AUTH_FAILED, "missing DSM-bound token")
            try:
                secret = service.services.secret_repo.get("jwt")
                if secret is None:
                    raise InvalidToken("jwt secret missing")
                payload = decode_token(secret, raw)
                claimed = payload.get("dsm_session")
                if not isinstance(claimed, str) or not hmac.compare_digest(claimed, binding):
                    raise InvalidToken("DSM session changed")
            except InvalidToken:
                raise OctopError(ErrorCode.AUTH_FAILED, "DSM session changed") from None
        user = await service.resolve_user(identity)
        if requires_token and payload["sub"] != user.id:
            raise OctopError(ErrorCode.AUTH_FAILED, "DSM identity changed")
        state = scope.setdefault("state", {})
        state["octop_user"] = user
        state["dsm_session"] = binding
        return identity

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        path = scope["path"]
        # Internal MCP has its own per-instance credential, used by background agents.
        if scope["type"] == "http" and (
            not path.startswith("/api/") or path in _PUBLIC or path.startswith("/api/internal/mcp/")
        ):
            await self.app(scope, receive, send)
            return
        context = _context(scope)
        try:
            identity = await self._authenticate(scope, context)
        except OctopError as exc:
            await self._deny(scope, receive, send, exc)
            return

        started = False
        closed = False

        async def guarded_send(message: Message) -> None:
            nonlocal started, closed
            if closed:
                return
            if message["type"] in {"http.response.start", "websocket.accept"}:
                started = True
            if message["type"] == "http.response.start":
                # A native DSM session must not be served from a browser/proxy cache.
                headers = [
                    (k, v) for k, v in message.get("headers", []) if k.lower() != b"cache-control"
                ]
                headers.append((b"cache-control", b"no-store"))
                message = {**message, "headers": headers}
            if message["type"] == "websocket.close":
                closed = True
            await send(message)

        async def validate_connection() -> None:
            current = await self._authenticate(scope, context)
            if current != identity:
                raise OctopError(ErrorCode.AUTH_FAILED, "DSM identity or privileges changed")

        async def guarded_receive() -> Message:
            message = await receive()
            if message["type"] == "websocket.receive":
                await validate_connection()
            return message

        async def watch() -> None:
            while True:
                await asyncio.sleep(_RECHECK_SECONDS)
                await validate_connection()

        application = asyncio.ensure_future(self.app(scope, guarded_receive, guarded_send))
        watcher = asyncio.create_task(watch())
        try:
            done, _ = await asyncio.wait(
                (application, watcher), return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                await task
        except OctopError as exc:
            if not closed:
                closed = True
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 4001})
                elif started:
                    await send({"type": "http.response.body", "body": b"", "more_body": False})
                else:
                    await self._deny(scope, receive, send, exc)
        finally:
            for task in (application, watcher):
                task.cancel()
            for task in (application, watcher):
                with contextlib.suppress(asyncio.CancelledError, OctopError):
                    await task

    @staticmethod
    async def _deny(scope: Scope, receive: Receive, send: Send, exc: OctopError) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 4001})
            return
        locale = resolve_request_locale(Request(scope))
        response = JSONResponse(
            exc.to_envelope(locale=locale),
            status_code=exc.status,
            headers={"Cache-Control": "no-store"},
        )
        await response(scope, receive, send)
