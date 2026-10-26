"""Validate the DSM CGI trust boundary without requiring a NAS."""

from __future__ import annotations

import os
import subprocess
from dataclasses import replace
from types import SimpleNamespace

import pytest

from octop.infra.auth.dsm import AUTHENTICATE_CGI, DsmRequest, verify_session
from octop.infra.errors import OctopError

posix_only = pytest.mark.skipif(os.name != "posix", reason="DSM uses POSIX accounts")
CONTEXT = DsmRequest(
    cookie="id=synthetic-session; other=value",
    remote_addr="192.0.2.10",
    server_addr="192.0.2.20",
    server_port="5001",
    host="nas.invalid:5001",
    scheme="https",
    syno_token="synthetic-csrf",
)


@posix_only
@pytest.mark.parametrize("administrator", [True, False])
def test_cgi_identity_and_system_group_are_authoritative(monkeypatch, administrator):
    import grp
    import pwd

    def run(command, **kwargs):
        assert command == [AUTHENTICATE_CGI]
        assert kwargs["timeout"] == 5 and kwargs["check"] is True
        assert kwargs["env"]["HTTP_COOKIE"] == CONTEXT.cookie
        assert kwargs["env"]["REMOTE_ADDR"] == CONTEXT.remote_addr
        assert kwargs["env"]["SERVER_ADDR"] == CONTEXT.server_addr
        assert kwargs["env"]["HTTPS"] == "on"
        assert kwargs["env"]["HTTP_X_SYNO_TOKEN"] == CONTEXT.syno_token
        assert kwargs["stderr"] == subprocess.DEVNULL
        return SimpleNamespace(stdout=b"alice\n")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(pwd, "getpwnam", lambda name: SimpleNamespace(pw_uid=1026, pw_gid=100))
    monkeypatch.setattr(grp, "getgrnam", lambda name: SimpleNamespace(gr_gid=101))
    monkeypatch.setattr(
        os, "getgrouplist", lambda name, gid: [100, 101] if administrator else [100]
    )
    identity = verify_session(CONTEXT)
    assert identity.username == "alice"
    assert identity.subject == "1026:alice"
    assert identity.administrator is administrator


@posix_only
@pytest.mark.parametrize("output", [b"", b"Content-Type: text/plain\n\nalice", b"\xff"])
def test_invalid_cgi_output_fails_closed(monkeypatch, output):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout=output))
    with pytest.raises(OctopError):
        verify_session(CONTEXT)


@posix_only
@pytest.mark.parametrize(
    "error",
    [PermissionError("denied"), subprocess.TimeoutExpired(AUTHENTICATE_CGI, 5)],
)
def test_cgi_failure_fails_closed_without_credential_details(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(OctopError) as caught:
        verify_session(CONTEXT)
    assert "synthetic-session" not in str(caught.value)


@pytest.mark.parametrize("cookie", ["", "id=", "not-id=value"])
def test_missing_session_rejected(cookie):
    with pytest.raises(OctopError):
        replace(CONTEXT, cookie=cookie).session_id()


async def test_verified_csrf_token_is_memory_only_and_scoped_to_session_and_ip(monkeypatch):
    from octop.infra.auth import dsm

    valid = True

    def verify(context):
        if not valid or context.syno_token != CONTEXT.syno_token:
            raise OctopError(dsm.ErrorCode.AUTH_FAILED, "invalid")
        return dsm.DsmIdentity("alice", 1026, True)

    monkeypatch.setattr(dsm, "verify_session", verify)
    service = dsm.DsmAuthService(None, None)
    await service.authenticate(CONTEXT)
    without_header = replace(CONTEXT, syno_token="")
    assert (await service.authenticate(without_header)).username == "alice"
    for other in (
        replace(without_header, remote_addr="192.0.2.11"),
        replace(without_header, cookie="id=other-session"),
    ):
        with pytest.raises(OctopError):
            await service.authenticate(other)
    assert len(service._syno_tokens) == 1
    assert all(isinstance(key, bytes) and len(key) == 32 for key in service._syno_tokens)
    valid = False
    with pytest.raises(OctopError):
        await service.authenticate(without_header)
    assert not service._syno_tokens


async def test_verified_csrf_token_cache_is_bounded(monkeypatch):
    from octop.infra.auth import dsm

    monkeypatch.setattr(dsm, "verify_session", lambda context: dsm.DsmIdentity("alice", 1026, True))
    service = dsm.DsmAuthService(None, None)
    for number in range(257):
        await service.authenticate(replace(CONTEXT, cookie=f"id=session-{number}"))
    assert len(service._syno_tokens) == 256
