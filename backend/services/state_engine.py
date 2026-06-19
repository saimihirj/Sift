"""Deterministic state updates for low-latency mentoring turns."""

from __future__ import annotations

import re
from typing import Iterable

from backend.core.state import ConversationState


SECTION_KEYWORDS = {
    "Problem": {
        "problem", "pain", "pain point", "friction", "struggle", "manual", "waste", "inefficient", "job to be done"
    },
    "Solution": {
        "product", "build", "solution", "platform", "tool", "workflow", "feature", "model", "app"
    },
    "Market": {
        "market", "tam", "sam", "customer", "buyer", "segment", "category", "why now", "industry"
    },
    "Business Model": {
        "pricing", "price", "revenue", "subscription", "margin", "business model", "ltv", "cac", "unit economics", "monet"
    },
    "Traction": {
        "traction", "users", "customers", "growth", "retention", "churn", "mrr", "arr", "revenue today", "pilot"
    },
    "Team": {
        "team", "founder", "co-founder", "background", "hiring", "operator", "experience"
    },
    "Ask": {
        "raise", "funding", "runway", "ask", "seed", "round", "valuation", "investor"
    },
}

SHARPNESS_LABELS = {
    "Problem": ("fuzzy", "emerging", "clear", "sharp"),
    "Solution": ("vague", "forming", "defined", "sharp"),
    "Market": ("untested", "framed", "researched", "grounded"),
    "Business Model": ("unclear", "forming", "modeled", "defensible"),
    "Traction": ("early", "emerging", "credible", "strong"),
    "Team": ("unstated", "present", "credible", "compelling"),
    "Ask": ("open", "rough", "calculated", "investor-ready"),
}

NUMBER_PATTERN = re.compile(
    r"(?:(?:\$|₹|€)\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:k|m|b|cr|crore|lakh))?|"
    r"\d+(?:\.\d+)?\s?(?:%|percent|users|customers|months|weeks|days|years|mrr|arr|gmv))",
    re.IGNORECASE,
)
SOURCE_PATTERN = re.compile(
    r"\b(statista|gartner|mckinsey|bcg|report|source|survey|research|ibef|tracxn|government|our data|interviews)\b",
    re.IGNORECASE,
)
URGENCY_PATTERN = re.compile(
    r"\b(demo day|pitch(?:ing)? (?:on|this|next)|meeting (?:on|this)|deadline|tomorrow|friday|monday|next week|in \d+ days?)\b",
    re.IGNORECASE,
)
COMPANY_PATTERN = re.compile(
    r"\b(?:we are|our company is|company called|called)\s+([A-Z][A-Za-z0-9&\- ]{1,40})"
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _matched_sections(text: str) -> set[str]:
    normalized = _normalize(text)
    matches: set[str] = set()
    for section, keywords in SECTION_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            matches.add(section)
    if not matches and normalized:
        matches.add("Problem")
    return matches


def _bump_score(current: int) -> int:
    if current < 20:
        return 18
    if current < 50:
        return 12
    if current < 75:
        return 8
    return 4


def detect_sector(text: str) -> str:
    normalized = _normalize(text)
    if any(term in normalized for term in ("saas", "b2b", "api", "workflow software", "crm", "copilot")):
        return "saas"
    if any(term in normalized for term in ("d2c", "brand", "consumer product", "shopify", "instagram", "quick commerce")):
        return "d2c"
    if any(term in normalized for term in ("upi", "lending", "payments", "insurance", "wealth", "nbfc", "rbi")):
        return "fintech"
    if any(term in normalized for term in ("marketplace", "buyers and sellers", "supply", "demand", "listings")):
        return "marketplace"
    return "unknown"


def detect_stage(text: str) -> str:
    normalized = _normalize(text)
    if any(term in normalized for term in ("pre-revenue", "no revenue", "building", "prototype")):
        return "pre-revenue"
    if any(term in normalized for term in ("mrr", "arr", "paying customers", "launched", "revenue")):
        return "early-revenue"
    if any(term in normalized for term in ("series a", "scaling", "growing fast", "multi-market")):
        return "growth"
    if any(term in normalized for term in ("idea", "thinking about", "exploring")):
        return "idea"
    return "unknown"


def extract_number_claims(text: str) -> list[tuple[str, bool]]:
    source_provided = bool(SOURCE_PATTERN.search(text or ""))
    return [(match.group(0), source_provided) for match in NUMBER_PATTERN.finditer(text or "")]


def infer_phase(state: ConversationState) -> str:
    overall = state.overall_coverage()
    if state.turns <= 1:
        return "intro"
    if overall < 30:
        return "exploration"
    if overall < 65:
        return "deep_dive"
    return "synthesis"


def update_state_from_turn(
    state: ConversationState,
    founder_message: str,
    assistant_message: str = "",
) -> ConversationState:
    text = founder_message or ""
    for section in _matched_sections(text):
        state.coverage[section] = min(100, state.coverage[section] + _bump_score(state.coverage[section]))

    sector = detect_sector(text)
    if state.sector == "unknown" and sector != "unknown":
        state.sector = sector

    stage = detect_stage(text)
    if state.stage == "unknown" and stage != "unknown":
        state.stage = stage

    company_match = COMPANY_PATTERN.search(text)
    if company_match and not state.company_name:
        state.company_name = company_match.group(1).strip()

    if URGENCY_PATTERN.search(text):
        state.urgency = True

    for claim, source_provided in extract_number_claims(text):
        state.add_number_claim(claim, source_provided=source_provided)

    state.turns += 1
    state.phase = infer_phase(state)
    if assistant_message:
        state.facts["last_question"] = assistant_message.strip()
    return state


def coverage_items(state: ConversationState) -> list[dict]:
    items = []
    for section, score in state.coverage.items():
        labels = SHARPNESS_LABELS.get(section, ("low", "medium", "high", "complete"))
        if score < 25:
            label = labels[0]
        elif score < 50:
            label = labels[1]
        elif score < 75:
            label = labels[2]
        else:
            label = labels[3]
        items.append({"section": section, "score": score, "label": label})
    return items


def next_gap(state: ConversationState) -> str:
    weakest = min(state.coverage.items(), key=lambda item: item[1])[0]
    return weakest


def last_assistant_message(history: Iterable[dict]) -> str:
    for item in reversed(list(history)):
        if item.get("role") == "assistant":
            return item.get("content", "")
    return ""
