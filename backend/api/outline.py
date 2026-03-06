"""Outline generation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

import memory
from state import ConversationState

from backend.schemas import OutlineRequest, OutlineResponse
from backend.services.model_router import generate_text
from backend.services.prompting import build_outline_prompt


router = APIRouter(prefix="/api/outline", tags=["outline"])


def _restore_state(turns: list[dict], session_row: dict) -> ConversationState:
    for turn in reversed(turns):
        snapshot = turn.get("metadata", {}).get("state_snapshot")
        if isinstance(snapshot, dict):
            return ConversationState.from_dict(snapshot)
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


def _preferred_profile(turns: list[dict]) -> str:
    for turn in reversed(turns):
        if turn["role"] == "assistant":
            profile = turn.get("metadata", {}).get("responseProfile")
            if profile in ("speed", "balanced"):
                return profile
    return "speed"


@router.post("", response_model=OutlineResponse)
async def create_outline(payload: OutlineRequest) -> OutlineResponse:
    session_row = memory.get_session(payload.sessionId)
    if session_row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    turns = memory.get_session_turns(payload.sessionId)
    history = [
        {"role": turn["role"], "content": turn["content"]}
        for turn in turns
        if turn["role"] in ("user", "assistant")
    ]
    state = _restore_state(turns, session_row)
    prompt = build_outline_prompt(state, history)
    result = await generate_text(
        system="You turn mentor transcripts into clean pitch outlines.",
        messages=[{"role": "user", "content": prompt}],
        response_profile=_preferred_profile(turns),
        max_tokens=900,
    )
    memory.track_event(
        event_type="outline_opened",
        client_id=session_row.get("user_identifier", ""),
        session_id=payload.sessionId,
        display_name=session_row.get("display_name", ""),
        pathname=f"/outline/{payload.sessionId}",
        metadata={
            "responseProfile": result["responseProfile"],
            "model": result["model"],
            "totalSeconds": result["timings"].get("totalSeconds", 0),
        },
    )
    return OutlineResponse(
        sessionId=payload.sessionId,
        markdown=result["message"],
        responseProfile=result["responseProfile"],
    )
