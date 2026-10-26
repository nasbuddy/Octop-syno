"""Native DSM sessions must remain authoritative after the initial login."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import WebSocket
from starlette.responses import StreamingResponse
from starlette.websockets import WebSocketDisconnect

from octop.infra.auth import dsm
from octop.infra.auth.tokens import decode_token, sign_token
from octop.infra.errors import ErrorCode, OctopError
from tests.support.app import octop_client, write_octop_config
from tests.support.http import ASGIWebSocketSession

_HEADERS = {
    "Cookie": "id=alice-session",
    "Origin": "http://testserver",
    "X-Octop-DSM-Remote-Addr": "192.0.2.10",
    "X-Octop-DSM-Server-Addr": "192.0.2.20",
    "X-Octop-DSM-Server-Port": "5000",
    "X-Octop-DSM-Scheme": "http",
}


@pytest.fixture
async def dsm_env(tmp_octop_home, monkeypatch) -> AsyncIterator[Any]:
    monkeypatch.setenv("OCTOP_DSM_AUTH", "1")
    write_octop_config(tmp_octop_home, enable_api_docs=True)
    state = {"valid": True, "admin": True}

    def verify(context: dsm.DsmRequest) -> dsm.DsmIdentity:
        session_id = context.session_id()
        if not state["valid"]:
            raise OctopError(ErrorCode.AUTH_FAILED, "expired")
        if session_id == "alice-session":
            if context.syno_token != "synthetic-csrf":
                raise OctopError(ErrorCode.AUTH_FAILED, "missing DSM CSRF token")
            return dsm.DsmIdentity("alice", 1026, state["admin"])
        if session_id == "bob-session":
            return dsm.DsmIdentity("bob", 1027, False)
        raise OctopError(ErrorCode.AUTH_FAILED, "invalid")

    monkeypatch.setattr(dsm, "verify_session", verify)
    async with octop_client(tmp_octop_home, bind_database=False) as (client, server):
        assert server.database_bound
        assert not (tmp_octop_home / "octop-login.txt").exists()
        response = await client.get(
            "/api/auth/dsm/session", headers={**_HEADERS, "X-Syno-Token": "synthetic-csrf"}
        )
        assert response.status_code == 200, response.text
        auth = {**_HEADERS, "Authorization": f"Bearer {response.json()['access_token']}"}
        yield client, server, auth, state


async def test_dsm_bootstrap_reuses_identity_and_maps_administrators(dsm_env):
    client, server, auth, state = dsm_env
    me = (await client.get("/api/auth/me", headers=auth)).json()
    assert me["username"] == "alice"
    assert me["role"] == "admin"
    repeated = await client.get("/api/auth/dsm/session", headers=_HEADERS)
    assert repeated.json()["user_id"] == me["id"]
    assert server.user_manager.count() == 1
    state["admin"] = False
    downgraded = await client.get("/api/auth/me", headers=auth)
    assert downgraded.json()["role"] == "user"
    denied = await client.get("/api/users", headers=auth)
    assert denied.status_code == 403


async def test_dsm_logout_invalidates_existing_token(dsm_env):
    client, _, auth, state = dsm_env
    assert (await client.get("/api/auth/me", headers=auth)).status_code == 200
    state["valid"] = False
    denied = await client.get("/api/auth/me", headers=auth)
    assert denied.status_code == 401
    assert denied.headers["cache-control"] == "no-store"


async def test_dsm_account_switch_rejects_old_tab_before_write(dsm_env):
    client, _, auth, _ = dsm_env
    switched = {**auth, "Cookie": "id=bob-session"}
    denied = await client.patch(
        "/api/auth/me", headers=switched, json={"display_name": "stale tab write"}
    )
    assert denied.status_code == 401
    boot = await client.get("/api/auth/dsm/session", headers=switched)
    bob_auth = {**switched, "Authorization": f"Bearer {boot.json()['access_token']}"}
    me = (await client.get("/api/auth/me", headers=bob_auth)).json()
    assert me["username"] == "bob"
    assert me["role"] == "user"
    assert me["display_name"] != "stale tab write"


async def test_dsm_rejects_regular_jwt_and_forged_identity_headers(dsm_env):
    client, server, auth, _ = dsm_env
    me = (await client.get("/api/auth/me", headers=auth)).json()
    token = sign_token(
        server.services.secret_repo.get("jwt"),
        sub=me["id"],
        uname="alice",
        role="admin",
    )
    forged = {**auth, "Authorization": f"Bearer {token}", "X-Remote-User": "alice"}
    assert (await client.get("/api/auth/me", headers=forged)).status_code == 401
    forged.pop("Cookie")
    assert (await client.get("/api/auth/dsm/session", headers=forged)).status_code == 401


@pytest.mark.parametrize("origin", [None, "http://attacker.invalid", "null"])
async def test_dsm_csrf_cannot_change_profile(dsm_env, origin):
    client, _, auth, _ = dsm_env
    headers = {**auth}
    headers.pop("Origin")
    if origin is not None:
        headers["Origin"] = origin
    denied = await client.patch(
        "/api/auth/me", headers=headers, json={"display_name": "cross-site"}
    )
    assert denied.status_code == 401


async def test_dsm_cross_origin_cannot_read_bootstrap_token(dsm_env):
    client, _, _, _ = dsm_env
    response = await client.get(
        "/api/auth/dsm/session",
        headers={**_HEADERS, "Origin": "https://attacker.invalid"},
    )
    assert response.status_code == 401


async def test_dsm_renewed_token_keeps_session_binding(dsm_env):
    client, server, auth, _ = dsm_env
    secret = server.services.secret_repo.get("jwt")
    payload = decode_token(secret, auth["Authorization"].removeprefix("Bearer "))
    short = sign_token(
        secret,
        sub=payload["sub"],
        uname=payload["uname"],
        role=payload["role"],
        ttl_seconds=30,
        dsm_session=payload["dsm_session"],
    )
    response = await client.get(
        "/api/auth/me", headers={**auth, "Authorization": f"Bearer {short}"}
    )
    assert response.status_code == 200
    renewed = response.headers["x-octop-access-token"]
    assert decode_token(secret, renewed)["dsm_session"] == payload["dsm_session"]


@pytest.mark.parametrize("change", ["logout", "demotion"])
async def test_dsm_invalidates_idle_websocket(dsm_env, monkeypatch, change):
    client, _, auth, state = dsm_env
    monkeypatch.setattr("octop.api.middleware.dsm_auth._RECHECK_SECONDS", 0.02)
    app = client._octop_app

    @app.websocket("/api/dsm-test")
    async def echo(websocket: WebSocket):
        await websocket.accept()
        while True:
            value = await websocket.receive_text()
            await websocket.send_json({"echo": value})

    async def with_headers(scope, receive, send):
        scope["headers"] += [(k.lower().encode(), v.encode()) for k, v in _HEADERS.items()]
        await app(scope, receive, send)

    token = auth["Authorization"].removeprefix("Bearer ")
    ws = ASGIWebSocketSession(with_headers, f"/api/dsm-test?token={token}")
    try:
        await ws.connect()
        await ws.send_json({"hello": "world"})
        assert (await ws.receive_json())["echo"]
        state["valid" if change == "logout" else "admin"] = False
        with pytest.raises(WebSocketDisconnect) as error:
            await ws.receive_json(timeout=2)
        assert error.value.code == 4001
    finally:
        await ws.close()


async def test_dsm_never_merges_local_account_by_name(dsm_env):
    client, server, _, _ = dsm_env
    local = await server.user_manager.create(username="bob", password="TestPass12", role="admin")
    response = await client.get(
        "/api/auth/dsm/session", headers={**_HEADERS, "Cookie": "id=bob-session"}
    )
    assert response.status_code == 200
    assert response.json()["user_id"] != local.id
    assert server.user_manager.get("bob").is_admin
    auth = {
        **_HEADERS,
        "Cookie": "id=bob-session",
        "Authorization": f"Bearer {response.json()['access_token']}",
    }
    me = (await client.get("/api/auth/me", headers=auth)).json()
    assert me["username"] == "bob_2"
    assert me["role"] == "user"


async def test_dsm_first_user_must_be_nas_administrator(tmp_octop_home, monkeypatch):
    monkeypatch.setenv("OCTOP_DSM_AUTH", "1")
    monkeypatch.setattr(dsm, "verify_session", lambda _: dsm.DsmIdentity("bob", 1027, False))
    async with octop_client(tmp_octop_home) as (client, server):
        response = await client.get("/api/auth/dsm/session", headers=_HEADERS)
        assert response.status_code == 403
        assert server.user_manager.count() == 0


async def test_dsm_logout_closes_an_idle_http_stream(dsm_env, monkeypatch):
    client, _, auth, state = dsm_env
    monkeypatch.setattr("octop.api.middleware.dsm_auth._RECHECK_SECONDS", 0.02)
    started = asyncio.Event()
    app = client._octop_app

    @app.get("/api/dsm-stream")
    async def stream():
        async def events():
            yield b"data: first\n\n"
            started.set()
            await asyncio.Future()

        return StreamingResponse(events(), media_type="text/event-stream")

    app.router.routes.insert(0, app.router.routes.pop())  # Before the SPA catch-all.
    task = asyncio.create_task(client.get("/api/dsm-stream", headers=auth))
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        state["valid"] = False
        response = await asyncio.wait_for(task, timeout=2)
        assert response.content == b"data: first\n\n"
    finally:
        task.cancel()


async def test_dsm_docs_use_same_origin_prefix_and_typed_session_schema(dsm_env):
    client, _, _, _ = dsm_env
    docs = await client.get("/api/docs", headers=_HEADERS)
    assert docs.status_code == 200
    assert "/octop/api/openapi.json" in docs.text
    schema = await client.get("/api/openapi.json", headers=_HEADERS)
    assert schema.status_code == 200
    assert {"url": "/octop"} in schema.json()["servers"]
    operation = schema.json()["paths"]["/api/auth/dsm/session"]["get"]
    assert operation["summary"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/DsmSessionResponse"
    }


async def test_dsm_download_requires_live_session_and_same_owner(dsm_env):
    client, _, auth, state = dsm_env
    response = await client.post(
        "/api/downloads/link",
        headers=auth,
        files={"file": ("private.txt", b"private content", "text/plain")},
    )
    assert response.status_code == 200
    url = response.json()["url"]
    assert (await client.get(url, headers=_HEADERS)).content == b"private content"
    switched = {**_HEADERS, "Cookie": "id=bob-session"}
    assert (await client.get(url, headers=switched)).status_code == 404
    state["valid"] = False
    assert (await client.get(url, headers=_HEADERS)).status_code == 401


@pytest.mark.parametrize("switch_account", [False, True])
async def test_dsm_oauth_callback_checks_state_owner_and_preserves_base(
    dsm_env, monkeypatch, switch_account
):
    client, server, auth, _ = dsm_env
    user_id = (await client.get("/api/auth/me", headers=auth)).json()["id"]
    server.services.repos.connector_repo.create_oauth_state(
        state_id="test-state",
        state="synthetic-state",
        user_id=user_id,
        kind="notion",
        code_verifier="verifier",
        redirect_after="/connectors",
    )
    exchange = AsyncMock(return_value={"access_token": "synthetic-provider-token"})
    monkeypatch.setattr("octop.api.routers.connectors.exchange_oauth_code", exchange)
    headers = {**_HEADERS, "Sec-Fetch-Site": "cross-site"}
    headers.pop("Origin")
    if switch_account:
        headers["Cookie"] = "id=bob-session"
    response = await client.get(
        "/api/connectors/oauth/callback",
        headers=headers,
        params={"state": "synthetic-state", "code": "synthetic-code"},
    )
    if switch_account:
        assert response.status_code == 400
        exchange.assert_not_awaited()
    else:
        assert response.status_code == 200
        assert "/octop/connectors?oauth_state=test-state" in response.text
        assert exchange.await_args.kwargs["redirect_uri"] == (
            "http://testserver/octop/api/connectors/oauth/callback"
        )


async def test_dsm_internal_mcp_keeps_its_own_credential(dsm_env, monkeypatch):
    from octop.api.routers.internal_mcp import _service
    from octop.infra.connectors import qcc

    client, server, auth, _ = dsm_env
    created = await client.post(
        "/api/connector-instances",
        headers=auth,
        json={"kind": "qcc", "display_name": "Test", "credentials": {"api_key": "synthetic"}},
    )
    assert created.status_code == 201
    instance_id = created.json()["instance_id"]
    token = _service(server).decrypt(instance_id)["internal_token"]
    request = AsyncMock(return_value={"tools": []})
    monkeypatch.setattr(qcc, "request_resource", request)
    path = f"/api/internal/mcp/qcc/{instance_id}"
    body = {"id": 1, "method": "tools/list"}
    assert (await client.post(path, params={"token": "wrong"}, json=body)).status_code == 401
    request.assert_not_awaited()
    assert (await client.post(path, params={"token": token}, json=body)).status_code == 200
    request.assert_awaited()
