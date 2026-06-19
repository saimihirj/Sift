"""Adaptive evaluator endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile

from backend.core import memory
from backend.core.state import ConversationState

from backend.schemas import EvaluatorAnswerResponse, EvaluatorReportResponse
from backend.services.deck_review import (
    answer_deck_follow_up,
    normalize_evaluator_mode,
    present_deck_review_report,
    review_deck_session,
)
from backend.services.evaluator import (
    build_evaluation_report,
    continue_evaluation_deeper,
    evaluate_answer,
    has_cached_presentable_report,
    naturalize_evaluation_report,
    present_evaluation_report,
    public_progress,
)
from backend.services.model_router import (
    accumulate_runtime_usage,
    default_model_for_provider,
    empty_runtime_usage,
    model_supports_vision,
    normalize_provider,
    normalize_usage,
)
from backend.services.retrieval import build_retrieval_context
from backend.services.session_access import require_session_owner
from backend.services.state_engine import update_state_from_turn
from backend.services.uploads import ingest_upload, list_active_uploads, retrieve_upload_context


router = APIRouter(prefix="/api/evaluator", tags=["evaluator"])


def _runtime_usage(metadata: dict) -> dict:
    usage = metadata.get("runtimeUsage")
    return usage if isinstance(usage, dict) else empty_runtime_usage()


def _restore_state(session_row: dict, turns: list[dict]) -> ConversationState:
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
            "geography": session_row.get("geography", "unspecified"),
            "company_name": session_row.get("company_name", ""),
        }
    )


@router.post("/answer", response_model=EvaluatorAnswerResponse)
async def answer_question(
    sessionId: str = Form(...),
    clientId: str = Form(""),
    answer: str = Form(""),
    evaluatorMode: str = Form(""),
    provider: str = Form(""),
    model: str = Form(""),
    apiKey: str = Form(""),
    file: UploadFile | None = File(default=None),
) -> EvaluatorAnswerResponse:
    session_row = memory.get_session(sessionId)
    if session_row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    require_session_owner(session_row, clientId)
    if session_row.get("session_type") != "evaluator":
        raise HTTPException(status_code=400, detail="This session is not an evaluator session")

    metadata = memory.get_session_metadata(session_row)
    active_mode = normalize_evaluator_mode(evaluatorMode or metadata.get("evaluatorMode"))
    current_mode = normalize_evaluator_mode(metadata.get("evaluatorMode"))
    metadata["evaluatorMode"] = active_mode
    if active_mode != current_mode:
        if metadata.get("answers") or list_active_uploads(sessionId):
            raise HTTPException(status_code=400, detail="Start a new Evaluate session to switch review modes after work has started")
        metadata["evaluatorMode"] = active_mode
        metadata["stopReason"] = "Upload a deck to start the review." if active_mode == "deck_review" else "Gathering evidence."

    chosen_provider = normalize_provider(provider or session_row.get("provider", "ollama"))
    chosen_model = (model or session_row.get("model", "")).strip() or default_model_for_provider(chosen_provider)
    if chosen_provider != session_row.get("provider", "ollama") or chosen_model != (session_row.get("model", "") or ""):
        memory.update_session_runtime(sessionId, chosen_provider, chosen_model)
        session_row["provider"] = chosen_provider
        session_row["model"] = chosen_model

    upload_entry = None
    if file is not None:
        try:
            upload_entry = await ingest_upload(sessionId, file)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    turns = memory.get_session_turns(sessionId)
    state = _restore_state(session_row, turns)
    supports_vision = model_supports_vision(chosen_provider, chosen_model)

    answer_text = answer.strip()
    if active_mode == "deck_review":
        if upload_entry is None and not list_active_uploads(sessionId):
            raise HTTPException(status_code=400, detail="Upload a PDF or PPTX deck to start deck review")

        if upload_entry is not None or not metadata.get("completed"):
            context_bits = [answer_text]
            if upload_entry is not None:
                context_bits.append(f"Uploaded deck: {upload_entry['name']}.")
            review_report = await review_deck_session(
                session_id=sessionId,
                provider=chosen_provider,
                model=chosen_model,
                api_key=apiKey or None,
                user_context="\n\n".join(bit for bit in context_bits if bit),
            )
            metadata["evaluatorMode"] = "deck_review"
            metadata["completed"] = True
            metadata["partial"] = False
            metadata["completedAt"] = datetime.now(timezone.utc).isoformat()
            metadata["currentQuestionId"] = ""
            metadata["stopReason"] = review_report.get("stopReason", "Deck review complete.")
            metadata["deckReviewRuns"] = int(metadata.get("deckReviewRuns", 0) or 0) + 1
            metadata["deckReviewSummary"] = review_report.get("summary", "")
            metadata["deckReviewReport"] = review_report
            run_usage = normalize_usage(review_report.get("runtimeUsage"))
            metadata["runtimeUsage"] = accumulate_runtime_usage(metadata.get("runtimeUsage"), run_usage)
            updated_state = update_state_from_turn(
                state,
                answer_text or (f"I uploaded {upload_entry['name']}." if upload_entry else ""),
                assistant_message=review_report.get("summary") or review_report.get("verdict") or "Deck review complete.",
            )
            user_content = answer_text if upload_entry is None else f"{answer_text}\n\n[Attached {upload_entry['name']}]".strip()
            if not user_content:
                user_content = f"[Attached {upload_entry['name']}]" if upload_entry else "[Deck review requested]"
            assistant_content = review_report.get("summary") or review_report.get("verdict") or "Deck review complete."
            memory.update_session(sessionId, updated_state)
            memory.update_session_metadata(sessionId, metadata)
            memory.store_turn(
                sessionId,
                "user",
                user_content,
                metadata={
                    "sessionType": "evaluator",
                    "evaluatorMode": "deck_review",
                    "upload": upload_entry,
                },
            )
            memory.store_turn(
                sessionId,
                "assistant",
                assistant_content,
                metadata={
                    "sessionType": "evaluator",
                    "evaluatorMode": "deck_review",
                    "responseProfile": "balanced",
                    "state_snapshot": updated_state.to_dict(),
                    "reviewMode": review_report.get("reviewMode", "text_transcript"),
                    "reviewLimitations": review_report.get("reviewLimitations", []),
                    "supportsVision": supports_vision,
                    "usage": run_usage,
                },
            )
            if upload_entry is not None:
                memory.track_event(
                    event_type="file_uploaded",
                    client_id=session_row.get("user_identifier", ""),
                    session_id=sessionId,
                    display_name=session_row.get("display_name", ""),
                    pathname="/",
                    metadata={
                        "name": upload_entry.get("name"),
                        "docType": upload_entry.get("docType"),
                        "chunkCount": upload_entry.get("chunkCount"),
                        "chars": upload_entry.get("chars"),
                        "sessionType": "evaluator",
                    },
                )
            memory.track_event(
                event_type="evaluator_completed",
                client_id=session_row.get("user_identifier", ""),
                session_id=sessionId,
                display_name=session_row.get("display_name", ""),
                pathname="/",
                metadata={
                    "provider": chosen_provider,
                    "model": chosen_model,
                    "overallScore": review_report.get("overallScore", 0),
                    "confidence": review_report.get("confidence", 0),
                    "stopReason": review_report.get("stopReason", ""),
                    "evaluatorMode": "deck_review",
                    "reviewMode": review_report.get("reviewMode", "text_transcript"),
                },
            )
            return EvaluatorAnswerResponse(
                sessionId=sessionId,
                evaluatorMode="deck_review",
                evaluationProgress=public_progress(metadata, updated_state),
                evaluationReport=None,
                deckEvaluationReport=review_report,
                reciprocal=assistant_content,
                question=None,
                questionLabel="",
                activeUploads=list_active_uploads(sessionId),
                warning=metadata.get("website", {}).get("warning", ""),
                supportsVision=supports_vision,
                runtimeUsage=metadata.get("runtimeUsage", _runtime_usage(metadata)),
            )

        follow_up = await answer_deck_follow_up(
            session_id=sessionId,
            report=present_deck_review_report(metadata),
            question=answer_text,
            provider=chosen_provider,
            model=chosen_model,
            api_key=apiKey or None,
        )
        follow_up_text = str(follow_up.get("message", "") or "")
        follow_up_usage = normalize_usage(follow_up.get("runtimeUsage"))
        metadata["runtimeUsage"] = accumulate_runtime_usage(metadata.get("runtimeUsage"), follow_up_usage)
        updated_state = update_state_from_turn(state, answer_text, assistant_message=follow_up_text)
        memory.update_session(sessionId, updated_state)
        memory.update_session_metadata(sessionId, metadata)
        memory.store_turn(
            sessionId,
            "user",
            answer_text,
            metadata={"sessionType": "evaluator", "evaluatorMode": "deck_review"},
        )
        memory.store_turn(
            sessionId,
            "assistant",
            follow_up,
            metadata={
                "sessionType": "evaluator",
                "evaluatorMode": "deck_review",
                "responseProfile": "balanced",
                "state_snapshot": updated_state.to_dict(),
                "reviewMode": metadata.get("deckReviewReport", {}).get("reviewMode", "text_transcript"),
                "reviewLimitations": metadata.get("deckReviewReport", {}).get("reviewLimitations", []),
                "supportsVision": supports_vision,
                "usage": follow_up_usage,
            },
        )
        return EvaluatorAnswerResponse(
            sessionId=sessionId,
            evaluatorMode="deck_review",
            evaluationProgress=public_progress(metadata, updated_state),
            evaluationReport=None,
            deckEvaluationReport=present_deck_review_report(metadata),
            reciprocal=follow_up_text,
            question=None,
            questionLabel="",
            activeUploads=list_active_uploads(sessionId),
            warning=metadata.get("website", {}).get("warning", ""),
            supportsVision=supports_vision,
            runtimeUsage=metadata.get("runtimeUsage", _runtime_usage(metadata)),
        )

    if metadata.get("completed"):
        raise HTTPException(status_code=400, detail="This evaluator is already complete")

    if not answer_text and upload_entry is None:
        raise HTTPException(status_code=400, detail="Answer or file is required")
    if not answer_text and upload_entry is not None:
        answer_text = f"I uploaded {upload_entry['name']}. Use it to assess my answer quality."

    upload_context_items = retrieve_upload_context(
        sessionId,
        query=f"{metadata.get('currentQuestionId', '')} {answer_text}",
        top_k=2,
        max_chars=900,
    )
    upload_context = "\n\n".join(item["text"] for item in upload_context_items)
    retrieval = build_retrieval_context(
        sessionId,
        state,
        f"{metadata.get('currentQuestionId', '')} {answer_text}".strip(),
        domain_focus=metadata.get("domainFocus", []),
        geography=getattr(state, "geography", metadata.get("geography", "unspecified")),
        assumptions_to_verify=metadata.get("assumptionsToVerify", []),
        answer_record=metadata.get("answerRecord"),
        session_context="\n\n".join(
            bit
            for bit in [
                str(metadata.get("setupContext", "")).strip(),
                (
                    metadata.get("website", {}).get("text", "").strip()
                    if isinstance(metadata.get("website"), dict)
                    else ""
                ),
            ]
            if bit
        ),
    )

    result = await evaluate_answer(
        state=state,
        metadata=metadata,
        answer=answer_text,
        provider=chosen_provider,
        model=chosen_model,
        api_key=apiKey or None,
        upload_context=upload_context,
        retrieval_context=retrieval["text"],
        needs_info=retrieval["needsInfo"],
        retrieval_gap=retrieval["retrievalGap"],
        source_conflict=retrieval["sourceConflict"],
    )

    updated_metadata = result["metadata"]
    answered = result.get("answered", {})
    report = result["report"]

    assistant_content = answered.get("reciprocal", "Assessment updated.")
    if updated_metadata.get("completed"):
        assistant_content = f"{assistant_content}\n\nI have enough. I’m building the report now."
    elif result.get("question"):
        assistant_content = f"{assistant_content}\n\n{result['question']['text']}"

    updated_state = update_state_from_turn(state, answer_text, assistant_message=assistant_content)
    if updated_metadata.get("completed"):
        report = await naturalize_evaluation_report(
            report=report,
            metadata=updated_metadata,
            state=updated_state,
            provider=chosen_provider,
            model=chosen_model,
            api_key=apiKey or None,
        )
    progress = public_progress(updated_metadata, updated_state)
    memory.update_session(sessionId, updated_state)
    memory.update_session_metadata(sessionId, updated_metadata)
    memory.store_turn(
        sessionId,
        "user",
        answer_text if upload_entry is None else f"{answer_text}\n\n[Attached {upload_entry['name']}]",
        metadata={
            "sessionType": "evaluator",
            "questionId": answered.get("questionId", updated_metadata.get("currentQuestionId", "")),
            "upload": upload_entry,
            "needsInfo": retrieval["needsInfo"],
            "retrievalGap": retrieval["retrievalGap"],
            "sourceConflict": retrieval["sourceConflict"],
        },
    )
    memory.store_turn(
        sessionId,
        "assistant",
        assistant_content,
        metadata={
            "sessionType": "evaluator",
            "responseProfile": "speed",
            "state_snapshot": updated_state.to_dict(),
            "questionId": result.get("question", {}).get("id", ""),
            "evaluation": answered,
            "needsInfo": retrieval["needsInfo"],
            "retrievalGap": retrieval["retrievalGap"],
            "sourceConflict": retrieval["sourceConflict"],
        },
    )

    memory.track_event(
        event_type="evaluator_answered",
        client_id=session_row.get("user_identifier", ""),
        session_id=sessionId,
        display_name=session_row.get("display_name", ""),
        pathname="/",
            metadata={
                "provider": chosen_provider,
                "model": chosen_model,
                "questionId": answered.get("questionId", ""),
                "questionScore": answered.get("overallScore", 0),
                "currentScore": report["overallScore"] if updated_metadata.get("completed") else 0,
                "answeredQuestions": progress["answeredQuestions"],
                "stopReason": updated_metadata.get("stopReason", ""),
                "needsInfo": retrieval["needsInfo"],
                "retrievalGap": retrieval["retrievalGap"],
                "sourceConflict": retrieval["sourceConflict"],
            },
        )
    if upload_entry is not None:
        memory.track_event(
            event_type="file_uploaded",
            client_id=session_row.get("user_identifier", ""),
            session_id=sessionId,
            display_name=session_row.get("display_name", ""),
            pathname="/",
            metadata={
                "name": upload_entry.get("name"),
                "docType": upload_entry.get("docType"),
                "chunkCount": upload_entry.get("chunkCount"),
                "chars": upload_entry.get("chars"),
                "sessionType": "evaluator",
            },
        )
    if updated_metadata.get("completed"):
        memory.track_event(
            event_type="evaluator_completed",
            client_id=session_row.get("user_identifier", ""),
            session_id=sessionId,
            display_name=session_row.get("display_name", ""),
            pathname="/",
            metadata={
                "provider": chosen_provider,
                "model": chosen_model,
                "questionBudget": updated_metadata.get("maxQuestionsHidden", updated_metadata.get("questionBudget", 12)),
                "overallScore": report["overallScore"],
                "confidence": report.get("confidence", 0),
                "stopReason": report.get("stopReason", ""),
            },
        )

    return EvaluatorAnswerResponse(
        sessionId=sessionId,
        evaluatorMode="idea_review",
        evaluationProgress=progress,
        evaluationReport=report,
        deckEvaluationReport=None,
        reciprocal=answered.get("reciprocal", "Assessment updated."),
        question=None if updated_metadata.get("completed") else result.get("question"),
        questionLabel="",
        activeUploads=list_active_uploads(sessionId),
        warning=updated_metadata.get("website", {}).get("warning", ""),
        supportsVision=supports_vision,
        runtimeUsage=updated_metadata.get("runtimeUsage", _runtime_usage(updated_metadata)),
    )


@router.post("/{session_id}/deeper", response_model=EvaluatorAnswerResponse)
async def continue_deeper(
    session_id: str,
    clientId: str = "",
    x_sift_client_id: str = Header(default="", alias="x-sift-client-id"),
) -> EvaluatorAnswerResponse:
    session_row = memory.get_session(session_id)
    if session_row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    require_session_owner(session_row, x_sift_client_id or clientId)
    if session_row.get("session_type") != "evaluator":
        raise HTTPException(status_code=400, detail="This session is not an evaluator session")

    metadata = memory.get_session_metadata(session_row)
    if normalize_evaluator_mode(metadata.get("evaluatorMode")) == "deck_review":
        raise HTTPException(status_code=400, detail="Deck review does not use deeper question rounds")
    turns = memory.get_session_turns(session_id)
    state = _restore_state(session_row, turns)
    recent_user_context = " ".join(
        turn.get("content", "")
        for turn in turns[-4:]
        if turn.get("role") == "user"
    )
    retrieval = build_retrieval_context(
        session_id,
        state,
        f"{metadata.get('currentQuestionId', '')} {recent_user_context}".strip(),
        domain_focus=metadata.get("domainFocus", []),
        geography=getattr(state, "geography", metadata.get("geography", "unspecified")),
        assumptions_to_verify=metadata.get("assumptionsToVerify", []),
        answer_record=metadata.get("answerRecord"),
        session_context="\n\n".join(
            bit
            for bit in [
                str(metadata.get("setupContext", "")).strip(),
                (
                    metadata.get("website", {}).get("text", "").strip()
                    if isinstance(metadata.get("website"), dict)
                    else ""
                ),
            ]
            if bit
        ),
    )
    result = await continue_evaluation_deeper(
        state,
        metadata,
        provider=session_row.get("provider", "ollama"),
        model=session_row.get("model", ""),
        api_key=None,
        retrieval_context=retrieval["text"],
        needs_info=retrieval["needsInfo"],
        retrieval_gap=retrieval["retrievalGap"],
        source_conflict=retrieval["sourceConflict"],
    )
    updated_metadata = result["metadata"]
    report = result["report"]
    progress = public_progress(updated_metadata, state)
    question = result.get("question")
    answered = result.get("answered", {})

    assistant_content = answered.get("reciprocal", "Let's keep going.")
    if question:
        assistant_content = f"{assistant_content}\n\n{question['text']}"

    updated_state = update_state_from_turn(state, "", assistant_message=assistant_content)
    memory.update_session(session_id, updated_state)
    memory.update_session_metadata(session_id, updated_metadata)
    memory.store_turn(
        session_id,
        "assistant",
        assistant_content,
        metadata={
            "sessionType": "evaluator",
            "responseProfile": "speed",
            "state_snapshot": updated_state.to_dict(),
            "questionId": question.get("id", "") if question else "",
            "evaluation": answered,
            "needsInfo": retrieval["needsInfo"],
            "retrievalGap": retrieval["retrievalGap"],
            "sourceConflict": retrieval["sourceConflict"],
        },
    )
    memory.track_event(
        event_type="evaluator_deeper_started",
        client_id=session_row.get("user_identifier", ""),
        session_id=session_id,
        display_name=session_row.get("display_name", ""),
        pathname=f"/evaluate/{session_id}/report",
        metadata={
            "provider": session_row.get("provider", "ollama"),
            "model": session_row.get("model", ""),
            "remaining": updated_metadata.get("deeperQuestionsRemaining", 0),
        },
    )
    return EvaluatorAnswerResponse(
        sessionId=session_id,
        evaluatorMode="idea_review",
        evaluationProgress=progress,
        evaluationReport=report,
        deckEvaluationReport=None,
        reciprocal=answered.get("reciprocal", "Let's keep going."),
        question=question,
        questionLabel="",
        activeUploads=list_active_uploads(session_id),
        warning=updated_metadata.get("website", {}).get("warning", ""),
        supportsVision=model_supports_vision(session_row.get("provider", "ollama"), session_row.get("model", "")),
        runtimeUsage=updated_metadata.get("runtimeUsage", _runtime_usage(updated_metadata)),
    )


@router.get("/{session_id}/report", response_model=EvaluatorReportResponse)
async def get_report(
    session_id: str,
    clientId: str = "",
    x_sift_client_id: str = Header(default="", alias="x-sift-client-id"),
) -> EvaluatorReportResponse:
    session_row = memory.get_session(session_id)
    if session_row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    require_session_owner(session_row, x_sift_client_id or clientId)
    if session_row.get("session_type") != "evaluator":
        raise HTTPException(status_code=400, detail="This session is not an evaluator session")

    metadata = memory.get_session_metadata(session_row)
    turns = memory.get_session_turns(session_id)
    state = _restore_state(session_row, turns)
    evaluator_mode = normalize_evaluator_mode(metadata.get("evaluatorMode"))
    report = None
    deck_report = None
    if evaluator_mode == "deck_review":
        deck_report = present_deck_review_report(metadata)
    else:
        report = present_evaluation_report(metadata)
        if metadata.get("completed") and not has_cached_presentable_report(metadata, report):
            report = await naturalize_evaluation_report(
                report=report,
                metadata=metadata,
                state=state,
                provider=session_row.get("provider", "ollama"),
                model=session_row.get("model", ""),
                api_key=None,
            )
            memory.update_session_metadata(session_id, metadata)
    progress = public_progress(metadata, state)
    memory.track_event(
        event_type="evaluator_report_viewed",
        client_id=session_row.get("user_identifier", ""),
        session_id=session_id,
        display_name=session_row.get("display_name", ""),
        pathname=f"/evaluate/{session_id}/report",
        metadata={
            "provider": session_row.get("provider", "ollama"),
            "model": session_row.get("model", ""),
            "overallScore": (deck_report or report or {}).get("overallScore", 0),
            "evaluatorMode": evaluator_mode,
        },
    )
    return EvaluatorReportResponse(
        sessionId=session_id,
        evaluatorMode=evaluator_mode,
        evaluationReport=report,
        deckEvaluationReport=deck_report,
        evaluationProgress=progress,
        provider=session_row.get("provider", "ollama"),
        model=session_row.get("model", ""),
        supportsVision=model_supports_vision(session_row.get("provider", "ollama"), session_row.get("model", "")),
        websiteUrl=session_row.get("website_url", ""),
        runtimeUsage=metadata.get("runtimeUsage", _runtime_usage(metadata)),
    )
