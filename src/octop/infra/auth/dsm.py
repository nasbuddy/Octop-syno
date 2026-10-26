"""Validate the browser's existing DSM session; never accept a supplied username."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import os
import subprocess
from collections import OrderedDict
from dataclasses import dataclass, replace
from http.cookies import CookieError, SimpleCookie

from octop.infra.db.services import SharedServices
from octop.infra.errors import ErrorCode, OctopError
from octop.infra.users.identity import Role, User
from octop.infra.users.manager import UserManager

AUTHENTICATE_CGI = "/usr/syno/synoman/webman/modules/authenticate.cgi"
DSM_KIND = "dsm"


@dataclass(frozen=True)
class DsmRequest:
    cookie: str
    remote_addr: str
    server_addr: str
    server_port: str
    host: str
    scheme: str
    syno_token: str = ""

    def session_id(self) -> str:
        cookies = SimpleCookie()
        try:
            cookies.load(self.cookie)
        except CookieError:
            raise OctopError(ErrorCode.AUTH_FAILED, "invalid DSM cookie") from None
        session = cookies.get("id")
        if session is None or not session.value:
            raise OctopError(ErrorCode.AUTH_FAILED, "missing DSM session")
        return session.value


@dataclass(frozen=True)
class DsmIdentity:
    username: str
    uid: int
    administrator: bool

    @property
    def subject(self) -> str:
        # Including the name avoids assigning a deleted user's data to a reused UID.
        return f"{self.uid}:{self.username}"


def verify_session(request: DsmRequest) -> DsmIdentity:
    """Blocking DSM helper call; callers must use an executor."""
    request.session_id()
    if os.name != "posix":
        raise OctopError(ErrorCode.AUTH_FAILED, "DSM authentication requires DSM")
    import grp
    import pwd

    try:
        ipaddress.ip_address(request.remote_addr)
        ipaddress.ip_address(request.server_addr)
        if request.scheme not in {"http", "https"} or not 1 <= int(request.server_port) <= 65535:
            raise ValueError("invalid DSM request context")
        env = {
            "PATH": "/usr/syno/bin:/usr/syno/sbin:/usr/bin:/bin",
            "REQUEST_METHOD": "GET",
            "GATEWAY_INTERFACE": "CGI/1.1",
            "SERVER_PROTOCOL": "HTTP/1.1",
            "HTTP_COOKIE": request.cookie,
            "REMOTE_ADDR": request.remote_addr,
            "SERVER_ADDR": request.server_addr,
            "SERVER_PORT": request.server_port,
            "HTTP_HOST": request.host,
            "HTTPS": "on" if request.scheme == "https" else "off",
            "HTTP_X_SYNO_TOKEN": request.syno_token,
        }
        completed = subprocess.run(
            [AUTHENTICATE_CGI],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=True,
        )
        name = completed.stdout.decode("utf-8").strip()
        if not name or len(name) > 256 or any(ord(c) < 32 for c in name):
            raise ValueError("invalid DSM identity")
        account = pwd.getpwnam(name)
        admin_group = grp.getgrnam("administrators")
        administrator = admin_group.gr_gid in os.getgrouplist(name, account.pw_gid)
        return DsmIdentity(name, account.pw_uid, administrator)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        # Never include CGI output, environment, cookies or tokens in error responses/logs.
        raise OctopError(ErrorCode.AUTH_FAILED, "DSM session is unavailable") from None


class DsmAuthService:
    def __init__(self, services: SharedServices, users: UserManager) -> None:
        self.services = services
        self.users = users
        self._lock = asyncio.Lock()
        self._syno_tokens: OrderedDict[bytes, str] = OrderedDict()

    async def authenticate(self, request: DsmRequest) -> DsmIdentity:
        key = hashlib.sha256(f"{request.session_id()}\0{request.remote_addr}".encode()).digest()
        context = replace(request, syno_token=request.syno_token or self._syno_tokens.get(key, ""))
        try:
            identity = await asyncio.get_running_loop().run_in_executor(
                None, verify_session, context
            )
        except OctopError:
            self._syno_tokens.pop(key, None)
            raise
        # WS/download/OAuth requests cannot set headers; keep only verified tokens in memory.
        # This never caches authentication: every request still calls DSM's helper.
        if context.syno_token:
            self._syno_tokens[key] = context.syno_token
            self._syno_tokens.move_to_end(key)
            if len(self._syno_tokens) > 256:
                self._syno_tokens.popitem(last=False)
        return identity

    def session_binding(self, request: DsmRequest, identity: DsmIdentity) -> str:
        secret = self.services.secret_repo.get("jwt")
        if secret is None:
            raise OctopError(ErrorCode.INTERNAL_ERROR, "jwt secret missing")
        value = f"{identity.subject}\0{request.session_id()}\0{request.remote_addr}"
        return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()

    async def resolve_user(self, identity: DsmIdentity) -> User:
        async with self._lock:
            if self.users.count() == 0 and not identity.administrator:
                raise OctopError(ErrorCode.FORBIDDEN, "a DSM administrator must initialize Octop")
            provider = self.services.sso_repo.get_by_kind(DSM_KIND)
            if provider is None:
                provider = self.services.sso_repo.upsert_by_kind(
                    DSM_KIND,
                    enabled=True,
                    display_name="DSM",
                    issuer="",
                    client_id="",
                    client_secret_enc=None,
                    scopes="",
                    dashboard_origin=None,
                )
            if not provider.enabled:
                raise OctopError(ErrorCode.AUTH_FAILED, "DSM login is disabled")
            user = await self.users.resolve_or_create_sso_user(
                provider_id=provider.id,
                subject=identity.subject,
                claims={"preferred_username": identity.username, "name": identity.username},
            )
            if identity.administrator and not user.is_admin:
                await self.users.set_role(user.username, Role.ADMIN)
            elif not identity.administrator and user.is_admin:
                await self.users.set_role(user.username, Role.USER)
            return user
