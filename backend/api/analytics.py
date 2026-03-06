"""Analytics event endpoints."""

from __future__ import annotations

from fastapi import APIRouter

import memory

from backend.schemas import AnalyticsEventRequest, AnalyticsEventResponse


router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.post("/event", response_model=AnalyticsEventResponse)
async def create_event(payload: AnalyticsEventRequest) -> AnalyticsEventResponse:
    memory.track_event(
        event_type=payload.eventType,
        client_id=payload.clientId,
        session_id=payload.sessionId,
        display_name=payload.displayName,
        pathname=payload.pathname,
        metadata=payload.metadata,
    )
    return AnalyticsEventResponse()
