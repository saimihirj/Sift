"""Session management endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

import memory
from state import ConversationState

from backend.schemas import (
    ClearHistoryRequest,
    ClearHistoryResponse,
    SessionListResponse,
    SessionResponse,
    SessionRuntimeResponse,
    SessionRuntimeUpdateRequest,
    StartSessionRequest,
    StartSessionResponse,
)
from backend.services.deck_review import normalize_evaluator_mode, present_deck_review_report
from backend.services.expert_agent import build_expert_opening, get_expert_quick_actions
from backend.services.evaluator import (
    build_evaluation_report,
    initial_evaluation_metadata,
    naturalize_evaluation_report,
    normalize_budget,
    normalize_session_type,
    phrase_evaluator_turn,
    _question_context_hint,
    _question_probe_intent,
    _refresh_intake_state,
    _report_readiness,
    present_evaluation_report,
    public_question,
    public_progress,
    select_next_question,
)
from backend.services.model_router import default_model_for_provider, model_supports_vision, normalize_provider, provider_catalog
from backend.services.prompting import DEFAULT_RESPONSE_PROFILE, build_personalized_opening, get_chip_suggestions
from backend.services.refinement import empty_answer_record, refine_founder_input, update_answer_record
from backend.services.retrieval import infer_retrieval_needs
from backend.services.state_engine import coverage_items, last_assistant_message, next_gap
from backend.services.uploads import list_active_uploads
from backend.services.website_fetch import fetch_website_context


router = APIRouter(prefix="/api/session", tags=["session"])


def _empty_analysis_snapshot() -> dict:
    return {
        "strengths": [],
        "risks": [],
        "missingEvidence": [],
        "contradictions": [],
        "nextQuestions": [],
        "recommendedNextActions": [],
        "concepts": [],
    }


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
            "geography": session_row.get("geography", "unspecified"),
            "company_name": session_row.get("company_name", ""),
        }
    )


def _session_metadata(row: dict | None) -> dict:
    return memory.get_session_metadata(row)


def _seed_session_refinement_metadata(
    state: ConversationState,
    *,
    setup_context: str = "",
    website: dict | None = None,
) -> dict:
    metadata = {
        "setupContext": (setup_context or "").strip(),
        "website": website or {},
        "geography": state.geography,
        "domainFocus": [],
        "answerRecord": empty_answer_record(),
        "assumptionsToVerify": [],
        "conversationMove": "",
        "needsInfo": [],
        "retrievalGap": "",
        "sourceConflict": "",
        "lastQuestionStem": "",
        "lastMoveType": "",
        "lastReflectionUsed": "",
        "stableWorkflow": False,
        "runtimeHealth": {"readTimeouts": 0, "slowTurns": 0},
    }
    combined = "\n\n".join(
        bit
        for bit in [metadata["setupContext"], metadata["website"].get("text", "").strip()]
        if bit
    )
    if not combined.strip():
        return metadata

    refinement = refine_founder_input(combined, state=state)
    metadata["domainFocus"] = refinement["domainFocus"]
    metadata["assumptionsToVerify"] = refinement["assumptionsToVerify"]
    metadata["answerRecord"] = update_answer_record(
        metadata["answerRecord"],
        combined,
        refinement["domainFocus"],
        source="setup",
        evidence_status=refinement["evidenceStatus"],
        assumptions=refinement["assumptionsToVerify"],
    )
    return metadata


def _response_extensions(metadata: dict) -> dict:
    return {
        "sources": list(metadata.get("sources", [])),
        "confidence": float(metadata.get("confidence", 0.0) or 0.0),
        "knowledgeLane": str(metadata.get("knowledgeLane", "general") or "general"),
        "usedLiveWeb": bool(metadata.get("usedLiveWeb", False)),
        "followUpMode": str(metadata.get("followUpMode", "") or ""),
        "helpMode": str(metadata.get("helpMode", "coach_me") or "coach_me"),
        "liveWebEnabled": bool(metadata.get("liveWebEnabled", False)),
        "analysisSnapshot": metadata.get("activeAnalysis") or _empty_analysis_snapshot(),
    }


def _session_profile(turns: list[dict]) -> str:
    for turn in reversed(turns):
        if turn["role"] != "assistant":
            continue
        profile = turn.get("metadata", {}).get("responseProfile")
        if profile in ("speed", "balanced"):
            return profile
    return DEFAULT_RESPONSE_PROFILE


def _session_summary(row: dict) -> dict:
    metadata = _session_metadata(row)
    evaluator_mode = normalize_evaluator_mode(metadata.get("evaluatorMode"))
    title = row.get("company_name") or f"{row.get('sector', 'unknown').upper()} · {row.get('stage', 'unknown')}"
    if row.get("session_type") == "evaluator" and not row.get("company_name"):
        title = f"{'Deck review' if evaluator_mode == 'deck_review' else 'Evaluate'} · {row.get('sector', 'unknown').upper()}"
    if row.get("session_type") == "expert" and not row.get("company_name"):
        title = f"Expert · {row.get('sector', 'unknown').upper()}"
    workflow_label = "ideate"
    if row.get("session_type") == "evaluator":
        workflow_label = "deck review" if evaluator_mode == "deck_review" else "evaluate"
    elif row.get("session_type") == "expert":
        workflow_label = "expert"
    subtitle_bits = [
        row.get("display_name", "").strip(),
        row.get("founder_type", "unknown"),
        f"{workflow_label} · {row.get('mode', 'think_it_through').replace('_', ' ')}",
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


@router.post("/clear-history", response_model=ClearHistoryResponse)
async def clear_user_history(payload: ClearHistoryRequest) -> ClearHistoryResponse:
    cleared = memory.clear_history_for_user(payload.clientId)
    return ClearHistoryResponse(
        ok=True,
        sessionsDeleted=cleared["sessions"],
        turnsDeleted=cleared["turns"],
        eventsDeleted=cleared["events"],
    )


@router.post("/start", response_model=StartSessionResponse)
async def start_session(payload: StartSessionRequest) -> StartSessionResponse:
    session_type = normalize_session_type(payload.sessionType)
    provider = normalize_provider(payload.provider)
    model = payload.model.strip() or default_model_for_provider(provider)
    question_budget = normalize_budget(payload.questionBudget)
    user_role = payload.userRole or payload.founderType
    state = ConversationState(
        founder_type=user_role,
        sector=payload.sector,
        stage=payload.stage,
        mode=payload.mode,
        geography=(payload.geography or "").strip() or "unspecified",
    )
    website_result = {}
    if payload.websiteUrl.strip():
        website_result = await fetch_website_context(payload.websiteUrl)

    if session_type == "evaluator":
        evaluator_mode = normalize_evaluator_mode(payload.evaluatorMode)
        metadata = initial_evaluation_metadata(
            question_budget=question_budget,
            provider=provider,
            model=model,
            setup_context=payload.setupContext,
            website=website_result,
            founder_type=user_role,
            sector=payload.sector,
            stage=payload.stage,
            mode=payload.mode,
            geography=state.geography,
            evaluator_mode=evaluator_mode,
        )
        has_starting_context = bool((payload.setupContext or "").strip() or website_result.get("text", "").strip())
        if evaluator_mode == "deck_review":
            opening = "Upload the deck. I’ll review it against the template, flag what is missing, and avoid guessing."
            metadata["stopReason"] = "Upload a deck to start the review."
        elif has_starting_context:
            metadata["intakeComplete"] = True
            _refresh_intake_state(metadata)
            ready, stop_reason = _report_readiness(metadata)
            metadata["stopReason"] = stop_reason
            if ready:
                metadata["completed"] = True
                metadata["completedAt"] = datetime.now(timezone.utc).isoformat()
                opening = "I've got enough context to evaluate this directly. Let me build the report."
            else:
                first_question = select_next_question(state, metadata)
                if first_question is None:
                    raise HTTPException(status_code=500, detail="Failed to initialize evaluator questions")
                metadata["askedQuestionIds"].append(first_question["id"])
                metadata["currentQuestionId"] = first_question["id"]
                probe_intent = _question_probe_intent(first_question, state, metadata)
                context_hint = _question_context_hint(first_question, state, metadata)
                intake_context = "\n\n".join(
                    bit
                    for bit in [
                        payload.setupContext.strip(),
                        website_result.get("text", "").strip(),
                    ]
                    if bit
                )[:900]
                needs_info = infer_retrieval_needs(intake_context or first_question["text"], state)
                phrased = await phrase_evaluator_turn(
                    provider=provider,
                    model=model,
                    api_key=payload.apiKey or None,
                    state=state,
                    metadata=metadata,
                    question=first_question,
                    probe_intent=probe_intent,
                    default_reciprocal="I've got enough context to pressure-test the weak spots.",
                    context_hint=context_hint,
                    latest_answer=payload.setupContext,
                    opening_style="first_follow_up",
                    retrieval_context=intake_context,
                    needs_info=needs_info,
                    move_type="move_to_next_gap",
                )
                metadata["nextProbeIntent"] = probe_intent
                metadata["currentQuestionSurfaceText"] = phrased["question"]
                metadata["currentQuestionContextHint"] = context_hint
                metadata["conversationMove"] = probe_intent
                metadata["needsInfo"] = needs_info
                metadata["retrievalGap"] = ""
                metadata["sourceConflict"] = ""
                metadata["lastQuestionStem"] = " ".join(phrased["question"].split()[:6])
                metadata["lastMoveType"] = "move_to_next_gap"
                metadata["lastReflectionUsed"] = " ".join(phrased["reciprocal"].split()[:6])
                first_public_question = public_question(first_question, state, metadata)
                opening = f"{phrased['reciprocal']}\n\n{first_public_question['text']}"
        else:
            opening = "Hi. What are you building? Paste the pitch, deck notes, or URL. Half-baked answers are fine. I'll only ask what is missing."
    else:
        metadata = _seed_session_refinement_metadata(
            state,
            setup_context=payload.setupContext,
            website=website_result,
        )
        auto_research_enabled = session_type == "expert" or bool(payload.liveWebEnabled)
        metadata.update(
            {
                "userRole": user_role,
                "geographyMode": (payload.geography or "auto").strip().lower() or "auto",
                "knowledgeLane": metadata.get("knowledgeLane", "startup"),
                "helpMode": payload.helpMode,
                "liveWebEnabled": auto_research_enabled,
                "sources": [],
                "confidence": 0.0,
                "usedLiveWeb": False,
                "followUpMode": "",
                "activeAnalysis": _empty_analysis_snapshot(),
            }
        )
        if session_type == "expert":
            opening = build_expert_opening(user_role, metadata["geographyMode"])
        else:
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
            "evaluatorMode": normalize_evaluator_mode(metadata.get("evaluatorMode")),
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
            "founderType": user_role,
            "userRole": user_role,
            "sector": payload.sector,
            "stage": payload.stage,
            "mode": payload.mode,
            "provider": provider,
            "model": model,
            "questionBudget": question_budget if session_type == "evaluator" else None,
            "evaluatorMode": normalize_evaluator_mode(metadata.get("evaluatorMode")) if session_type == "evaluator" else None,
            "helpMode": payload.helpMode,
            "liveWebEnabled": bool(payload.liveWebEnabled),
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
                "evaluatorMode": normalize_evaluator_mode(metadata.get("evaluatorMode")),
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
    elif website_result and not website_result.get("ok"):
        memory.track_event(
            event_type="website_fetch_failed",
            client_id=payload.clientId or "",
            session_id=session_id,
            display_name=payload.displayName or "",
            pathname="/",
            metadata={"url": payload.websiteUrl, "warning": website_result.get("warning", "")},
        )

    evaluation_report = None
    deck_evaluation_report = None
    if session_type == "evaluator":
        if normalize_evaluator_mode(metadata.get("evaluatorMode")) == "deck_review":
            deck_evaluation_report = present_deck_review_report(metadata)
        else:
            evaluation_report = build_evaluation_report(metadata)
            if metadata.get("completed"):
                evaluation_report = await naturalize_evaluation_report(
                    report=evaluation_report,
                    metadata=metadata,
                    state=state,
                    provider=provider,
                    model=model,
                    api_key=payload.apiKey or None,
                )
    return StartSessionResponse(
        sessionId=session_id,
        openingMessage=opening,
        state=state.to_dict(),
        chips=(
            get_chip_suggestions(state)
            if session_type == "mentor"
            else (get_expert_quick_actions() if session_type == "expert" else [])
        ),
        responseProfile=DEFAULT_RESPONSE_PROFILE,
        coverage=coverage_items(state),
        nextGap=next_gap(state),
        activeUploads=[],
        sessionType=session_type,
        evaluatorMode=normalize_evaluator_mode(metadata.get("evaluatorMode")),
        provider=provider,
        model=model,
        supportsVision=model_supports_vision(provider, model),
        questionBudget=question_budget if session_type == "evaluator" else None,
        websiteUrl=(payload.websiteUrl or "").strip(),
        **_response_extensions(metadata),
        evaluationProgress=public_progress(metadata, state) if session_type == "evaluator" else None,
        evaluationReport=evaluation_report,
        deckEvaluationReport=deck_evaluation_report,
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
    evaluation_report = None
    deck_evaluation_report = None
    if session_type == "evaluator":
        if normalize_evaluator_mode(metadata.get("evaluatorMode")) == "deck_review":
            deck_evaluation_report = present_deck_review_report(metadata)
        else:
            evaluation_report = present_evaluation_report(metadata)
    return SessionResponse(
        sessionId=session_id,
        history=history,
        state=state.to_dict(),
        chips=(
            get_chip_suggestions(state, last_assistant_message(history))
            if session_type == "mentor"
            else (get_expert_quick_actions() if session_type == "expert" else [])
        ),
        responseProfile=_session_profile(turns),
        coverage=coverage_items(state),
        nextGap=next_gap(state),
        activeUploads=list_active_uploads(session_id),
        sessionType=session_type,
        evaluatorMode=normalize_evaluator_mode(metadata.get("evaluatorMode")),
        provider=session_row.get("provider", "ollama"),
        model=session_row.get("model", ""),
        supportsVision=model_supports_vision(session_row.get("provider", "ollama"), session_row.get("model", "")),
        questionBudget=session_row.get("question_budget"),
        websiteUrl=session_row.get("website_url", ""),
        **_response_extensions(metadata),
        evaluationProgress=public_progress(metadata, state) if session_type == "evaluator" else None,
        evaluationReport=evaluation_report,
        deckEvaluationReport=deck_evaluation_report,
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
    return SessionRuntimeResponse(
        sessionId=session_id,
        provider=provider,
        model=model,
        supportsVision=model_supports_vision(provider, model),
    )
