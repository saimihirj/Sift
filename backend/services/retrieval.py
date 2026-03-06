"""Context assembly for the chat runtime."""

from __future__ import annotations

from state import ConversationState

from backend.services.external_sources import retrieve_external_research_context
from backend.services.prompting import get_sector_prompt_snippet
from backend.services.uploads import retrieve_upload_context


def build_retrieval_context(session_id: str, state: ConversationState, query: str) -> dict:
    parts = []
    sector_snippet = get_sector_prompt_snippet(state.sector)
    if sector_snippet:
        parts.append(f"Sector lens:\n{sector_snippet}")

    external_research = retrieve_external_research_context(state, query=query, top_k=2, max_chars=560)
    if external_research["text"]:
        parts.append(external_research["text"])

    upload_snippets = retrieve_upload_context(session_id, query=query, top_k=2, max_chars=1200)
    if upload_snippets:
        formatted = []
        for snippet in upload_snippets:
            formatted.append(
                f"[{snippet['source']} · {snippet['docType']}]\n{snippet['text']}"
            )
        parts.append("Uploaded context:\n" + "\n\n".join(formatted))

    context_text = "\n\n".join(parts)
    return {
        "text": context_text,
        "sectorSnippet": sector_snippet,
        "researchSources": external_research["sources"],
        "uploadSnippets": upload_snippets,
        "promptChars": len(context_text),
    }
