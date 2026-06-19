"""Context builder for the Sift Brain decision layer.

Assembles the full, optimised context for each query:
  1. Retrieve relevant KB cards (hybrid dense+sparse)
  2. Add entity graph neighbours
  3. Add session history (bounded by token budget)
  4. Add domain-specific metric benchmarks from the domain registry
  5. Return a ready-to-use system prompt addendum

Usage:
    from sift_brain.decision_layer.context_builder import build_context
    context = build_context(
        query="What's a good NRR for Series A SaaS?",
        session_turns=[...],
        domain="saas",
        geography="global",
        token_budget=2000,
    )
    # context["kb_cards"]    — list of retrieved cards
    # context["graph_nodes"] — related graph entities
    # context["benchmarks"]  — domain metric benchmarks
    # context["prompt_block"]— formatted string ready to inject into system prompt
"""

from __future__ import annotations

import os
from typing import Any

from sift_brain.knowledge_graph.domains import get_domain
from sift_brain.knowledge_graph.retriever import retrieve

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MAX_CARDS = int(os.environ.get("SIFT_BRAIN_MAX_KB_CARDS", "6"))
MAX_HISTORY_TURNS = int(os.environ.get("SIFT_BRAIN_MAX_HISTORY_TURNS", "8"))
CHARS_PER_TOKEN_ESTIMATE = 4


# ---------------------------------------------------------------------------
# Token budget helpers
# ---------------------------------------------------------------------------

def _approx_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN_ESTIMATE)


def _trim_to_budget(items: list[str], budget: int) -> list[str]:
    used = 0
    result: list[str] = []
    for item in items:
        cost = _approx_tokens(item)
        if used + cost > budget:
            break
        result.append(item)
        used += cost
    return result


# ---------------------------------------------------------------------------
# Card formatting
# ---------------------------------------------------------------------------

def _format_card(card: dict[str, Any], idx: int) -> str:
    title = card.get("title", "Untitled")
    body = (card.get("body") or card.get("description") or "")[:600]
    domain = card.get("domain", "")
    source = card.get("source", "")
    url = card.get("url", "")
    parts = [f"[{idx+1}] {title}"]
    if body:
        parts.append(body)
    meta = " | ".join(filter(None, [domain, source]))
    if meta:
        parts.append(f"Source: {meta}")
    if url:
        parts.append(f"Ref: {url}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# History formatting
# ---------------------------------------------------------------------------

def _format_history(turns: list[dict[str, Any]], max_turns: int) -> str:
    recent = turns[-max_turns:] if len(turns) > max_turns else turns
    lines: list[str] = []
    for turn in recent:
        role = turn.get("role", "unknown").upper()
        content = (turn.get("content") or "")[:400]
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Benchmark formatting
# ---------------------------------------------------------------------------

def _format_benchmarks(benchmarks: dict[str, str]) -> str:
    if not benchmarks:
        return ""
    lines = ["Domain benchmarks:"]
    for k, v in benchmarks.items():
        label = k.replace("_", " ").replace("good ", "").title()
        lines.append(f"  • {label}: {v}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_context(
    query: str,
    *,
    session_turns: list[dict[str, Any]] | None = None,
    domain: str | None = None,
    geography: str | None = None,
    token_budget: int = 2000,
    top_k: int = MAX_CARDS,
) -> dict[str, Any]:
    """Assemble the full context for a query.

    Returns a dict with:
      kb_cards     — retrieved knowledge cards
      graph_nodes  — related graph entity descriptions
      benchmarks   — domain metric benchmarks dict
      prompt_block — formatted string ready to inject into system prompt
      tokens_used  — approximate token count of the prompt block
    """
    # ---- 1. Retrieve KB cards -------
    kb_cards = retrieve(query, domain=domain, top_k=top_k, use_graph=True)

    # ---- 2. Domain benchmarks -------
    benchmarks: dict[str, str] = {}
    domain_cfg = get_domain(domain or "")
    if domain_cfg:
        benchmarks = domain_cfg.metric_benchmarks

    # ---- 3. Session history ---------
    history_str = ""
    if session_turns:
        history_str = _format_history(session_turns, MAX_HISTORY_TURNS)

    # ---- 4. Assemble prompt block ----
    sections: list[str] = []

    if kb_cards:
        card_texts = [_format_card(c, i) for i, c in enumerate(kb_cards)]
        kb_budget = int(token_budget * 0.55)
        card_texts = _trim_to_budget(card_texts, kb_budget)
        if card_texts:
            sections.append("=== Knowledge Base Context ===\n" + "\n\n".join(card_texts))

    if benchmarks:
        bench_str = _format_benchmarks(benchmarks)
        sections.append(bench_str)

    if history_str:
        history_budget = int(token_budget * 0.25)
        trimmed_history = history_str[: history_budget * CHARS_PER_TOKEN_ESTIMATE]
        sections.append("=== Recent Conversation ===\n" + trimmed_history)

    prompt_block = "\n\n".join(sections)
    tokens_used = _approx_tokens(prompt_block)

    return {
        "kb_cards": kb_cards,
        "benchmarks": benchmarks,
        "history": history_str,
        "prompt_block": prompt_block,
        "tokens_used": tokens_used,
        "cards_used": len(card_texts) if kb_cards else 0,
    }
