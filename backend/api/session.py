"""Session management endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query

import memory
from state import ConversationState

from backend.schemas import (
    SessionListResponse,
    SessionResponse,
    SessionRuntimeResponse,
    SessionRuntimeUpdateRequest,
    StartSessionRequest,
    StartSessionResponse,
)
from backend.services.evaluator import (
    build_evaluation_report,
    initial_evaluation_metadata,
    normalize_budget,
    normalize_session_type,
    public_progress,
    select_next_question,
)
from backend.services.model_router import default_model_for_provider, normalize_provider, provider_catalog
from backend.services.prompting import DEFAULT_RESPONSE_PROFILE, build_personalized_opening, get_chip_suggestions
from backend.services.state_engine import coverage_items, last_assistant_message, next_gap
from backend.services.uploads import list_active_uploads
from backend.services.website_fetch import fetch_website_context


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


def _session_metadata(row: dict | None) -> dict:
    return memory.get_session_metadata(row)


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
    if row.get("session_type") == "evaluator" and not row.get("company_name"):
        title = f"Evaluator · {row.get('sector', 'unknown').upper()}"
    subtitle_bits = [
        row.get("display_name", "").strip(),
        row.get("founder_type", "unknown"),
        (
            f"evaluation · {row.get('mode', 'think_it_through').replace('_', ' ')}"
            if row.get("session_type") == "evaluator"
            else row.get("mode", "think_it_through").replace("_", " ")
        ),
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
        "sessionType": row.get("session_type", "mentor"),
        "provider": row.get("provider", "ollama"),
        "model": row.get("model", ""),
        "questionBudget": row.get("question_budget"),
    }


@router.get("", response_model=SessionListResponse)
async def list_user_sessions(clientId: str = Query(default="")) -> SessionListResponse:
    sessions = memory.list_sessions_for_user(clientId, limit=30)
    return SessionListResponse(sessions=[_session_summary(item) for item in sessions])


@router.get("/providers")
async def list_providers() -> dict:
    return {"providers": provider_catalog()}


@router.post("/start", response_model=StartSessionResponse)
async def start_session(payload: StartSessionRequest) -> StartSessionResponse:
    session_type = normalize_session_type(payload.sessionType)
    provider = normalize_provider(payload.provider)
    model = payload.model.strip() or default_model_for_provider(provider)
    question_budget = normalize_budget(payload.questionBudget)
    state = ConversationState(
        founder_type=payload.founderType,
        sector=payload.sector,
        stage=payload.stage,
        mode=payload.mode,
    )
    website_result = {}
    if session_type == "evaluator" and payload.websiteUrl.strip():
        website_result = await fetch_website_context(payload.websiteUrl)

    if session_type == "evaluator":
        metadata = initial_evaluation_metadata(
            question_budget=question_budget,
            provider=provider,
            model=model,
            setup_context=payload.setupContext,
            website=website_result,
        )
        has_starting_context = bool((payload.setupContext or "").strip() or website_result.get("text", "").strip())
        evaluator_style = "guided build" if payload.mode == "think_it_through" else "tight review"
        if has_starting_context:
            metadata["intakeComplete"] = True
            first_question = select_next_question(state, metadata)
            if first_question is None:
                raise HTTPException(status_code=500, detail="Failed to initialize evaluator questions")
            metadata["askedQuestionIds"].append(first_question["id"])
            metadata["currentQuestionId"] = first_question["id"]
            opening = f"I've got enough context to dive in. We’ll keep this {evaluator_style} and adaptive.\n\nFirst question: {first_question['text']}"
        else:
            opening = "Hi. What are you building? Give me the problem, who it is for, and anything you already know."
    else:
        metadata = {}
        opening = build_personalized_opening(state.founder_type, state.sector, state.stage)

    session_id = memory.create_session(
        state,
        user_identifier=payload.clientId or "",
        display_name=payload.displayName or "",
        session_type=session_type,
        question_budget=question_budget,
        provider=provider,
        model=model,
        website_url=payload.websiteUrl,
        metadata=metadata,
    )
    memory.store_turn(
        session_id,
        "assistant",
        opening,
        metadata={
            "responseProfile": DEFAULT_RESPONSE_PROFILE,
            "state_snapshot": state.to_dict(),
            "sessionType": session_type,
        },
    )
    memory.track_event(
        event_type="session_started",
        client_id=payload.clientId or "",
        session_id=session_id,
        display_name=payload.displayName or "",
        pathname="/",
        metadata={
            "sessionType": session_type,
            "founderType": payload.founderType,
            "sector": payload.sector,
            "stage": payload.stage,
            "mode": payload.mode,
            "provider": provider,
            "model": model,
            "questionBudget": question_budget,
        },
    )
    if session_type == "evaluator":
        memory.track_event(
            event_type="evaluator_started",
            client_id=payload.clientId or "",
            session_id=session_id,
            display_name=payload.displayName or "",
            pathname="/",
            metadata={
                "provider": provider,
                "model": model,
                "questionBudget": question_budget,
            },
        )
        if website_result and not website_result.get("ok"):
            memory.track_event(
                event_type="website_fetch_failed",
                client_id=payload.clientId or "",
                session_id=session_id,
                display_name=payload.displayName or "",
                pathname="/",
                metadata={"url": payload.websiteUrl, "warning": website_result.get("warning", "")},
            )

    evaluation_progress = public_progress(metadata) if session_type == "evaluator" else None
    evaluation_report = build_evaluation_report(metadata) if session_type == "evaluator" else None
    return StartSessionResponse(
        sessionId=session_id,
        openingMessage=opening,
        state=state.to_dict(),
        chips=get_chip_suggestions(state) if session_type == "mentor" else [],
        responseProfile=DEFAULT_RESPONSE_PROFILE,
        coverage=coverage_items(state),
        nextGap=next_gap(state),
        activeUploads=[],
        sessionType=session_type,
        provider=provider,
        model=model,
        questionBudget=question_budget,
        websiteUrl=(payload.websiteUrl or "").strip(),
        evaluationProgress=evaluation_progress,
        evaluationReport=evaluation_report,
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    session_row = memory.get_session(session_id)
    if session_row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    turns = memory.get_session_turns(session_id)
    state = _session_state_from_storage(session_row, turns)
    metadata = _session_metadata(session_row)
    session_type = session_row.get("session_type", "mentor")
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
        chips=get_chip_suggestions(state, last_assistant_message(history)) if session_type == "mentor" else [],
        responseProfile=_session_profile(turns),
        coverage=coverage_items(state),
        nextGap=next_gap(state),
        activeUploads=list_active_uploads(session_id),
        sessionType=session_type,
        provider=session_row.get("provider", "ollama"),
        model=session_row.get("model", ""),
        questionBudget=session_row.get("question_budget"),
        websiteUrl=session_row.get("website_url", ""),
        evaluationProgress=public_progress(metadata) if session_type == "evaluator" else None,
        evaluationReport=build_evaluation_report(metadata) if session_type == "evaluator" else None,
    )


@router.post("/{session_id}/runtime", response_model=SessionRuntimeResponse)
async def update_runtime(session_id: str, payload: SessionRuntimeUpdateRequest) -> SessionRuntimeResponse:
    session_row = memory.get_session(session_id)
    if session_row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    provider = normalize_provider(payload.provider)
    model = payload.model.strip() or default_model_for_provider(provider)
    memory.update_session_runtime(session_id, provider, model)
    memory.track_event(
        event_type="session_runtime_updated",
        client_id=session_row.get("user_identifier", ""),
        session_id=session_id,
        display_name=session_row.get("display_name", ""),
        pathname="/",
        metadata={"provider": provider, "model": model},
    )
    return SessionRuntimeResponse(sessionId=session_id, provider=provider, model=model)
