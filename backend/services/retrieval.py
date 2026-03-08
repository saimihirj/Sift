"""Context assembly for the chat and evaluator runtime."""

from __future__ import annotations

from state import ConversationState

from backend.services.external_sources import retrieve_external_research_context
from backend.services.prompting import get_sector_prompt_snippet
from backend.services.refinement import summarize_answer_record
from backend.services.uploads import retrieve_upload_context
from backend.services.vc_firm_knowledge import retrieve_vc_firm_context


NEEDS_KEYWORDS: dict[str, tuple[str, ...]] = {
    "problem and users": (
        "user",
        "customer",
        "buyer",
        "team",
        "desk",
        "segment",
        "who is this for",
        "who has this problem",
        "problem",
        "pain",
        "freeze",
        "stuck",
        "error",
    ),
    "pain and workflow": (
        "workflow",
        "manual",
        "today",
        "current workaround",
        "process",
        "friction",
        "painful",
        "annoying",
        "unacceptable",
    ),
    "current workaround": (
        "today",
        "currently",
        "without you",
        "alternative",
        "competitor",
        "status quo",
        "spreadsheet",
        "excel",
        "email",
    ),
    "solution and value": (
        "solution",
        "product",
        "feature",
        "value",
        "outcome",
        "result",
        "benefit",
        "why it matters",
    ),
    "proof and experiments": (
        "proof",
        "pilot",
        "test",
        "prototype",
        "pretotype",
        "experiment",
        "interview",
        "validation",
        "traction",
        "usage",
    ),
    "constraints and risks": (
        "risk",
        "constraint",
        "compliance",
        "legal",
        "security",
        "governance",
        "blocker",
        "hard part",
    ),
    "pricing and willingness to pay": (
        "pricing",
        "pay",
        "paid",
        "revenue",
        "margin",
        "cost",
        "unit economics",
        "business model",
    ),
}

INVESTOR_QUERY_TERMS = (
    "investor",
    "vc",
    "fundraise",
    "fundraising",
    "fund",
    "seed",
    "series a",
    "series b",
    "antler",
    "yc",
    "accelerator",
)

CONFLICT_RULES = [
    ("pre-revenue", "mrr", "The available context mixes a pre-revenue story with recurring revenue claims."),
    ("no users", "pilot", "The available context says there are no users, but also points to a pilot or live usage."),
    ("manual", "fully automated", "The available context alternates between a manual workaround story and a fully automated story."),
]

MAX_RETRIEVAL_CONTEXT_CHARS = 1700


def _contains_any(text: str, values: tuple[str, ...]) -> bool:
    return any(value in text for value in values)


def _format_needs(needs: list[str]) -> str:
    if not needs:
        return "problem and users"
    if len(needs) == 1:
        return needs[0]
    if len(needs) == 2:
        return f"{needs[0]} and {needs[1]}"
    return ", ".join(needs[:-1]) + f", and {needs[-1]}"


def infer_retrieval_needs(query: str, state: ConversationState | None = None) -> list[str]:
    lowered = (query or "").strip().lower()
    needs = [label for label, keywords in NEEDS_KEYWORDS.items() if _contains_any(lowered, keywords)]

    if not needs:
        stage = getattr(state, "stage", "unknown")
        if stage in {"idea", "pre-revenue", "unknown"}:
            needs = ["problem and users", "pain and workflow", "proof and experiments"]
        else:
            needs = ["problem and users", "solution and value", "pricing and willingness to pay"]

    if getattr(state, "stage", "unknown") in {"idea", "pre-revenue"} and "pricing and willingness to pay" in needs and "problem and users" not in needs:
        needs.insert(0, "problem and users")

    return needs[:4]


def _needs_query(query: str, needs: list[str]) -> str:
    if not needs:
        return query
    return f"{query}\n\nFocus the retrieval on: {_format_needs(needs)}."


def _detect_source_conflict(*texts: str) -> str:
    combined = " ".join(text for text in texts if text).lower()
    for left, right, message in CONFLICT_RULES:
        if left in combined and right in combined:
            return message
    return ""


def _merge_needs_from_domains(needs_info: list[str], domain_focus: list[str] | None) -> list[str]:
    merged = list(needs_info)
    domain_map = {
        "problem": ["problem and users", "pain and workflow", "current workaround"],
        "market": ["problem and users", "pricing and willingness to pay"],
        "solution": ["solution and value", "constraints and risks"],
        "business": ["pricing and willingness to pay", "solution and value"],
        "founder": ["problem and users", "constraints and risks"],
    }
    for domain in domain_focus or []:
        for item in domain_map.get(domain, []):
            if item not in merged:
                merged.append(item)
    return merged[:4]


def _trim_block(text: str, max_chars: int) -> str:
    value = (text or "").strip()
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + "..."


def _assemble_with_budget(parts: list[str], budget: int) -> str:
    assembled: list[str] = []
    used = 0
    for part in parts:
        cleaned = (part or "").strip()
        if not cleaned:
            continue
        separator = "\n\n" if assembled else ""
        remaining = budget - used - len(separator)
        if remaining <= 40:
            break
        piece = _trim_block(cleaned, remaining)
        assembled.append(piece)
        used += len(separator) + len(piece)
        if len(piece) < len(cleaned):
            break
    return "\n\n".join(assembled)


def build_retrieval_context(
    session_id: str,
    state: ConversationState,
    query: str,
    *,
    domain_focus: list[str] | None = None,
    geography: str = "",
    assumptions_to_verify: list[str] | None = None,
    answer_record: dict | None = None,
    session_context: str = "",
) -> dict:
    needs_info = infer_retrieval_needs(query, state)
    needs_info = _merge_needs_from_domains(needs_info, domain_focus)
    search_query = _needs_query(query, needs_info)
    if geography and geography != "unspecified":
        search_query += f"\n\nGeography: {geography}."
    if assumptions_to_verify:
        search_query += "\n\nAssumptions to verify:\n" + "\n".join(f"- {item}" for item in assumptions_to_verify[:3])

    sector_snippet = get_sector_prompt_snippet(state.sector)
    upload_snippets = retrieve_upload_context(session_id, query=search_query, top_k=2, max_chars=720)
    external_research = retrieve_external_research_context(state, query=search_query, top_k=2, max_chars=360)
    should_fetch_vc = _contains_any(search_query.lower(), INVESTOR_QUERY_TERMS)
    vc_firm_context = retrieve_vc_firm_context(state, query=search_query, top_k=2, max_chars=460) if should_fetch_vc else {"text": "", "sources": []}

    parts: list[str] = []
    if needs_info:
        parts.append("Current information need:\n" + "\n".join(f"- {item}" for item in needs_info))
    if domain_focus:
        parts.append("Business-domain focus:\n" + "\n".join(f"- {item}" for item in domain_focus))
    if geography and geography != "unspecified":
        parts.append(f"Geography context:\n- {geography}")
    if assumptions_to_verify:
        parts.append("Assumptions to verify:\n" + "\n".join(f"- {item}" for item in assumptions_to_verify[:3]))
    if answer_record:
        answer_record_summary = summarize_answer_record(answer_record, limit_domains=4)
        if answer_record_summary:
            parts.append("Internal answer record:\n" + answer_record_summary)
    if session_context.strip():
        context_excerpt = _trim_block(session_context.strip(), 420)
        parts.append("Active session context:\n" + context_excerpt)

    if upload_snippets:
        formatted = [f"[{snippet['source']} · {snippet['docType']}]\n{snippet['text']}" for snippet in upload_snippets]
        parts.append("Knowledge base notes:\n" + "\n\n".join(formatted))

    if external_research["text"]:
        parts.append(external_research["text"])

    if vc_firm_context["text"]:
        parts.append(vc_firm_context["text"])

    if sector_snippet:
        parts.append(f"Sector lens:\n{sector_snippet}")

    retrieval_gap = ""
    if not upload_snippets and not external_research["text"] and not vc_firm_context["text"]:
        retrieval_gap = f"The knowledge base does not currently have a strong answer on {_format_needs(needs_info)}."

    source_conflict = _detect_source_conflict(
        session_context,
        " ".join(snippet["text"] for snippet in upload_snippets),
        external_research["text"],
        vc_firm_context["text"],
    )

    if source_conflict:
        parts.append(f"Potential tension in available context:\n- {source_conflict}")
    if retrieval_gap:
        parts.append(f"Knowledge base gap:\n- {retrieval_gap}")

    context_text = _assemble_with_budget(parts, MAX_RETRIEVAL_CONTEXT_CHARS)
    return {
        "text": context_text,
        "sectorSnippet": sector_snippet,
        "researchSources": external_research["sources"] + vc_firm_context["sources"],
        "uploadSnippets": upload_snippets,
        "promptChars": len(context_text),
        "needsInfo": needs_info,
        "retrievalGap": retrieval_gap,
        "sourceConflict": source_conflict,
    }
