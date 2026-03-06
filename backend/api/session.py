"""Session management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

import memory
from state import ConversationState

from backend.schemas import SessionListResponse, SessionResponse, StartSessionRequest, StartSessionResponse
from backend.services.prompting import DEFAULT_RESPONSE_PROFILE, build_personalized_opening, get_chip_suggestions
from backend.services.state_engine import coverage_items, last_assistant_message, next_gap
from backend.services.uploads import list_active_uploads


router = APIRouter(prefix="/api/session", tags=["session"])


def _session_state_from_storage(session_row: dict | None, turns: list[dict]) -> ConversationState:
    for turn in reversed(turns):
        snapshot = turn.get("metadata", {}).get("state_snapshot")
        if isinstance(snapshot, dict):
            return ConversationState.from_dict(snapshot)

    if not session_row:
        return ConversationState()

    return ConversationState.from_dict(
        {
            "coverage": session_row.get("coverage_json") and __import__("json").loads(session_row["coverage_json"]) or {},
            "facts": session_row.get("facts_json") and __import__("json").loads(session_row["facts_json"]) or {},
            "sector": session_row.get("sector", "unknown"),
            "stage": session_row.get("stage", "unknown"),
            "founder_type": session_row.get("founder_type", "unknown"),
            "mode": session_row.get("mode", "think_it_through"),
            "company_name": session_row.get("company_name", ""),
        }
    )


def _session_profile(turns: list[dict]) -> str:
    for turn in reversed(turns):
        if turn["role"] != "assistant":
            continue
        profile = turn.get("metadata", {}).get("responseProfile")
        if profile in ("speed", "balanced"):
            return profile
    return DEFAULT_RESPONSE_PROFILE


def _session_summary(row: dict) -> dict:
    title = row.get("company_name") or f"{row.get('sector', 'unknown').upper()} · {row.get('stage', 'unknown')}"
    subtitle_bits = [
        row.get("display_name", "").strip(),
        row.get("founder_type", "unknown"),
        row.get("mode", "think_it_through").replace("_", " "),
    ]
    subtitle = " · ".join(bit for bit in subtitle_bits if bit)
    return {
        "sessionId": row["id"],
        "title": title,
        "subtitle": subtitle,
        "lastActive": row.get("last_active"),
        "turnCount": int(row.get("turn_count", 0) or 0),
        "companyName": row.get("company_name", ""),
        "displayName": row.get("display_name", ""),
        "sector": row.get("sector", "unknown"),
        "stage": row.get("stage", "unknown"),
    }


@router.get("", response_model=SessionListResponse)
async def list_user_sessions(clientId: str = Query(default="")) -> SessionListResponse:
    sessions = memory.list_sessions_for_user(clientId, limit=30)
    return SessionListResponse(sessions=[_session_summary(item) for item in sessions])


@router.post("/start", response_model=StartSessionResponse)
async def start_session(payload: StartSessionRequest) -> StartSessionResponse:
    state = ConversationState(
        founder_type=payload.founderType,
        sector=payload.sector,
        stage=payload.stage,
        mode=payload.mode,
    )
    opening = build_personalized_opening(state.founder_type, state.sector, state.stage)
    session_id = memory.create_session(
        state,
        user_identifier=payload.clientId or "",
        display_name=payload.displayName or "",
    )
    memory.store_turn(
        session_id,
        "assistant",
        opening,
        metadata={
            "responseProfile": DEFAULT_RESPONSE_PROFILE,
            "state_snapshot": state.to_dict(),
        },
    )
    memory.track_event(
        event_type="session_started",
        client_id=payload.clientId or "",
        session_id=session_id,
        display_name=payload.displayName or "",
        pathname="/",
        metadata={
            "founderType": payload.founderType,
            "sector": payload.sector,
            "stage": payload.stage,
            "mode": payload.mode,
        },
    )
    return StartSessionResponse(
        sessionId=session_id,
        openingMessage=opening,
        state=state.to_dict(),
        chips=get_chip_suggestions(state),
        responseProfile=DEFAULT_RESPONSE_PROFILE,
        coverage=coverage_items(state),
        nextGap=next_gap(state),
        activeUploads=[],
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    session_row = memory.get_session(session_id)
    if session_row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    turns = memory.get_session_turns(session_id)
    state = _session_state_from_storage(session_row, turns)
    history = [
        {
            "role": turn["role"],
            "content": turn["content"],
            "timestamp": turn.get("timestamp"),
            "metadata": turn.get("metadata", {}),
        }
        for turn in turns
        if turn["role"] in ("user", "assistant")
    ]
    return SessionResponse(
        sessionId=session_id,
        history=history,
        state=state.to_dict(),
        chips=get_chip_suggestions(state, last_assistant_message(history)),
        responseProfile=_session_profile(turns),
        coverage=coverage_items(state),
        nextGap=next_gap(state),
        activeUploads=list_active_uploads(session_id),
    )
