"""Expert-mode routing, retrieval assembly, and prompting."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from state import ConversationState
from backend.services.expert_knowledge import (
    build_card_context,
    retrieve_expert_cards,
    source_citations,
    suggest_knowledge_lane,
)
from backend.services.uploads import retrieve_upload_context


EXPERT_QUICK_ACTIONS = [
    "Break down a term",
    "Compare structures",
    "Pre-screen an idea",
    "Review a deck",
    "Check market context",
    "Map key risks",
    "Pressure-test unit economics",
]

STUCK_CUES = (
    "i'm stuck",
    "im stuck",
    "not sure",
    "confused",
    "idk",
    "i dont know",
    "i don't know",
    "help me think",
)

COMPARE_CUES = (" vs ", "versus", "compare", "difference between", "better than")
PRE_SCREEN_CUES = ("pre-screen", "prescreen", "screen this", "assess this", "evaluate this", "should i invest")
FRESHNESS_CUES = ("latest", "current", "today", "recent", "new", "updated", "as of")
EXPLAIN_CUES = ("what is", "explain", "define", "meaning of", "term", "break down")
MARKET_CUES = (
    "market",
    "landscape",
    "space",
    "ecosystem",
    "trend",
    "adoption",
    "who is building",
    "who are the players",
    "competition",
    "competitive",
)
LIVE_WEB_STOPWORDS = {
    "about",
    "after",
    "around",
    "because",
    "between",
    "does",
    "from",
    "have",
    "into",
    "space",
    "than",
    "that",
    "their",
    "there",
    "these",
    "this",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
}

ROLE_STYLE = {
    "student": "Keep it practical, plain, and confidence-building without doing the reasoning for them.",
    "operator": "Assume execution context. Focus on tradeoffs, bottlenecks, and what would matter in practice.",
    "founder": "Assume urgency and ownership. Push for judgment, evidence, and next actions.",
    "investor": "Assume they care about downside, evidence quality, and why the opportunity matters now.",
    "professional": "Bridge domain knowledge and startup logic. Translate where needed, but do not over-teach.",
    "other": "Stay adaptable and direct.",
    "unknown": "Stay adaptable and direct.",
}

HELP_MODE_STYLE = {
    "coach_me": "Answer clearly, then ask one focused follow-up that makes the user reason from their own context.",
    "challenge_me": "Answer clearly, then pressure-test the weakest assumption or missing evidence.",
    "explain_directly": "Answer directly and completely first. Only ask a follow-up if it is genuinely necessary.",
}

ACTION_NEEDS = {
    "explain": ["definition", "practical use", "why it matters"],
    "compare": ["differences", "tradeoffs", "when to use each"],
    "pre_screen": ["strengths", "risks", "missing evidence", "contradictions", "next actions"],
    "analyze_upload": ["strongest signal", "gaps", "contradictions", "next actions"],
    "freshness_query": ["latest context", "what changed", "what still matters"],
    "open_discussion": ["best framing", "tradeoffs", "next question"],
}


def build_expert_opening(user_role: str, geography: str) -> str:
    geography_text = geography if geography and geography != "auto" else "global"
    return (
        "Expert mode is ready. Ask a concrete question, compare structures, or upload material for review. "
        f"I will use the local corpus first, pull in live web context when the local evidence is thin or stale, "
        f"keep geography in view ({geography_text}), and tell you directly when the evidence is weak."
    )


def get_expert_quick_actions() -> list[str]:
    return EXPERT_QUICK_ACTIONS


def classify_expert_turn(message: str, *, has_upload: bool = False, help_mode: str = "coach_me") -> dict[str, Any]:
    lowered = (message or "").strip().lower()
    action = "open_discussion"
    if has_upload:
        action = "analyze_upload"
    elif any(cue in lowered for cue in PRE_SCREEN_CUES):
        action = "pre_screen"
    elif any(cue in lowered for cue in COMPARE_CUES):
        action = "compare"
    elif any(cue in lowered for cue in FRESHNESS_CUES):
        action = "freshness_query"
    elif any(cue in lowered for cue in EXPLAIN_CUES):
        action = "explain"

    stuck = any(cue in lowered for cue in STUCK_CUES)
    follow_up_mode = "scaffold_then_probe" if stuck else ("answer_only" if help_mode == "explain_directly" else "answer_then_probe")
    lane = suggest_knowledge_lane(message)
    return {
        "action": action,
        "knowledgeLane": lane,
        "followUpMode": follow_up_mode,
        "needsInfo": ACTION_NEEDS.get(action, ACTION_NEEDS["open_discussion"]),
        "stuck": stuck,
    }


def _live_web_context(query: str, geography: str, max_chars: int = 420) -> dict[str, Any]:
    search_terms = query.strip()
    if geography and geography not in {"auto", "unspecified"}:
        search_terms += f" {geography}"
    try:
        response = requests.get(
            f"https://html.duckduckgo.com/html/?q={quote(search_terms)}",
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        sources: list[dict[str, Any]] = []
        snippets: list[str] = []
        for result in soup.select(".result")[:3]:
            anchor = result.select_one(".result__a")
            if anchor is None:
                continue
            title = anchor.get_text(" ", strip=True)
            url = anchor.get("href", "").strip()
            snippet_node = result.select_one(".result__snippet")
            snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
            sources.append(
                {
                    "title": title or url,
                    "url": url,
                    "label": title or url,
                    "sourceType": "live_web",
                    "geographyScope": geography if geography not in {"", "auto", "unspecified"} else "global",
                    "confidence": "reference",
                    "domain": "live_web",
                }
            )
            if snippet:
                snippets.append(f"[{title}]\n{snippet}")
            if sum(len(item) for item in snippets) >= max_chars:
                break
        return {
            "text": "\n\n".join(snippets)[:max_chars],
            "sources": sources[:3],
        }
    except Exception:
        return {"text": "", "sources": []}


def _coverage_tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[a-z0-9][a-z0-9+.-]{1,}", text or "", flags=re.IGNORECASE)
        if token.lower() not in LIVE_WEB_STOPWORDS
    }


def should_use_live_web(
    query: str,
    *,
    route: dict[str, Any],
    cards: list[dict[str, Any]],
    upload_snippets: list[dict[str, Any]],
) -> bool:
    if upload_snippets:
        return False
    lowered = (query or "").strip().lower()
    action = route.get("action", "open_discussion")
    top_score = cards[0]["score"] if cards else 0
    query_tokens = _coverage_tokens(query)
    evidence_tokens = _coverage_tokens(
        " ".join(
            " ".join(
                [
                    str(card.get("title", "")),
                    str(card.get("body", "")),
                    " ".join(card.get("tags", [])),
                    " ".join(card.get("relatedTerms", [])),
                ]
            )
            for card in cards[:3]
        )
    )
    token_coverage = len(query_tokens & evidence_tokens) / max(len(query_tokens), 1)
    if action == "freshness_query":
        return True
    if not cards:
        return True
    if top_score < 10:
        return True
    if top_score < 14 and token_coverage < 0.6:
        return True
    if any(cue in lowered for cue in MARKET_CUES) and token_coverage < 0.58:
        return True
    return False


def build_expert_retrieval_context(
    session_id: str,
    query: str,
    *,
    route: dict[str, Any],
    geography: str = "auto",
    live_web_enabled: bool = False,
) -> dict[str, Any]:
    upload_snippets = retrieve_upload_context(session_id, query=query, top_k=2, max_chars=900)
    cards = retrieve_expert_cards(
        query,
        lane=route.get("knowledgeLane", "startup"),
        geography=geography,
        top_k=6,
    )
    live_web = {"text": "", "sources": []}
    retrieval_gap = ""
    top_score = cards[0]["score"] if cards else 0
    if not upload_snippets and (not cards or top_score < 10):
        retrieval_gap = "The local expert corpus does not have a strong direct hit for this question yet."
    if live_web_enabled and should_use_live_web(query, route=route, cards=cards, upload_snippets=upload_snippets):
        live_web = _live_web_context(query, geography)
    concepts = [card["title"] for card in cards[:5]]
    sources = source_citations(cards)
    if live_web["sources"]:
        sources.extend(live_web["sources"])

    parts: list[str] = [
        f"Requested expert action: {route.get('action', 'open_discussion')}",
        f"Knowledge lane: {route.get('knowledgeLane', 'startup')}",
        f"Preferred follow-up mode: {route.get('followUpMode', 'answer_then_probe')}",
        "Need to cover: " + ", ".join(route.get("needsInfo", [])),
    ]
    if geography and geography not in {"", "auto", "unspecified"}:
        parts.append(f"Geography preference: {geography}")
    if cards:
        parts.append("Retrieved expert knowledge:\n" + build_card_context(cards, max_chars=1200))
    if upload_snippets:
        formatted = [f"[{item['source']} · {item['docType']}]\n{item['text']}" for item in upload_snippets]
        parts.append("Uploaded context:\n" + "\n\n".join(formatted))
    if live_web["text"]:
        parts.append("Live web fallback:\n" + live_web["text"])
    if retrieval_gap and not live_web["text"]:
        parts.append("Knowledge gap:\n" + retrieval_gap)

    confidence = 0.22
    if top_score >= 24:
        confidence = 0.88
    elif top_score >= 16:
        confidence = 0.74
    elif top_score >= 8:
        confidence = 0.58
    if live_web["text"] and not cards:
        confidence = max(confidence, 0.42)

    return {
        "text": "\n\n".join(part for part in parts if part).strip(),
        "cards": cards,
        "sources": sources[:8],
        "confidence": round(confidence, 2),
        "knowledgeLane": route.get("knowledgeLane", "startup"),
        "usedLiveWeb": bool(live_web["text"]),
        "retrievalGap": retrieval_gap,
        "sourceConflict": "",
        "concepts": concepts,
        "uploadSnippets": upload_snippets,
        "promptChars": len("\n\n".join(part for part in parts if part)),
        "needsInfo": route.get("needsInfo", []),
    }


def build_analysis_snapshot(
    *,
    query: str,
    route: dict[str, Any],
    retrieval: dict[str, Any],
) -> dict[str, Any]:
    action = route.get("action", "open_discussion")
    concepts = retrieval.get("concepts", [])[:5]
    strengths: list[str] = []
    risks: list[str] = []
    missing: list[str] = []
    contradictions: list[str] = []
    next_questions: list[str] = []
    next_actions: list[str] = []

    if retrieval.get("uploadSnippets"):
        strengths.append("There is direct uploaded material to inspect, so the read can stay concrete.")
    if concepts:
        strengths.append("The question maps to known concepts in the local corpus: " + ", ".join(concepts[:3]) + ".")
    if not retrieval.get("sources"):
        risks.append("This turn has weak provenance because no useful KB sources were retrieved.")
    if retrieval.get("usedLiveWeb"):
        risks.append("Part of the answer depends on live web fallback and should be treated as fresher but less curated.")
    if retrieval.get("retrievalGap"):
        missing.append(retrieval["retrievalGap"])
    if action in {"pre_screen", "analyze_upload"}:
        missing.extend(
            [
                "Clear user pain evidence",
                "Proof that the wedge is believable",
                "Concrete distribution or GTM path",
            ]
        )
        next_questions.extend(
            [
                "What is the strongest proof that users care right now?",
                "What breaks first if this has to scale?",
                "What would make an investor or operator say no today?",
            ]
        )
        next_actions.extend(
            [
                "List the top 3 strengths and top 3 risks before making the next decision.",
                "Rewrite the core claim in one sentence and attach one supporting proof point.",
            ]
        )
    elif action == "compare":
        next_questions.extend(
            [
                "Which option matches your stage and constraints better?",
                "What downside are you most willing to accept?",
            ]
        )
        next_actions.append("Turn the comparison into a decision memo with when-to-use and when-not-to-use guidance.")
    else:
        next_questions.extend(
            [
                "What part of this matters most to your actual decision right now?",
                "What context are you already assuming that should be made explicit?",
            ]
        )
        next_actions.append("Move from definition to application: explain how this changes your next move.")

    return {
        "strengths": strengths[:4],
        "risks": risks[:4],
        "missingEvidence": missing[:4],
        "contradictions": contradictions[:3],
        "nextQuestions": next_questions[:4],
        "recommendedNextActions": next_actions[:4],
        "concepts": concepts,
    }


def build_expert_system_prompt(
    *,
    state: ConversationState,
    user_message: str,
    route: dict[str, Any],
    retrieval_context: str,
    help_mode: str,
    analysis_snapshot: dict[str, Any],
    stable_workflow: bool = False,
) -> str:
    role_style = ROLE_STYLE.get(state.founder_type, ROLE_STYLE["unknown"])
    prompt_parts = [
        "You are SignalX Expert, a domain workbench for startup, VC, finance, regulation, and market questions.",
        "Use only the supplied context and sources. If coverage is thin, stale, or geographically mismatched, say that directly instead of filling gaps from unstated memory.",
        "Never invent market facts, company activity, regulatory detail, or current-state claims that are not supported by the supplied context.",
        "Lead with the answer in one or two direct sentences, then support it with the strongest evidence and the next implication.",
        "Do not sound generic. Be sharp, natural, and useful.",
        HELP_MODE_STYLE.get(help_mode, HELP_MODE_STYLE["coach_me"]),
        role_style,
        "Two-way default: answer the user, then make one high-value move. At most one direct question unless the user explicitly asks for a list.",
        "If the user sounds stuck, you may give a short scaffold, template, or example, then return to the question.",
        f"Current action: {route.get('action', 'open_discussion')}.",
        f"Knowledge lane: {route.get('knowledgeLane', 'startup')}.",
        f"Follow-up mode: {route.get('followUpMode', 'answer_then_probe')}.",
        "When the action is pre-screen or upload analysis, organize the answer operationally around strengths, risks, missing evidence, contradictions, and next actions.",
        "Mention geography when it materially changes the answer.",
        "Prefer short prose or short labeled sections. Do not use markdown syntax like **bold**, # headings, or decorative bullet spam.",
    ]
    if analysis_snapshot.get("missingEvidence"):
        prompt_parts.append("Current missing evidence: " + "; ".join(analysis_snapshot["missingEvidence"][:3]))
    if stable_workflow:
        prompt_parts.append("Stable workflow: keep the answer lower-variance and concise.")
    if retrieval_context:
        prompt_parts.append(retrieval_context[:2000])
    return "\n\n".join(prompt_parts)
