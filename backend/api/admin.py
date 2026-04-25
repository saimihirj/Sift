"""Admin monitoring endpoints."""

from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException, Query

import memory

from backend.schemas import AdminEventsResponse, AdminOverviewResponse, SessionSummary


router = APIRouter(prefix="/api/admin", tags=["admin"])


def _admin_mode_enabled() -> bool:
    return os.environ.get("SIFT_ADMIN_MODE", "false").strip().lower() == "true"


def _require_admin_token(header_token: str | None) -> None:
    if not _admin_mode_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    expected = os.environ.get("SIFT_ADMIN_TOKEN", "").strip()
    if not expected:
        return
    if (header_token or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Invalid admin token")


def _session_summary(row: dict) -> dict:
    title = row.get("company_name") or f"{row.get('sector', 'unknown').upper()} · {row.get('stage', 'unknown')}"
    subtitle_bits = [row.get("display_name", "").strip(), row.get("founder_type", "unknown"), row.get("mode", "think_it_through").replace("_", " ")]
    subtitle = " · ".join(bit for bit in subtitle_bits if bit)
    return SessionSummary(
        sessionId=row["id"],
        title=title,
        subtitle=subtitle,
        lastActive=row.get("last_active"),
        turnCount=int(row.get("turn_count", 0) or 0),
        companyName=row.get("company_name", ""),
        displayName=row.get("display_name", ""),
        sector=row.get("sector", "unknown"),
        stage=row.get("stage", "unknown"),
    ).model_dump()


@router.get("/overview", response_model=AdminOverviewResponse)
async def get_admin_overview(x_admin_token: str | None = Header(default=None)) -> AdminOverviewResponse:
    _require_admin_token(x_admin_token)
    return AdminOverviewResponse(**memory.get_admin_overview())


@router.get("/events", response_model=AdminEventsResponse)
async def get_admin_events(
    limit: int = Query(default=60, ge=1, le=200),
    x_admin_token: str | None = Header(default=None),
) -> AdminEventsResponse:
    _require_admin_token(x_admin_token)
    return AdminEventsResponse(
        events=memory.list_recent_events(limit=limit, current_build_only=True, useful_only=True),
        sessions=[_session_summary(item) for item in memory.list_sessions(limit=20)],
    )
