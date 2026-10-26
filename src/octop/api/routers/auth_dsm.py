"""DSM browser session bootstrap; only mounted in the native DSM package."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from octop.infra.auth.tokens import sign_token

router = APIRouter()


class DsmSessionResponse(BaseModel):
    access_token: str
    user_id: int


@router.get(
    "/dsm/session",
    response_model=DsmSessionResponse,
    summary="Use the current DSM browser session",
    description="Requires a live DSM session. The returned token remains bound to that session.",
)
async def dsm_session(request: Request) -> DsmSessionResponse:
    server = request.app.state.octop_server
    user = request.state.octop_user
    token = sign_token(
        server.services.secret_repo.get("jwt"),
        sub=user.id,
        uname=user.username,
        role=user.role,
        ttl_seconds=server.services.config.access_token_ttl_seconds,
        dsm_session=request.state.dsm_session,
    )
    return DsmSessionResponse(access_token=token, user_id=user.id)
