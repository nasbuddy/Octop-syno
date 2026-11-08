from __future__ import annotations

import httpx

from octop.infra.auth.dsm import DsmRequest
from octop.infra.connectors.builder import validate_create_credentials
from octop.infra.connectors.synology import _NativeTransport


async def test_native_transport_never_sends_dsm_cookie_to_a_remote_host():
    context = DsmRequest(
        cookie="other_cookie=private; id=synthetic-session",
        remote_addr="192.0.2.10",
        server_addr="192.0.2.20",
        server_port="5000",
        host="nas.example:5000",
        scheme="http",
        syno_token="synthetic-csrf",
    )
    observed = []

    def handler(request):
        observed.append(request)
        return httpx.Response(200, json={"success": True})

    transport = _NativeTransport(context)
    await transport.transport.aclose()
    transport.transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await client.post("http://remote.example/webapi/entry.cgi", content=b"api=SYNO.API.Info")
    request = observed[0]
    assert request.url.host == "127.0.0.1"
    assert request.url.port == 5000
    assert request.headers["host"] == "nas.example:5000"
    assert request.headers["cookie"] == "id=synthetic-session"
    assert request.headers["x-syno-token"] == "synthetic-csrf"
    assert "x-real-ip" not in request.headers
    assert "x-forwarded-for" not in request.headers
    assert request.content == b"api=SYNO.API.Info"


def test_native_credentials_never_accept_a_supplied_identity_or_session():
    result = validate_create_credentials(
        "synology-nas",
        {"allow_writes": "false", "user_id": 999, "sid": "injected", "password": "secret"},
    )
    assert result == {"allow_writes": False}
    assert validate_create_credentials("synology-nas", {"allow_writes": "true"}) == {
        "allow_writes": True
    }
