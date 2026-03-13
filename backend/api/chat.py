"""Streaming chat endpoint."""

from __future__ import annotations

import json
import re
import time
from typing import AsyncIterator

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

import memory
from state import ConversationState

from backend.services.expert_agent import (
    build_analysis_snapshot,
    build_expert_retrieval_context,
    build_expert_system_prompt,
    classify_expert_turn,
    get_expert_quick_actions,
)
from backend.services.model_router import default_model_for_provider, normalize_provider, stream_chat_completion
from backend.services.prompting import (
    DEFAULT_RESPONSE_PROFILE,
    build_system_prompt,
    derive_mentor_turn_metadata,
    get_chip_suggestions,
)
from backend.services.refinement import empty_answer_record, refine_founder_input, update_answer_record
from backend.services.retrieval import build_retrieval_context
from backend.services.state_engine import coverage_items, next_gap, update_state_from_turn
from backend.services.uploads import ingest_upload, list_active_uploads


router = APIRouter(prefix="/api/chat", tags=["chat"])

MAX_HISTORY_MESSAGES = 4
MAX_HISTORY_MESSAGE_CHARS = 320
MAX_HISTORY_TOTAL_CHARS = 1100
STABLE_WORKFLOW_TOTAL_CHARS = 4800
STABLE_WORKFLOW_PROMPT_CHARS = 3800
MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
MARKDOWN_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
MARKDOWN_UNDERLINE_RE = re.compile(r"__(.+?)__")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


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
            "geography": session_row.get("geography", "unspecified"),
            "company_name": session_row.get("company_name", ""),
        }
    )


def _active_session_context(metadata: dict) -> str:
    website = metadata.get("website", {})
    website_text = website.get("text", "").strip() if isinstance(website, dict) else ""
    return "\n\n".join(
        bit
        for bit in [
            str(metadata.get("setupContext", "")).strip(),
            website_text,
        ]
        if bit
    )


def _trim_text(text: str, max_chars: int) -> str:
    value = (text or "").strip()
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + "..."


def _compact_history(turns: list[dict]) -> list[dict[str, str]]:
    history = [
        {"role": turn["role"], "content": _trim_text(turn["content"], MAX_HISTORY_MESSAGE_CHARS)}
        for turn in turns
        if turn["role"] in ("user", "assistant")
    ][-MAX_HISTORY_MESSAGES:]
    total = sum(len(item["content"]) for item in history)
    if total <= MAX_HISTORY_TOTAL_CHARS:
        return history

    compacted: list[dict[str, str]] = []
    remaining = MAX_HISTORY_TOTAL_CHARS
    for item in reversed(history):
        allowance = max(120, remaining // max(len(history) - len(compacted), 1))
        text = _trim_text(item["content"], allowance)
        compacted.append({"role": item["role"], "content": text})
        remaining -= len(text)
        if remaining <= 0:
            break
    return list(reversed(compacted))


def _runtime_health(metadata: dict) -> dict:
    health = metadata.get("runtimeHealth")
    if not isinstance(health, dict):
        health = {}
    return {
        "readTimeouts": int(health.get("readTimeouts", 0) or 0),
        "slowTurns": int(health.get("slowTurns", 0) or 0),
    }


def _should_use_stable_workflow(provider: str, metadata: dict, *, total_chars: int = 0, prompt_chars: int = 0) -> bool:
    if normalize_provider(provider) != "ollama":
        return bool(metadata.get("stableWorkflow"))
    if metadata.get("stableWorkflow"):
        return True
    health = _runtime_health(metadata)
    if health["readTimeouts"] > 0 or health["slowTurns"] >= 2:
        return True
    return total_chars >= STABLE_WORKFLOW_TOTAL_CHARS or prompt_chars >= STABLE_WORKFLOW_PROMPT_CHARS


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


def _normalize_assistant_output(text: str) -> str:
    value = (text or "").strip()
    value = MARKDOWN_HEADING_RE.sub("", value)
    value = MARKDOWN_BOLD_RE.sub(r"\1", value)
    value = MARKDOWN_UNDERLINE_RE.sub(r"\1", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _stream_limits(session_type: str, *, has_upload: bool = False) -> tuple[int, float]:
    if session_type == "expert":
        if has_upload:
            return 1200, 85.0
        return 900, 70.0
    if has_upload:
        return 680, 60.0
    return 520, 45.0


@router.post("")
async def chat(
    sessionId: str = Form(...),
    message: str = Form(""),
    responseProfile: str = Form(DEFAULT_RESPONSE_PROFILE),
    provider: str = Form(""),
    model: str = Form(""),
    apiKey: str = Form(""),
    helpMode: str = Form(""),
    liveWebEnabled: bool = Form(False),
    file: UploadFile | None = File(default=None),
) -> StreamingResponse:
    session_row = memory.get_session(sessionId)
    if session_row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if not (message or "").strip() and file is None:
        raise HTTPException(status_code=400, detail="Message or file is required")

    turns = memory.get_session_turns(sessionId)
    restored_state = _restore_state(turns, session_row)
    session_metadata = memory.get_session_metadata(session_row)
    session_metadata["answerRecord"] = session_metadata.get("answerRecord") or empty_answer_record()
    session_metadata["assumptionsToVerify"] = list(session_metadata.get("assumptionsToVerify", []))
    session_metadata["domainFocus"] = list(session_metadata.get("domainFocus", []))
    session_type = session_row.get("session_type", "mentor")
    session_metadata["helpMode"] = (helpMode or session_metadata.get("helpMode", "coach_me") or "coach_me").strip() or "coach_me"
    session_metadata["liveWebEnabled"] = True if session_type == "expert" else bool(liveWebEnabled)
    chosen_provider = normalize_provider(provider or session_row.get("provider", "ollama"))
    chosen_model = (model or session_row.get("model", "")).strip() or default_model_for_provider(chosen_provider, responseProfile)
    api_key = (apiKey or "").strip() or None

    if chosen_provider != session_row.get("provider", "ollama") or chosen_model != (session_row.get("model", "") or ""):
        memory.update_session_runtime(sessionId, chosen_provider, chosen_model)
        session_row["provider"] = chosen_provider
        session_row["model"] = chosen_model

    async def event_stream() -> AsyncIterator[str]:
        started_at = time.perf_counter()
        upload_entry = None
        try:
            if file is not None:
                upload_entry = await ingest_upload(sessionId, file)

            user_message = (message or "").strip()
            display_message = user_message
            if not user_message:
                file_label = upload_entry["name"] if upload_entry else "document"
                user_message = f"I uploaded {file_label}. React to the strongest signal in it and ask the next sharp question."
                display_message = f"[Attached {file_label}]"
            elif upload_entry is not None:
                display_message = f"{user_message}\n\n[Attached {upload_entry['name']}]"

            history_window = _compact_history(turns)

            recent_user_context = " ".join(turn["content"] for turn in history_window if turn["role"] == "user")
            query = " ".join(bit for bit in [recent_user_context, user_message] if bit).strip()
            current_state = restored_state
            refinement = {
                "domainFocus": [],
                "assumptionsToVerify": [],
                "evidenceStatus": "unknown",
            }
            route = {}
            analysis_snapshot = _empty_analysis_snapshot()
            if session_type == "expert":
                route = classify_expert_turn(
                    user_message,
                    has_upload=upload_entry is not None,
                    help_mode=session_metadata.get("helpMode", "coach_me"),
                )
                session_metadata["domainFocus"] = [route.get("knowledgeLane", "startup")]
                session_metadata["knowledgeLane"] = route.get("knowledgeLane", "startup")
                session_metadata["followUpMode"] = route.get("followUpMode", "answer_then_probe")
                session_metadata["usedLiveWeb"] = False
                retrieval = build_expert_retrieval_context(
                    sessionId,
                    query,
                    route=route,
                    geography=session_metadata.get("geographyMode", current_state.geography or "auto"),
                    live_web_enabled=True,
                )
                analysis_snapshot = build_analysis_snapshot(
                    query=query,
                    route=route,
                    retrieval=retrieval,
                )
                session_metadata.update(
                    {
                        "sources": retrieval["sources"],
                        "confidence": retrieval["confidence"],
                        "knowledgeLane": retrieval["knowledgeLane"],
                        "usedLiveWeb": retrieval["usedLiveWeb"],
                        "followUpMode": route.get("followUpMode", ""),
                        "activeAnalysis": analysis_snapshot,
                    }
                )
                conversation_metadata = {
                    "conversationMove": route.get("action", "open_discussion"),
                    "needsInfo": retrieval["needsInfo"],
                    "retrievalGap": retrieval["retrievalGap"],
                    "sourceConflict": retrieval["sourceConflict"],
                    "domainFocus": session_metadata.get("domainFocus", []),
                    "assumptionsToVerify": [],
                    "answerRecordSummary": "",
                    "lastQuestionStem": "",
                    "lastMoveType": route.get("action", "open_discussion"),
                    "lastReflectionUsed": "",
                    "knowledgeLane": retrieval["knowledgeLane"],
                    "followUpMode": route.get("followUpMode", ""),
                    "helpMode": session_metadata.get("helpMode", "coach_me"),
                    "usedLiveWeb": retrieval["usedLiveWeb"],
                    "confidence": retrieval["confidence"],
                    "sources": retrieval["sources"],
                    "activeAnalysis": analysis_snapshot,
                }
                system_prompt = build_expert_system_prompt(
                    state=current_state,
                    user_message=user_message,
                    route=route,
                    retrieval_context=retrieval["text"],
                    help_mode=session_metadata.get("helpMode", "coach_me"),
                    analysis_snapshot=analysis_snapshot,
                    stable_workflow=False,
                )
            else:
                refinement = refine_founder_input(
                    user_message,
                    state=current_state,
                    recent_history=[turn["content"] for turn in history_window],
                )
                merged_assumptions = list(session_metadata.get("assumptionsToVerify", []))
                for item in refinement["assumptionsToVerify"]:
                    if item not in merged_assumptions:
                        merged_assumptions.append(item)
                session_metadata["domainFocus"] = refinement["domainFocus"]
                session_metadata["assumptionsToVerify"] = merged_assumptions[:5]
                session_metadata["answerRecord"] = update_answer_record(
                    session_metadata.get("answerRecord"),
                    user_message,
                    refinement["domainFocus"],
                    source="founder",
                    evidence_status=refinement["evidenceStatus"],
                    assumptions=refinement["assumptionsToVerify"],
                )
                session_context = _active_session_context(session_metadata)
                retrieval = build_retrieval_context(
                    sessionId,
                    current_state,
                    query,
                    domain_focus=session_metadata.get("domainFocus", []),
                    geography=current_state.geography,
                    assumptions_to_verify=session_metadata.get("assumptionsToVerify", []),
                    answer_record=session_metadata.get("answerRecord"),
                    session_context=session_context,
                )
                conversation_metadata = derive_mentor_turn_metadata(
                    current_state,
                    user_message,
                    [turn["content"] for turn in history_window if turn["role"] == "assistant"],
                    needs_info=retrieval["needsInfo"],
                    retrieval_gap=retrieval["retrievalGap"],
                    source_conflict=retrieval["sourceConflict"],
                    domain_focus=session_metadata.get("domainFocus", []),
                    assumptions_to_verify=session_metadata.get("assumptionsToVerify", []),
                    answer_record=session_metadata.get("answerRecord"),
                )
                system_prompt = build_system_prompt(
                    current_state,
                    retrieval_context=retrieval["text"],
                    last_user_message=user_message,
                    recent_assistant_turns=[turn["content"] for turn in history_window if turn["role"] == "assistant"],
                    needs_info=retrieval["needsInfo"],
                    retrieval_gap=retrieval["retrievalGap"],
                    source_conflict=retrieval["sourceConflict"],
                    domain_focus=session_metadata.get("domainFocus", []),
                    assumptions_to_verify=session_metadata.get("assumptionsToVerify", []),
                    answer_record=session_metadata.get("answerRecord"),
                    stable_workflow=False,
                )
            history_chars = sum(len(turn["content"]) for turn in history_window)
            stable_workflow = _should_use_stable_workflow(
                chosen_provider,
                session_metadata,
                total_chars=history_chars + retrieval["promptChars"],
            )
            if session_type == "expert":
                system_prompt = build_expert_system_prompt(
                    state=current_state,
                    user_message=user_message,
                    route=route,
                    retrieval_context=retrieval["text"],
                    help_mode=session_metadata.get("helpMode", "coach_me"),
                    analysis_snapshot=analysis_snapshot,
                    stable_workflow=stable_workflow,
                )
            else:
                system_prompt = build_system_prompt(
                    current_state,
                    retrieval_context=retrieval["text"],
                    last_user_message=user_message,
                    recent_assistant_turns=[turn["content"] for turn in history_window if turn["role"] == "assistant"],
                    needs_info=retrieval["needsInfo"],
                    retrieval_gap=retrieval["retrievalGap"],
                    source_conflict=retrieval["sourceConflict"],
                    domain_focus=session_metadata.get("domainFocus", []),
                    assumptions_to_verify=session_metadata.get("assumptionsToVerify", []),
                    answer_record=session_metadata.get("answerRecord"),
                    stable_workflow=stable_workflow,
                )
            active_uploads = list_active_uploads(sessionId)
            system_prompt_chars = len(system_prompt)
            total_send_chars = history_chars + system_prompt_chars
            if not stable_workflow and _should_use_stable_workflow(
                chosen_provider,
                session_metadata,
                total_chars=total_send_chars,
                prompt_chars=system_prompt_chars,
            ):
                stable_workflow = True
                if session_type == "expert":
                    system_prompt = build_expert_system_prompt(
                        state=current_state,
                        user_message=user_message,
                        route=route,
                        retrieval_context=retrieval["text"],
                        help_mode=session_metadata.get("helpMode", "coach_me"),
                        analysis_snapshot=analysis_snapshot,
                        stable_workflow=True,
                    )
                else:
                    system_prompt = build_system_prompt(
                        current_state,
                        retrieval_context=retrieval["text"],
                        last_user_message=user_message,
                        recent_assistant_turns=[turn["content"] for turn in history_window if turn["role"] == "assistant"],
                        needs_info=retrieval["needsInfo"],
                        retrieval_gap=retrieval["retrievalGap"],
                        source_conflict=retrieval["sourceConflict"],
                        domain_focus=session_metadata.get("domainFocus", []),
                        assumptions_to_verify=session_metadata.get("assumptionsToVerify", []),
                        answer_record=session_metadata.get("answerRecord"),
                        stable_workflow=True,
                    )
                system_prompt_chars = len(system_prompt)
                total_send_chars = history_chars + system_prompt_chars
            if stable_workflow and not session_metadata.get("stableWorkflow"):
                session_metadata["stableWorkflow"] = True

            assistant_chunks: list[str] = []
            completion_payload = None
            max_output_tokens, output_timeout = _stream_limits(session_type, has_upload=upload_entry is not None)
            async for event, payload in stream_chat_completion(
                system=system_prompt,
                messages=[*history_window, {"role": "user", "content": user_message}],
                response_profile=responseProfile,
                provider_override=chosen_provider,
                model_override=chosen_model,
                api_key=api_key,
                max_tokens_override=max_output_tokens,
                timeout_seconds_override=output_timeout,
                allow_continuation=session_type == "expert" or upload_entry is not None,
                continuation_limit=1,
            ):
                if event == "meta":
                    payload["activeUploads"] = active_uploads
                    payload["retrievalChars"] = retrieval["promptChars"]
                    payload["historyChars"] = history_chars
                    payload["systemPromptChars"] = system_prompt_chars
                    payload["stableWorkflow"] = stable_workflow
                    payload["researchSources"] = retrieval.get("researchSources", [])
                    payload["sources"] = session_metadata.get("sources", [])
                    payload["confidence"] = session_metadata.get("confidence", 0.0)
                    payload["knowledgeLane"] = session_metadata.get("knowledgeLane", "general")
                    payload["usedLiveWeb"] = session_metadata.get("usedLiveWeb", False)
                    payload["followUpMode"] = session_metadata.get("followUpMode", "")
                    payload["helpMode"] = session_metadata.get("helpMode", "coach_me")
                    payload["liveWebEnabled"] = session_metadata.get("liveWebEnabled", False)
                    payload["analysisSnapshot"] = session_metadata.get("activeAnalysis", _empty_analysis_snapshot())
                    yield _sse("meta", payload)
                elif event == "delta":
                    assistant_chunks.append(payload["delta"])
                    yield _sse("delta", payload)
                elif event == "complete":
                    completion_payload = payload

            if completion_payload is None:
                raise RuntimeError("Model did not produce a completion")

            assistant_message = _normalize_assistant_output(completion_payload["message"])
            current_state = update_state_from_turn(current_state, user_message, assistant_message=assistant_message)
            total_seconds = round(time.perf_counter() - started_at, 3)

            user_metadata = {
                "responseProfileRequested": responseProfile,
                "provider": chosen_provider,
                "model": chosen_model,
                "sessionType": session_type,
                "upload": upload_entry,
                "retrievalChars": retrieval["promptChars"],
                "historyChars": history_chars,
                "systemPromptChars": system_prompt_chars,
                "stableWorkflow": stable_workflow,
                "researchSources": retrieval.get("researchSources", []),
                "needsInfo": retrieval["needsInfo"],
                "retrievalGap": retrieval["retrievalGap"],
                "sourceConflict": retrieval["sourceConflict"],
                "domainFocus": session_metadata.get("domainFocus", []),
                "assumptionsToVerify": session_metadata.get("assumptionsToVerify", []),
                "evidenceStatus": refinement["evidenceStatus"],
                "knowledgeLane": session_metadata.get("knowledgeLane", "general"),
                "helpMode": session_metadata.get("helpMode", "coach_me"),
                "usedLiveWeb": session_metadata.get("usedLiveWeb", False),
                "finishReason": completion_payload.get("finishReason", "stop"),
                "continuedAfterLengthLimit": completion_payload.get("continuedAfterLengthLimit", False),
                "continuationCount": completion_payload.get("continuationCount", 0),
            }
            assistant_metadata = {
                "responseProfile": completion_payload["responseProfile"],
                "model": completion_payload["model"],
                "provider": completion_payload.get("provider", chosen_provider),
                "sessionType": session_type,
                "fallbackUsed": completion_payload.get("fallbackUsed", False),
                "timings": {
                    **completion_payload["timings"],
                    "totalBackendSeconds": total_seconds,
                },
                "finishReason": completion_payload.get("finishReason", "stop"),
                "continuedAfterLengthLimit": completion_payload.get("continuedAfterLengthLimit", False),
                "continuationCount": completion_payload.get("continuationCount", 0),
                "activeUploads": active_uploads,
                "researchSources": retrieval.get("researchSources", []),
                "historyChars": history_chars,
                "systemPromptChars": system_prompt_chars,
                "stableWorkflow": stable_workflow,
                "state_snapshot": current_state.to_dict(),
                **conversation_metadata,
            }

            runtime_health = _runtime_health(session_metadata)
            if completion_payload.get("fallbackUsed", False):
                session_metadata["stableWorkflow"] = True
                runtime_health["slowTurns"] += 1
            if assistant_metadata["timings"].get("firstTokenSeconds", 0) >= 6 or assistant_metadata["timings"].get("totalSeconds", 0) >= 18:
                runtime_health["slowTurns"] += 1
            session_metadata["runtimeHealth"] = runtime_health
            session_metadata.update(
                {
                    "conversationMove": conversation_metadata.get("conversationMove", ""),
                    "needsInfo": retrieval["needsInfo"],
                    "retrievalGap": retrieval["retrievalGap"],
                    "sourceConflict": retrieval["sourceConflict"],
                    "lastQuestionStem": conversation_metadata.get("lastQuestionStem", ""),
                    "lastMoveType": conversation_metadata.get("lastMoveType", ""),
                    "lastReflectionUsed": conversation_metadata.get("lastReflectionUsed", ""),
                    "stableWorkflow": bool(session_metadata.get("stableWorkflow")),
                }
            )

            memory.store_turn(sessionId, "user", display_message, metadata=user_metadata)
            memory.store_turn(sessionId, "assistant", assistant_message, metadata=assistant_metadata)
            memory.update_session(sessionId, current_state)
            memory.update_session_metadata(sessionId, session_metadata)
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
                    },
                )
            memory.track_event(
                event_type="chat_completed",
                client_id=session_row.get("user_identifier", ""),
                session_id=sessionId,
                display_name=session_row.get("display_name", ""),
                pathname="/",
                metadata={
                    "responseProfile": completion_payload["responseProfile"],
                    "provider": completion_payload.get("provider", chosen_provider),
                    "model": completion_payload["model"],
                    "fallbackUsed": completion_payload.get("fallbackUsed", False),
                    "firstTokenSeconds": assistant_metadata["timings"].get("firstTokenSeconds", 0),
                    "totalSeconds": assistant_metadata["timings"].get("totalSeconds", 0),
                    "totalBackendSeconds": total_seconds,
                    "hadUpload": upload_entry is not None,
                    "historyChars": history_chars,
                    "systemPromptChars": system_prompt_chars,
                    "retrievalChars": retrieval["promptChars"],
                    "stableWorkflow": bool(session_metadata.get("stableWorkflow")),
                    "sessionType": session_type,
                    "knowledgeLane": session_metadata.get("knowledgeLane", "general"),
                    "usedLiveWeb": session_metadata.get("usedLiveWeb", False),
                    "finishReason": completion_payload.get("finishReason", "stop"),
                    "continuedAfterLengthLimit": completion_payload.get("continuedAfterLengthLimit", False),
                    "continuationCount": completion_payload.get("continuationCount", 0),
                },
            )

            yield _sse(
                "done",
                {
                    "message": assistant_message,
                    "state": current_state.to_dict(),
                    "chips": get_expert_quick_actions() if session_type == "expert" else get_chip_suggestions(current_state, assistant_message),
                    "coverage": coverage_items(current_state),
                    "nextGap": next_gap(current_state),
                    "responseProfile": completion_payload["responseProfile"],
                    "provider": completion_payload.get("provider", chosen_provider),
                    "model": completion_payload["model"],
                    "timings": assistant_metadata["timings"],
                    "fallbackUsed": completion_payload.get("fallbackUsed", False),
                    "finishReason": completion_payload.get("finishReason", "stop"),
                    "continuedAfterLengthLimit": completion_payload.get("continuedAfterLengthLimit", False),
                    "continuationCount": completion_payload.get("continuationCount", 0),
                    "activeUploads": active_uploads,
                    "historyChars": history_chars,
                    "systemPromptChars": system_prompt_chars,
                    "retrievalChars": retrieval["promptChars"],
                    "stableWorkflow": bool(session_metadata.get("stableWorkflow")),
                    "sources": session_metadata.get("sources", []),
                    "confidence": session_metadata.get("confidence", 0.0),
                    "knowledgeLane": session_metadata.get("knowledgeLane", "general"),
                    "usedLiveWeb": session_metadata.get("usedLiveWeb", False),
                    "followUpMode": session_metadata.get("followUpMode", ""),
                    "helpMode": session_metadata.get("helpMode", "coach_me"),
                    "liveWebEnabled": session_metadata.get("liveWebEnabled", False),
                    "analysisSnapshot": session_metadata.get("activeAnalysis", _empty_analysis_snapshot()),
                },
            )
        except httpx.ReadTimeout:
            session_metadata["stableWorkflow"] = True
            runtime_health = _runtime_health(session_metadata)
            runtime_health["readTimeouts"] += 1
            session_metadata["runtimeHealth"] = runtime_health
            memory.update_session_metadata(sessionId, session_metadata)
            yield _sse(
                "error",
                {
                    "message": "The local model took too long to respond. SignalX will use the simpler stable workflow on the next turn.",
                },
            )
        except Exception as exc:
            yield _sse("error", {"message": repr(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
