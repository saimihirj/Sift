"""Lightweight prompt refinement and answer-record helpers."""

from __future__ import annotations

import re
from typing import Any

from backend.core.state import ConversationState


DOMAIN_ORDER = ("problem", "market", "solution", "business", "founder")

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "problem": (
        "problem",
        "pain",
        "user",
        "customer",
        "annoying",
        "unacceptable",
        "workflow",
        "workaround",
        "manual",
        "error",
        "friction",
    ),
    "market": (
        "market",
        "segment",
        "buyer",
        "customer segment",
        "distribution",
        "channel",
        "go to market",
        "wedge",
        "beachhead",
        "why now",
        "regulation",
        "geography",
    ),
    "solution": (
        "solution",
        "product",
        "feature",
        "workflow",
        "platform",
        "tool",
        "engine",
        "model",
        "automation",
        "integration",
        "outcome",
    ),
    "business": (
        "pricing",
        "revenue",
        "business model",
        "margin",
        "cost",
        "unit economics",
        "pay",
        "subscription",
        "sales",
        "contract",
        "budget",
    ),
    "founder": (
        "founder",
        "background",
        "experience",
        "co-founder",
        "operator",
        "why us",
        "why you",
        "credibility",
        "advantage",
    ),
}

DOMAIN_HINTS: dict[str, str] = {
    "problem": "likely talking about the problem definition, so verify the exact user and pain.",
    "market": "likely pointing at the market or customer wedge, so verify the first buyer and why now.",
    "solution": "likely describing the solution, so verify the user outcome before the feature list.",
    "business": "likely discussing business logic, so verify what gets paid for and the delivery cost.",
    "founder": "likely about founder credibility or team fit, so verify why this team can win here.",
}

ANSWER_RECORD_LABELS: dict[str, str] = {
    "problem": "Problem",
    "market": "Market",
    "solution": "Solution",
    "business": "Business",
    "founder": "Founder",
}

EVIDENCE_TERMS = (
    "interview",
    "interviews",
    "pilot",
    "pilots",
    "test",
    "tests",
    "prototype",
    "pretotype",
    "measured",
    "observed",
    "usage",
    "users",
    "customers",
    "paying",
    "signed",
    "live",
    "launched",
    "feedback",
    "retention",
    "revenue",
    "waitlist",
)

PLAN_TERMS = (
    "will",
    "would",
    "plan",
    "planning",
    "going to",
    "want to",
    "hope to",
    "intend to",
    "we think",
    "we believe",
    "could",
    "should",
    "might",
    "next we",
)

USER_PAIN_TERMS = ("user", "customer", "pain", "problem", "workaround", "manual", "workflow")
NUMBER_PATTERN = re.compile(r"(?:(?:\$|₹|€)\s?\d[\d,]*(?:\.\d+)?|\d+(?:\.\d+)?\s?(?:%|users|customers|months|weeks|days|hours|minutes|pilots|tests|interviews))", re.IGNORECASE)
WORD_PATTERN = re.compile(r"[a-zA-Z0-9']+")


def _empty_record_entry(label: str) -> dict[str, Any]:
    return {
        "label": label,
        "notes": [],
        "evidence": [],
        "hypotheses": [],
    }


def empty_answer_record() -> dict[str, dict[str, Any]]:
    return {key: _empty_record_entry(label) for key, label in ANSWER_RECORD_LABELS.items()}


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = (text or "").lower()
    return any(keyword in lowered for keyword in keywords)


def _tokens(text: str) -> list[str]:
    return WORD_PATTERN.findall((text or "").lower())


def _first_sentences(text: str, limit: int = 2) -> list[str]:
    parts = [chunk.strip() for chunk in re.split(r"(?<=[.!?])\s+|\n+", text or "") if chunk.strip()]
    return parts[:limit]


def _clean_snippet(text: str, limit: int = 220) -> str:
    snippet = " ".join(_first_sentences(text, limit=2)).strip()
    snippet = re.sub(r"\s+", " ", snippet)
    if len(snippet) > limit:
        snippet = snippet[: limit - 1].rstrip() + "..."
    return snippet


def classify_domain_focus(text: str, state: ConversationState | None = None) -> list[str]:
    lowered = (text or "").strip().lower()
    if not lowered:
        if state and state.stage in {"idea", "pre-revenue", "unknown"}:
            return ["problem"]
        return ["solution"]

    scores: list[tuple[int, str]] = []
    for domain in DOMAIN_ORDER:
        score = sum(lowered.count(keyword) for keyword in DOMAIN_KEYWORDS[domain])
        if score > 0:
            scores.append((score, domain))

    if not scores:
        if _contains_any(lowered, USER_PAIN_TERMS):
            return ["problem"]
        if state and state.stage in {"idea", "pre-revenue", "unknown"}:
            return ["problem"]
        return ["solution"]

    scores.sort(key=lambda item: (-item[0], DOMAIN_ORDER.index(item[1])))
    domains = [scores[0][1]]
    if len(scores) > 1 and scores[1][0] >= max(scores[0][0] - 1, 1):
        domains.append(scores[1][1])
    return domains[:2]


def detect_evidence_balance(text: str) -> dict[str, Any]:
    lowered = (text or "").lower()
    evidence_hits = sum(lowered.count(term) for term in EVIDENCE_TERMS)
    plan_hits = sum(lowered.count(term) for term in PLAN_TERMS)
    has_numbers = bool(NUMBER_PATTERN.search(text or ""))

    if evidence_hits == 0 and plan_hits == 0:
        status = "mixed"
    elif evidence_hits >= max(plan_hits, 1):
        status = "evidence"
    elif plan_hits >= evidence_hits + 1:
        status = "hypothesis"
    else:
        status = "mixed"

    return {
        "status": status,
        "evidenceHits": evidence_hits,
        "planHits": plan_hits,
        "hasNumbers": has_numbers,
    }


def infer_assumptions_to_verify(text: str, domains: list[str], state: ConversationState | None = None) -> list[str]:
    lowered = (text or "").strip().lower()
    token_count = len(_tokens(lowered))
    assumptions: list[str] = []

    if not domains:
        domains = classify_domain_focus(text, state)

    if token_count <= 12:
        assumptions.append(
            f"Assumption to verify: this is {DOMAIN_HINTS.get(domains[0], 'likely a broad founder point, so verify what part of the story they mean first.')}"
        )

    primary = domains[0]
    if primary == "problem" and not _contains_any(lowered, ("user", "customer", "buyer", "team")):
        assumptions.append("Assumption to verify: the exact user is still implied rather than named directly.")
    if primary == "market" and not _contains_any(lowered, ("first", "segment", "buyer", "customer", "why now", "region", "country")):
        assumptions.append("Assumption to verify: the first customer wedge and market timing are still underspecified.")
    if primary == "solution" and not _contains_any(lowered, ("outcome", "better", "faster", "save", "reduce", "prevent")):
        assumptions.append("Assumption to verify: the user outcome is still weaker than the product description.")
    if primary == "business" and not _contains_any(lowered, ("pay", "pricing", "revenue", "cost", "budget", "margin")):
        assumptions.append("Assumption to verify: the payment logic is implied, but not yet stated clearly.")
    if primary == "founder" and not _contains_any(lowered, ("experience", "background", "worked", "built", "team", "founder")):
        assumptions.append("Assumption to verify: founder credibility is implied, but not yet supported with specifics.")

    return assumptions[:3]


def update_answer_record(
    record: dict[str, dict[str, Any]] | None,
    text: str,
    domains: list[str],
    *,
    source: str = "founder",
    evidence_status: str = "mixed",
    assumptions: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    next_record = empty_answer_record()
    for key, value in (record or {}).items():
        if key not in next_record or not isinstance(value, dict):
            continue
        next_record[key]["notes"] = list(value.get("notes", []))[:6]
        next_record[key]["evidence"] = list(value.get("evidence", []))[:6]
        next_record[key]["hypotheses"] = list(value.get("hypotheses", []))[:6]

    snippet = _clean_snippet(text)
    if not snippet or not domains:
        return next_record

    bucket = "evidence" if evidence_status == "evidence" else "hypotheses" if evidence_status == "hypothesis" else "notes"
    source_prefix = "Founder" if source == "founder" else source.title()
    formatted = f"{source_prefix}: {snippet}"
    for domain in domains:
        if domain not in next_record:
            continue
        entry = next_record[domain]
        if formatted not in entry["notes"]:
            entry["notes"] = ([formatted] + entry["notes"])[:6]
        if formatted not in entry[bucket]:
            entry[bucket] = ([formatted] + entry[bucket])[:6]

    for assumption in assumptions or []:
        problem_entry = next_record[domains[0]]
        assumption_text = f"Assumption: {assumption}"
        if assumption_text not in problem_entry["hypotheses"]:
            problem_entry["hypotheses"] = ([assumption_text] + problem_entry["hypotheses"])[:6]

    return next_record


def summarize_answer_record(record: dict[str, dict[str, Any]] | None, *, limit_domains: int = 3) -> str:
    if not record:
        return ""

    lines: list[str] = []
    used = 0
    for domain in DOMAIN_ORDER:
        entry = (record or {}).get(domain)
        if not isinstance(entry, dict):
            continue
        note = ""
        for bucket in ("evidence", "notes", "hypotheses"):
            values = [str(item).strip() for item in entry.get(bucket, []) if str(item).strip()]
            if values:
                note = values[0]
                break
        if not note:
            continue
        lines.append(f"- {ANSWER_RECORD_LABELS[domain]}: {note}")
        used += 1
        if used >= limit_domains:
            break
    return "\n".join(lines)


def refine_founder_input(
    text: str,
    *,
    state: ConversationState | None = None,
    recent_history: list[str] | None = None,
) -> dict[str, Any]:
    del recent_history
    domains = classify_domain_focus(text, state)
    evidence_balance = detect_evidence_balance(text)
    assumptions = infer_assumptions_to_verify(text, domains, state)
    return {
        "domainFocus": domains,
        "assumptionsToVerify": assumptions,
        "evidenceStatus": evidence_balance["status"],
        "evidenceSignals": evidence_balance["evidenceHits"],
        "planSignals": evidence_balance["planHits"],
        "hasNumbers": evidence_balance["hasNumbers"],
    }
