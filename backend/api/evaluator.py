"""Adaptive evaluator endpoints."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

import memory
from state import ConversationState

from backend.schemas import EvaluatorAnswerResponse, EvaluatorReportResponse
from backend.services.evaluator import build_evaluation_report, evaluate_answer, public_progress
from backend.services.model_router import default_model_for_provider, normalize_provider
from backend.services.state_engine import update_state_from_turn
from backend.services.uploads import ingest_upload, list_active_uploads, retrieve_upload_context


router = APIRouter(prefix="/api/evaluator", tags=["evaluator"])


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
            "company_name": session_row.get("company_name", ""),
        }
    )


@router.post("/answer", response_model=EvaluatorAnswerResponse)
async def answer_question(
    sessionId: str = Form(...),
    answer: str = Form(""),
    provider: str = Form(""),
    model: str = Form(""),
    apiKey: str = Form(""),
    file: UploadFile | None = File(default=None),
) -> EvaluatorAnswerResponse:
    session_row = memory.get_session(sessionId)
    if session_row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_row.get("session_type") != "evaluator":
        raise HTTPException(status_code=400, detail="This session is not an evaluator session")

    metadata = memory.get_session_metadata(session_row)
    if metadata.get("completed"):
        raise HTTPException(status_code=400, detail="This evaluator is already complete")

    chosen_provider = normalize_provider(provider or session_row.get("provider", "ollama"))
    chosen_model = (model or session_row.get("model", "")).strip() or default_model_for_provider(chosen_provider)
    if chosen_provider != session_row.get("provider", "ollama") or chosen_model != (session_row.get("model", "") or ""):
        memory.update_session_runtime(sessionId, chosen_provider, chosen_model)
        session_row["provider"] = chosen_provider
        session_row["model"] = chosen_model

    upload_entry = None
    if file is not None:
        upload_entry = await ingest_upload(sessionId, file)

    turns = memory.get_session_turns(sessionId)
    state = _restore_state(session_row, turns)
    if not answer.strip() and upload_entry is None:
        raise HTTPException(status_code=400, detail="Answer or file is required")

    answer_text = answer.strip()
    if not answer_text and upload_entry is not None:
        answer_text = f"I uploaded {upload_entry['name']}. Use it to assess my answer quality."

    upload_context_items = retrieve_upload_context(
        sessionId,
        query=f"{metadata.get('currentQuestionId', '')} {answer_text}",
        top_k=2,
        max_chars=900,
    )
    upload_context = "\n\n".join(item["text"] for item in upload_context_items)

    result = await evaluate_answer(
        state=state,
        metadata=metadata,
        answer=answer_text,
        provider=chosen_provider,
        model=chosen_model,
        api_key=apiKey or None,
        upload_context=upload_context,
    )

    updated_metadata = result["metadata"]
    answered = result.get("answered", {})
    report = result["report"]
    progress = public_progress(updated_metadata)

    assistant_content = answered.get("reciprocal", "Assessment updated.")
    question_label = answered.get("questionLabel", "")
    if result.get("question"):
        if not question_label:
            question_label = f"Question {progress['answeredQuestions'] + 1}"
            if progress["answeredQuestions"] == 0:
                question_label = "First question"
            elif progress["questionBudget"] - progress["answeredQuestions"] <= 1:
                question_label = "Final question"
        assistant_content = f"{assistant_content}\n\n{question_label}: {result['question']['text']}"
    elif updated_metadata.get("completed"):
        assistant_content = f"{assistant_content}\n\nThat is enough. Let me evaluate the idea and build the report."

    updated_state = update_state_from_turn(state, answer_text, assistant_message=assistant_content)
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
                "questionBudget": updated_metadata.get("questionBudget", 15),
                "overallScore": report["overallScore"],
            },
        )

    return EvaluatorAnswerResponse(
        sessionId=sessionId,
        evaluationProgress=progress,
        evaluationReport=report,
        reciprocal=answered.get("reciprocal", "Assessment updated."),
        question=result.get("question"),
        questionLabel=question_label,
        activeUploads=list_active_uploads(sessionId),
        warning=updated_metadata.get("website", {}).get("warning", ""),
    )


@router.get("/{session_id}/report", response_model=EvaluatorReportResponse)
async def get_report(session_id: str) -> EvaluatorReportResponse:
    session_row = memory.get_session(session_id)
    if session_row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_row.get("session_type") != "evaluator":
        raise HTTPException(status_code=400, detail="This session is not an evaluator session")

    metadata = memory.get_session_metadata(session_row)
    report = build_evaluation_report(metadata)
    progress = public_progress(metadata)
    memory.track_event(
        event_type="evaluator_report_viewed",
        client_id=session_row.get("user_identifier", ""),
        session_id=session_id,
        display_name=session_row.get("display_name", ""),
        pathname=f"/evaluate/{session_id}/report",
        metadata={
            "provider": session_row.get("provider", "ollama"),
            "model": session_row.get("model", ""),
            "overallScore": report["overallScore"],
        },
    )
    return EvaluatorReportResponse(
        sessionId=session_id,
        evaluationReport=report,
        evaluationProgress=progress,
        provider=session_row.get("provider", "ollama"),
        model=session_row.get("model", ""),
        websiteUrl=session_row.get("website_url", ""),
    )
