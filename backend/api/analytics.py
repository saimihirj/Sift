"""Analytics event endpoints."""

from __future__ import annotations

import os
from fastapi import APIRouter
from backend.core import memory
from backend.schemas import AnalyticsEventRequest, AnalyticsEventResponse

try:
    from posthog import Posthog
    _posthog_client = None
    if os.environ.get("POSTHOG_PROJECT_API_KEY"):
        _posthog_client = Posthog(
            project_api_key=os.environ.get("POSTHOG_PROJECT_API_KEY", ""),
            host=os.environ.get("POSTHOG_HOST", "https://app.posthog.com")
        )
except ImportError:
    _posthog_client = None

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
    
    if _posthog_client and (payload.clientId or payload.sessionId):
        _posthog_client.capture(
            distinct_id=payload.clientId or payload.sessionId or "anonymous",
            event=payload.eventType,
            properties={
                "session_id": payload.sessionId,
                "display_name": payload.displayName,
                "pathname": payload.pathname,
                **(payload.metadata or {})
            }
        )

    return AnalyticsEventResponse()
