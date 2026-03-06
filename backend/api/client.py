"""Client heartbeat endpoints for local app runtime management."""

from __future__ import annotations

from fastapi import APIRouter

from backend.schemas import HeartbeatRequest, HeartbeatResponse
from backend.services.runtime_state import register_heartbeat


router = APIRouter(prefix="/api/client", tags=["client"])


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(payload: HeartbeatRequest) -> HeartbeatResponse:
    register_heartbeat(payload.clientId)
    return HeartbeatResponse()
