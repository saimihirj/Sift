"""Intelligent query router for the Sift Brain decision layer.

Routes incoming queries to the most appropriate model/path based on:
  - Query type (ideation, evaluation, expert, deck review)
  - Domain complexity
  - Available providers
  - Whether the Sift Brain custom model is running

This wraps backend/services/model_router.py and adds intelligence-layer routing.

Usage:
    from sift_brain.decision_layer.router import route_query
    provider, model = route_query(query, session_context=ctx)
"""

from __future__ import annotations

import os
import re
from typing import Any


# ---------------------------------------------------------------------------
# Query type classifier
# ---------------------------------------------------------------------------

_EVALUATE_PATTERNS = re.compile(
    r"\b(evaluate|assess|score|rate|verdict|deck|pitch deck|investment|risk|red flag|"
    r"burn rate|runway|unit economics|ltv|cac|arr|mrr|nrr|churn|cap table)\b",
    re.I,
)
_EXPERT_PATTERNS = re.compile(
    r"\b(explain|what is|how does|define|compare|frameworks?|term sheet|"
    r"waterfall|preference stack|anti-dilution|esop|convertible note|safe|"
    r"valuation|series [a-e]|vc fund|pe fund|irr|moic)\b",
    re.I,
)
_DECK_PATTERNS = re.compile(
    r"\b(deck|pitch deck|slide|presentation|pdf|pptx|review the deck)\b",
    re.I,
)
_IDEATE_PATTERNS = re.compile(
    r"\b(idea|ideate|brainstorm|think through|startup idea|problem|solution|"
    r"customer|market|gtm|go.to.market|pivot|founder)\b",
    re.I,
)


def classify_query(query: str) -> str:
    """Return one of: 'evaluate', 'expert', 'deck', 'ideate', 'general'."""
    q = query.strip()
    if _DECK_PATTERNS.search(q):
        return "deck"
    if _EVALUATE_PATTERNS.search(q):
        return "evaluate"
    if _EXPERT_PATTERNS.search(q):
        return "expert"
    if _IDEATE_PATTERNS.search(q):
        return "ideate"
    return "general"


# ---------------------------------------------------------------------------
# Complexity estimator
# ---------------------------------------------------------------------------

def estimate_complexity(query: str, turn_count: int = 0) -> str:
    """Return 'speed' or 'balanced' based on query length/complexity and turn count."""
    word_count = len(query.split())
    has_multi_part = bool(re.search(r"(and|also|additionally|furthermore|secondly)", query, re.I))
    has_numbers = bool(re.search(r"\d+[%$MBK]?", query))

    if word_count > 40 or has_multi_part or (has_numbers and word_count > 20):
        return "balanced"
    if turn_count > 6:
        return "balanced"
    return "speed"


# ---------------------------------------------------------------------------
# Provider availability
# ---------------------------------------------------------------------------

def _sift_brain_available() -> bool:
    """Check if the Sift Brain local server is configured and likely running."""
    base_url = os.environ.get("SIFT_BRAIN_BASE_URL", "").strip()
    return bool(base_url) and os.environ.get("SIFT_MODEL_PROVIDER", "").lower() == "sift_brain"


def _get_active_provider() -> str:
    try:
        from backend.services.model_router import active_provider
        return active_provider()
    except Exception:
        return os.environ.get("SIFT_MODEL_PROVIDER", "ollama")


# ---------------------------------------------------------------------------
# Routing table
# ---------------------------------------------------------------------------

# Maps (query_type, complexity) -> preferred provider type
# "any" means use whatever the session has configured
ROUTING_TABLE: dict[tuple[str, str], str] = {
    ("deck", "balanced"):    "sift_brain_or_vision",
    ("deck", "speed"):       "sift_brain_or_vision",
    ("evaluate", "balanced"): "sift_brain_or_balanced",
    ("evaluate", "speed"):    "any",
    ("expert", "balanced"):   "sift_brain_or_balanced",
    ("expert", "speed"):      "any",
    ("ideate", "speed"):      "any",
    ("ideate", "balanced"):   "any",
    ("general", "speed"):     "any",
    ("general", "balanced"):  "any",
}


def route_query(
    query: str,
    *,
    session_provider: str = "",
    session_model: str = "",
    turn_count: int = 0,
    force_profile: str = "",
) -> dict[str, Any]:
    """Return routing decision for a query.

    Returns:
        {
          "provider": str,
          "profile": "speed" | "balanced",
          "query_type": str,
          "complexity": str,
          "use_sift_brain": bool,
          "rationale": str,
        }
    """
    query_type = classify_query(query)
    complexity = force_profile or estimate_complexity(query, turn_count)
    routing_hint = ROUTING_TABLE.get((query_type, complexity), "any")

    use_sift_brain = False
    rationale = f"query_type={query_type}, complexity={complexity}"

    if routing_hint == "sift_brain_or_vision" and _sift_brain_available():
        provider = "sift_brain"
        use_sift_brain = True
        rationale += " → Sift Brain (deck/vision)"
    elif routing_hint == "sift_brain_or_balanced" and _sift_brain_available():
        provider = "sift_brain"
        use_sift_brain = True
        rationale += " → Sift Brain (balanced expert)"
    else:
        provider = session_provider or _get_active_provider()
        rationale += f" → {provider} (session default)"

    return {
        "provider": provider,
        "profile": complexity,
        "query_type": query_type,
        "complexity": complexity,
        "use_sift_brain": use_sift_brain,
        "rationale": rationale,
    }
