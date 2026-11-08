"""DSM browser session bootstrap; only mounted in the native DSM package."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

from octop.infra.auth.tokens import sign_token

router = APIRouter()
logger = logging.getLogger(__name__)


class DsmSessionResponse(BaseModel):
    access_token: str
    user_id: int


@router.get(
    "/dsm/session",
    response_model=DsmSessionResponse,
    summary="Use the current DSM browser session",
    description=(
        "Requires a live DSM session. The returned token remains bound to that session. "
        "On first use, creates a private built-in NAS connector and Synology expert for this user."
    ),
)
async def dsm_session(request: Request) -> DsmSessionResponse:
    server = request.app.state.octop_server
    user = request.state.octop_user
    native = server.native_synology
    if native is not None:
        try:
            await native.ensure_defaults(user)
        except Exception as exc:
            # Optional expert provisioning must never become a login prerequisite.
            # Log only the failure class: exceptions may contain private context.
            logger.warning(
                "DSM default expert could not be created user_id=%s failure=%s",
                user.id,
                type(exc).__name__,
            )
    token = sign_token(
        server.services.secret_repo.get("jwt"),
        sub=user.id,
        uname=user.username,
        role=user.role,
        ttl_seconds=server.services.config.access_token_ttl_seconds,
        dsm_session=request.state.dsm_session,
    )
    return DsmSessionResponse(access_token=token, user_id=user.id)
