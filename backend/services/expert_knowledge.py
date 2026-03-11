"""Canonical expert knowledge ingestion and hybrid retrieval."""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9_+.-]{1,}", re.IGNORECASE)
STOPWORDS = {
    "about",
    "after",
    "also",
    "because",
    "between",
    "could",
    "does",
    "from",
    "have",
    "into",
    "more",
    "most",
    "should",
    "than",
    "that",
    "their",
    "there",
    "these",
    "this",
    "those",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
}

DATA_FILES = (
    "kb_part_rounds.json",
    "kb_finance_expanded_part2.json",
    "kb_taxonomy.json",
    "kb_web_search_results.json",
    "kb_web_search_results_2.json",
    "kb_web_search_results_3.json",
    "kb_web_search_results_4.json",
    "kb_web_search_results_5.json",
    "kb_web_search_results_6.json",
    "kb_web_sources_raw.json",
)

WEB_SECTION_DOMAIN = {
    "Business_Models_Web": ("startup", "global"),
    "Macro_Indicators_Web": ("macro", "global"),
    "Business_Risks_Web": ("startup", "global"),
    "India_VC_Ecosystem_Web": ("vc", "india"),
    "VC_Term_Sheet_Web": ("vc", "global"),
    "PE_Fund_Metrics_Web": ("finance", "global"),
    "India_Regulation_Web": ("regulation", "india"),
    "Product_Market_Fit_Web": ("startup", "global"),
    "Market_Sizing_Web": ("startup", "global"),
    "Unit_Economics_Web": ("startup", "global"),
    "ESOP_Governance_Web": ("regulation", "india"),
    "DCF_Valuation_Web": ("finance", "global"),
    "Accelerators_Web": ("startup", "global"),
    "SWF_Web": ("macro", "global"),
    "Unicorn_Decacorn_Web": ("startup", "global"),
    "India_Fintech_Infrastructure_Web": ("fintech_infra", "india"),
    "PLG_GTM_Web": ("startup", "global"),
}

RAW_SOURCE_DOMAIN = {
    "goingvc_com": ("vc", "global"),
    "dwfgroup_com": ("regulation", "global"),
    "ivca_in": ("vc", "india"),
}

TAXONOMY_LANE_MAP = {
    "Finance_Core": "finance",
    "Venture_Capital_Funds": "vc",
    "Rounds_Instruments_Terms": "vc",
    "Fund_Lifecycle_Ops": "vc",
    "Investments_Asset_Classes": "finance",
    "Entrepreneurship_Startup": "startup",
    "Business_Models": "startup",
    "Sectors_Industries": "startup",
    "Geography": "macro",
    "Regulation_Policy_Compliance": "regulation",
    "Risk": "finance",
    "Macro_Markets": "macro",
    "Data_ML_Analytics": "startup",
    "Datasets_OSINT": "startup",
    "Startup_Support_Ecosystem": "startup",
    "Governance_Legal_Docs": "regulation",
    "Content_File_Types": "startup",
    "Outcomes_Success_Failure": "startup",
    "Famous_Companies": "startup",
}

LANE_KEYWORDS = {
    "vc": {
        "vc",
        "venture",
        "investor",
        "fundraise",
        "fundraising",
        "term sheet",
        "cap table",
        "safe",
        "convertible",
        "liquidation",
        "seed",
        "series a",
        "series b",
        "pre-seed",
        "esop",
    },
    "finance": {
        "valuation",
        "finance",
        "var",
        "cvar",
        "expected shortfall",
        "duration",
        "monte carlo",
        "black scholes",
        "binomial tree",
        "credit default swap",
        "dcf",
        "discounted cash flow",
    },
    "startup": {
        "pmf",
        "product market fit",
        "gtm",
        "go to market",
        "plg",
        "saas",
        "marketplace",
        "pricing",
        "unit economics",
        "market sizing",
        "tam",
        "sam",
        "som",
        "accelerator",
        "yc",
    },
    "regulation": {
        "regulation",
        "policy",
        "compliance",
        "legal",
        "esop",
        "governance",
        "rbi",
        "sebi",
        "companies act",
    },
    "macro": {
        "macro",
        "inflation",
        "interest rate",
        "gdp",
        "sovereign wealth",
        "swf",
        "market cycle",
    },
    "fintech_infra": {
        "upi",
        "ocen",
        "account aggregator",
        "aa framework",
        "npci",
        "fintech infrastructure",
    },
}


def expert_data_dir() -> Path:
    explicit = os.environ.get("SIGNALX_EXPERT_DATA_DIR", "").strip()
    candidates = [Path(explicit)] if explicit else []
    current = Path(__file__).resolve()
    candidates.extend(
        [
            current.parents[4] / "data",
            current.parents[2] / "data",
            Path("/Users/saimihirj/Desktop/data"),
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else Path("data")


def _normalize_phrase(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("_", " ").replace("-", " ").lower()).strip()


def _to_title(value: str) -> str:
    text = value.replace("_", " ").strip()
    if text.isupper():
        return text
    return " ".join(part if part.isupper() else part.capitalize() for part in text.split())


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _normalize_phrase(value)).strip("-")


def _tokenize(text: str) -> set[str]:
    return {
        token.lower()
        for token in TOKEN_PATTERN.findall(text or "")
        if token.lower() not in STOPWORDS
    }


def _url_label(url: str) -> str:
    parsed = urlparse(url or "")
    host = parsed.netloc.lower().replace("www.", "")
    return host or (url or "source")


def _confidence_value(tier: str) -> int:
    if tier == "high":
        return 3
    if tier == "medium":
        return 2
    return 1


def _geography_bonus(preference: str, scope: str) -> int:
    pref = (preference or "auto").strip().lower()
    resolved_scope = (scope or "global").strip().lower()
    if pref in {"", "auto", "unspecified"}:
        return 2 if resolved_scope == "global" else 1
    if pref == resolved_scope:
        return 5
    if resolved_scope == "global":
        return 2
    return -2


def _build_body(fields: list[tuple[str, Any]]) -> str:
    parts: list[str] = []
    for label, value in fields:
        if not value:
            continue
        if isinstance(value, list):
            if not value:
                continue
            parts.append(f"{label}: {', '.join(str(item) for item in value)}.")
            continue
        parts.append(f"{label}: {str(value).strip()}")
    return "\n".join(parts)


def _make_card(
    *,
    title: str,
    body: str,
    domain: str,
    subdomain: str,
    tags: list[str] | None = None,
    geography_scope: str = "global",
    source_urls: list[str] | None = None,
    source_type: str = "structured_kb",
    confidence_tier: str = "medium",
    related_terms: list[str] | None = None,
) -> dict[str, Any]:
    title_text = _to_title(title)
    tag_values = [tag for tag in (tags or []) if tag]
    related_values = [term for term in (related_terms or []) if term]
    phrases = {
        _normalize_phrase(title_text),
        _normalize_phrase(title),
        *(_normalize_phrase(tag) for tag in tag_values),
        *(_normalize_phrase(term) for term in related_values),
    }
    search_terms = _tokenize(" ".join([title_text, body, *tag_values, *related_values]))
    return {
        "id": f"{domain}:{_slug(subdomain)}:{_slug(title_text)}",
        "title": title_text,
        "body": body.strip(),
        "domain": domain,
        "subdomain": _to_title(subdomain),
        "tags": sorted({tag.strip() for tag in tag_values if tag and str(tag).strip()}),
        "geographyScope": geography_scope,
        "sourceUrls": [url for url in (source_urls or []) if url],
        "sourceType": source_type,
        "confidenceTier": confidence_tier,
        "relatedTerms": sorted({term.strip() for term in related_values if term and str(term).strip()}),
        "_phrases": sorted(phrases),
        "_tokens": search_terms,
    }


def _cards_from_rounds(data: dict[str, Any]) -> list[dict[str, Any]]:
    root = data.get("Rounds_Instruments_Terms", {})
    cards: list[dict[str, Any]] = []
    for title, item in root.items():
        if not isinstance(item, dict):
            continue
        cards.append(
            _make_card(
                title=title,
                body=_build_body(
                    [
                        ("Definition", item.get("definition")),
                        ("Practical use", item.get("practical_use")),
                        ("Why it matters", item.get("why_it_matters")),
                    ]
                ),
                domain="vc",
                subdomain=item.get("category", "Rounds Instruments Terms"),
                tags=[title, item.get("category", ""), *item.get("related_terms", [])],
                source_urls=[],
                source_type="structured_kb",
                confidence_tier="high",
                related_terms=item.get("related_terms", []),
            )
        )
    return cards


def _cards_from_finance(data: dict[str, Any]) -> list[dict[str, Any]]:
    root = data.get("Finance_Expanded_Part2", {})
    cards: list[dict[str, Any]] = []
    for title, item in root.items():
        if not isinstance(item, dict):
            continue
        cards.append(
            _make_card(
                title=title,
                body=_build_body(
                    [
                        ("Definition", item.get("definition")),
                        ("Formula", item.get("formula")),
                        ("Practical use", item.get("practical_use")),
                        ("Why it matters", item.get("why_it_matters")),
                    ]
                ),
                domain="finance",
                subdomain="Finance Expanded Part 2",
                tags=[title, *item.get("related_terms", [])],
                source_urls=item.get("sources", []),
                source_type="structured_kb",
                confidence_tier="high",
                related_terms=item.get("related_terms", []),
            )
        )
    return cards


def _cards_from_web_sections(data: dict[str, Any]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for section, payload in data.items():
        if not isinstance(payload, dict):
            continue
        terms = payload.get("terms", {})
        if not isinstance(terms, dict):
            continue
        domain, geography_scope = WEB_SECTION_DOMAIN.get(section, ("startup", "global"))
        for title, summary in terms.items():
            cards.append(
                _make_card(
                    title=title,
                    body=_build_body(
                        [
                            ("Section", _to_title(section.replace("_Web", ""))),
                            ("Summary", summary),
                        ]
                    ),
                    domain=domain,
                    subdomain=section.replace("_Web", ""),
                    tags=[title, section, domain, geography_scope],
                    geography_scope=geography_scope,
                    source_urls=payload.get("sources", []),
                    source_type="curated_web_summary",
                    confidence_tier="medium",
                )
            )
    return cards


def _cards_from_raw_sources(data: dict[str, Any]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for source_key, payload in data.items():
        if not isinstance(payload, dict):
            continue
        domain, geography_scope = RAW_SOURCE_DOMAIN.get(source_key, ("startup", "global"))
        base_url = payload.get("url", "")
        title = payload.get("title", source_key)
        terms = payload.get("terms", {})
        if not isinstance(terms, dict):
            continue
        for term, summary in terms.items():
            cards.append(
                _make_card(
                    title=term,
                    body=_build_body(
                        [
                            ("Source", title),
                            ("Summary", summary),
                        ]
                    ),
                    domain=domain,
                    subdomain=title,
                    tags=[term, source_key, title, domain],
                    geography_scope=geography_scope,
                    source_urls=[base_url] if base_url else [],
                    source_type="raw_glossary",
                    confidence_tier="reference",
                )
            )
    return cards


def _flatten_taxonomy_items(node: Any) -> list[str]:
    items: list[str] = []
    if isinstance(node, list):
        for item in node:
            if isinstance(item, str):
                items.append(item)
    elif isinstance(node, dict):
        for value in node.values():
            items.extend(_flatten_taxonomy_items(value))
    return items


def _taxonomy_index(data: dict[str, Any]) -> dict[str, Any]:
    taxonomy = data.get("taxonomy", {})
    alias_map: dict[str, set[str]] = {}
    lane_tokens: dict[str, set[str]] = {lane: set() for lane in TAXONOMY_LANE_MAP.values()}
    for category, node in taxonomy.items():
        lane = TAXONOMY_LANE_MAP.get(category)
        for raw in _flatten_taxonomy_items(node):
            normalized = _normalize_phrase(raw)
            alias_map.setdefault(normalized, set()).add(category)
            if lane:
                lane_tokens.setdefault(lane, set()).update(_tokenize(raw))
                lane_tokens[lane].add(normalized)
    for raw in data.get("all_tags_flat", []):
        normalized = _normalize_phrase(str(raw))
        alias_map.setdefault(normalized, set()).add("all_tags")
    return {
        "aliasMap": {key: sorted(value) for key, value in alias_map.items()},
        "laneTokens": {key: sorted(value) for key, value in lane_tokens.items()},
    }


@lru_cache(maxsize=1)
def load_expert_corpus() -> dict[str, Any]:
    data_dir = expert_data_dir()
    loaded: dict[str, Any] = {}
    for name in DATA_FILES:
        path = data_dir / name
        if not path.exists():
            continue
        try:
            loaded[name] = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue

    cards: list[dict[str, Any]] = []
    if "kb_part_rounds.json" in loaded:
        cards.extend(_cards_from_rounds(loaded["kb_part_rounds.json"]))
    if "kb_finance_expanded_part2.json" in loaded:
        cards.extend(_cards_from_finance(loaded["kb_finance_expanded_part2.json"]))
    for name in (
        "kb_web_search_results.json",
        "kb_web_search_results_2.json",
        "kb_web_search_results_3.json",
        "kb_web_search_results_4.json",
        "kb_web_search_results_5.json",
        "kb_web_search_results_6.json",
    ):
        if name in loaded:
            cards.extend(_cards_from_web_sections(loaded[name]))
    if "kb_web_sources_raw.json" in loaded:
        cards.extend(_cards_from_raw_sources(loaded["kb_web_sources_raw.json"]))

    deduped: dict[str, dict[str, Any]] = {}
    for card in cards:
        stable_key = (card["domain"], _normalize_phrase(card["title"]))
        existing = deduped.get(stable_key)
        if existing is None or _confidence_value(card["confidenceTier"]) >= _confidence_value(existing["confidenceTier"]):
            deduped[stable_key] = card

    taxonomy_index = _taxonomy_index(loaded.get("kb_taxonomy.json", {})) if "kb_taxonomy.json" in loaded else {"aliasMap": {}, "laneTokens": {}}
    return {
        "cards": list(deduped.values()),
        "taxonomy": taxonomy_index,
        "dataDir": str(data_dir),
    }


def suggest_knowledge_lane(query: str) -> str:
    normalized = _normalize_phrase(query)
    tokens = _tokenize(query)
    corpus = load_expert_corpus()
    taxonomy_tokens = corpus.get("taxonomy", {}).get("laneTokens", {})
    scores: dict[str, int] = {lane: 0 for lane in {*LANE_KEYWORDS, *taxonomy_tokens}}
    for lane, keywords in LANE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in normalized:
                scores[lane] += 3
            if _tokenize(keyword) & tokens:
                scores[lane] += 1
    for lane, keywords in taxonomy_tokens.items():
        overlap = len(tokens & set(keywords))
        scores[lane] = scores.get(lane, 0) + overlap
    best_lane = max(scores.items(), key=lambda item: item[1])[0] if scores else "startup"
    return best_lane if scores.get(best_lane, 0) > 0 else "startup"


def retrieve_expert_cards(
    query: str,
    *,
    lane: str = "",
    geography: str = "auto",
    top_k: int = 6,
) -> list[dict[str, Any]]:
    normalized = _normalize_phrase(query)
    tokens = _tokenize(query)
    corpus = load_expert_corpus()
    cards = corpus.get("cards", [])
    preferred_lane = lane or suggest_knowledge_lane(query)
    scored: list[dict[str, Any]] = []

    for card in cards:
        overlap = len(tokens & set(card["_tokens"]))
        phrase_hits = sum(1 for phrase in card["_phrases"] if phrase and phrase in normalized)
        title_match = 1 if _normalize_phrase(card["title"]) in normalized else 0
        lane_bonus = 4 if card["domain"] == preferred_lane else 0
        geography_bonus = _geography_bonus(geography, card["geographyScope"])
        confidence_bonus = _confidence_value(card["confidenceTier"])
        score = (title_match * 16) + (phrase_hits * 6) + (overlap * 2) + lane_bonus + geography_bonus + confidence_bonus
        if score <= 0:
            continue
        scored.append(
            {
                **card,
                "score": score,
                "sourceLabel": ", ".join(_url_label(url) for url in card["sourceUrls"][:2]) or card["subdomain"],
            }
        )

    scored.sort(
        key=lambda item: (
            item["score"],
            _confidence_value(item["confidenceTier"]),
            len(item["sourceUrls"]),
            len(item["body"]),
        ),
        reverse=True,
    )
    return [
        {
            key: value
            for key, value in item.items()
            if not key.startswith("_")
        }
        for item in scored[:top_k]
    ]


def build_card_context(cards: list[dict[str, Any]], max_chars: int = 1400) -> str:
    parts: list[str] = []
    used = 0
    for card in cards:
        source_text = ", ".join(_url_label(url) for url in card.get("sourceUrls", [])[:2]) or card.get("subdomain", "")
        block = (
            f"[{card['title']} · {card['domain']} · {card['geographyScope']} · {card['confidenceTier']}]\n"
            f"{card['body']}\n"
            f"Sources: {source_text}"
        ).strip()
        separator = "\n\n" if parts else ""
        if used + len(separator) + len(block) > max_chars and parts:
            break
        parts.append(block)
        used += len(separator) + len(block)
    return "\n\n".join(parts)


def source_citations(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    citations: list[dict[str, Any]] = []
    for card in cards:
        urls = card.get("sourceUrls", []) or [""]
        for url in urls[:2]:
            key = (card["title"], url)
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                {
                    "title": card["title"],
                    "url": url,
                    "label": card.get("sourceLabel", "") or _url_label(url) or card["subdomain"],
                    "sourceType": card.get("sourceType", "kb"),
                    "geographyScope": card.get("geographyScope", "global"),
                    "confidence": card.get("confidenceTier", "medium"),
                    "domain": card.get("domain", "general"),
                }
            )
            if len(citations) >= 8:
                return citations
    return citations


def expert_card_count() -> int:
    return len(load_expert_corpus().get("cards", []))
