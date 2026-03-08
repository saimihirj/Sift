"""Streaming chat endpoint."""

from __future__ import annotations

import json
import time
from typing import AsyncIterator

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

import memory
from state import ConversationState

from backend.services.model_router import default_model_for_provider, normalize_provider, stream_chat_completion
from backend.services.prompting import (
    DEFAULT_RESPONSE_PROFILE,
    build_system_prompt,
    derive_mentor_turn_metadata,
    get_chip_suggestions,
)
from backend.services.retrieval import build_retrieval_context
from backend.services.state_engine import coverage_items, next_gap, update_state_from_turn
from backend.services.uploads import ingest_upload, list_active_uploads


router = APIRouter(prefix="/api/chat", tags=["chat"])


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
            "company_name": session_row.get("company_name", ""),
        }
    )


@router.post("")
async def chat(
    sessionId: str = Form(...),
    message: str = Form(""),
    responseProfile: str = Form(DEFAULT_RESPONSE_PROFILE),
    provider: str = Form(""),
    model: str = Form(""),
    apiKey: str = Form(""),
    file: UploadFile | None = File(default=None),
) -> StreamingResponse:
    session_row = memory.get_session(sessionId)
    if session_row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if not (message or "").strip() and file is None:
        raise HTTPException(status_code=400, detail="Message or file is required")

    turns = memory.get_session_turns(sessionId)
    restored_state = _restore_state(turns, session_row)
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

            history_window = [
                {"role": turn["role"], "content": turn["content"]}
                for turn in turns
                if turn["role"] in ("user", "assistant")
            ][-6:]

            query = user_message
            if history_window:
                query = f"{history_window[-1]['content']} {user_message}".strip()
            current_state = restored_state
            retrieval = build_retrieval_context(sessionId, current_state, query)
            conversation_metadata = derive_mentor_turn_metadata(
                current_state,
                user_message,
                [turn["content"] for turn in history_window if turn["role"] == "assistant"],
                needs_info=retrieval["needsInfo"],
                retrieval_gap=retrieval["retrievalGap"],
                source_conflict=retrieval["sourceConflict"],
            )
            system_prompt = build_system_prompt(
                current_state,
                retrieval_context=retrieval["text"],
                last_user_message=user_message,
                recent_assistant_turns=[turn["content"] for turn in history_window if turn["role"] == "assistant"],
                needs_info=retrieval["needsInfo"],
                retrieval_gap=retrieval["retrievalGap"],
                source_conflict=retrieval["sourceConflict"],
            )
            active_uploads = list_active_uploads(sessionId)

            assistant_chunks: list[str] = []
            completion_payload = None
            async for event, payload in stream_chat_completion(
                system=system_prompt,
                messages=[*history_window, {"role": "user", "content": user_message}],
                response_profile=responseProfile,
                provider_override=chosen_provider,
                model_override=chosen_model,
                api_key=api_key,
            ):
                if event == "meta":
                    payload["activeUploads"] = active_uploads
                    payload["retrievalChars"] = retrieval["promptChars"]
                    payload["researchSources"] = retrieval["researchSources"]
                    yield _sse("meta", payload)
                elif event == "delta":
                    assistant_chunks.append(payload["delta"])
                    yield _sse("delta", payload)
                elif event == "complete":
                    completion_payload = payload

            if completion_payload is None:
                raise RuntimeError("Model did not produce a completion")

            assistant_message = completion_payload["message"].strip()
            current_state = update_state_from_turn(current_state, user_message, assistant_message=assistant_message)
            total_seconds = round(time.perf_counter() - started_at, 3)

            user_metadata = {
                "responseProfileRequested": responseProfile,
                "provider": chosen_provider,
                "model": chosen_model,
                "upload": upload_entry,
                "retrievalChars": retrieval["promptChars"],
                "researchSources": retrieval["researchSources"],
                "needsInfo": retrieval["needsInfo"],
                "retrievalGap": retrieval["retrievalGap"],
                "sourceConflict": retrieval["sourceConflict"],
            }
            assistant_metadata = {
                "responseProfile": completion_payload["responseProfile"],
                "model": completion_payload["model"],
                "provider": completion_payload.get("provider", chosen_provider),
                "fallbackUsed": completion_payload.get("fallbackUsed", False),
                "timings": {
                    **completion_payload["timings"],
                    "totalBackendSeconds": total_seconds,
                },
                "activeUploads": active_uploads,
                "researchSources": retrieval["researchSources"],
                "state_snapshot": current_state.to_dict(),
                **conversation_metadata,
            }

            memory.store_turn(sessionId, "user", display_message, metadata=user_metadata)
            memory.store_turn(sessionId, "assistant", assistant_message, metadata=assistant_metadata)
            memory.update_session(sessionId, current_state)
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
                },
            )

            yield _sse(
                "done",
                {
                    "message": assistant_message,
                    "state": current_state.to_dict(),
                    "chips": get_chip_suggestions(current_state, assistant_message),
                    "coverage": coverage_items(current_state),
                    "nextGap": next_gap(current_state),
                    "responseProfile": completion_payload["responseProfile"],
                    "provider": completion_payload.get("provider", chosen_provider),
                    "model": completion_payload["model"],
                    "timings": assistant_metadata["timings"],
                    "fallbackUsed": completion_payload.get("fallbackUsed", False),
                    "activeUploads": active_uploads,
                },
            )
        except Exception as exc:
            yield _sse("error", {"message": repr(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
