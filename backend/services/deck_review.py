"""Deck review pipeline for Evaluate sessions."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from backend.services.model_router import (
    default_model_for_provider,
    empty_runtime_usage,
    generate_provider_multimodal_text,
    generate_provider_text,
    model_supports_vision,
    normalize_provider,
    normalize_usage,
    recommended_deck_model_for_provider,
)
from backend.services.uploads import load_deck_artifact


EVALUATOR_MODES = {"idea_review", "deck_review"}
DECK_TEMPLATE = [
    {
        "section": "Title Slide",
        "requirements": [
            {"label": "opening title or startup framing", "kind": "opening_title"},
            {"label": "one-line tagline or concise descriptor", "kind": "opening_tagline"},
            {"label": "team or company identity in text", "kind": "opening_identity"},
        ],
    },
    {
        "section": "Problem Statement",
        "requirements": [
            {"label": "what problem is being solved", "signals": ("problem", "pain", "challenge", "friction", "broken")},
            {"label": "who has the problem", "signals": ("customer", "user", "team", "ops", "trader", "retailer", "manager")},
            {"label": "how often or urgently it happens", "signals": ("daily", "weekly", "every", "often", "recurring", "delay", "slow")},
            {"label": "cost or pain points", "signals": ("cost", "loss", "error", "manual", "expensive", "risk", "pain point")},
        ],
    },
    {
        "section": "Existing Solutions and Competition",
        "requirements": [
            {"label": "how the problem is solved today", "signals": ("today", "status quo", "current", "manual", "workaround", "existing")},
            {"label": "gaps in current solutions", "signals": ("gap", "lack", "slow", "fragmented", "broken", "inefficient")},
            {"label": "main competitors or alternatives", "signals": ("competitor", "competition", "alternative", "incumbent", "vs")},
            {"label": "how competitors are positioned", "signals": ("position", "differentiated", "better", "faster", "cheaper", "advantage")},
        ],
    },
    {
        "section": "Customer Discovery",
        "requirements": [
            {"label": "why this customer group was chosen", "signals": ("customer", "persona", "segment", "target user", "icp")},
            {"label": "key hypotheses or assumptions", "signals": ("hypothesis", "assumption", "belief", "thesis")},
            {"label": "interviews, tests, or experiments", "signals": ("interview", "experiment", "pilot", "test", "pretotype", "discovery")},
            {"label": "pivots or insights from discovery", "signals": ("pivot", "learned", "insight", "narrowed", "lesson")},
        ],
    },
    {
        "section": "Your Solution",
        "requirements": [
            {"label": "what the solution is", "signals": ("solution", "product", "platform", "tool", "agent")},
            {"label": "how it works", "signals": ("how it works", "workflow", "engine", "process", "stack")},
            {"label": "why it is better than current options", "signals": ("better", "faster", "cheaper", "advantage", "differentiated")},
            {"label": "results for the user", "signals": ("result", "save", "reduce", "improve", "roi", "outcome")},
        ],
    },
    {
        "section": "Feasibility",
        "requirements": [
            {"label": "what is novel", "signals": ("novel", "proprietary", "unique", "innovation", "new")},
            {"label": "why the team believes it can be built", "signals": ("build", "technical", "architecture", "can build", "team can execute")},
            {"label": "why the approach is feasible now", "signals": ("why now", "available", "ready", "existing models", "infrastructure")},
        ],
    },
    {
        "section": "Market Opportunity",
        "requirements": [
            {"label": "target customers", "signals": ("customer", "buyer", "segment", "icp", "target")},
            {"label": "why the solution is desirable now", "signals": ("why now", "tailwind", "timing", "trend", "regulation")},
            {"label": "TAM, SAM, or SOM", "signals": ("tam", "sam", "som", "market size")},
            {"label": "market segmentation or 4Ps logic", "signals": ("segment", "price", "promotion", "place", "distribution")},
        ],
    },
    {
        "section": "Profit Model",
        "requirements": [
            {"label": "cost structure", "signals": ("cost", "cogs", "expense", "burn")},
            {"label": "revenue model or pricing", "signals": ("revenue", "pricing", "subscription", "transaction", "fee")},
            {"label": "why it can be profitable", "signals": ("profit", "margin", "unit economics", "gross margin")},
            {"label": "key assumptions", "signals": ("assumption", "assumes", "conversion", "retention", "take rate")},
        ],
    },
    {
        "section": "Implementation Plan",
        "requirements": [
            {"label": "high-level next steps", "signals": ("next step", "next steps", "milestone", "action plan")},
            {"label": "timeline or roadmap", "signals": ("timeline", "roadmap", "gantt", "18-month", "semester")},
            {"label": "testing or customer discovery plan", "signals": ("test", "pilot", "discovery", "validation", "experiment")},
            {"label": "why investors should back this team or idea", "signals": ("why us", "why this team", "back us", "founder-market fit")},
        ],
    },
    {
        "section": "Research and References",
        "requirements": [
            {"label": "relevant sources or citations", "signals": ("source", "reference", "citation", "research")},
            {"label": "links or external evidence", "signals": ("http://", "https://", "www.", "report", "study")},
        ],
    },
]
FOCUSED_AREAS = [
    ("customer_discovery", "Customer discovery"),
    ("competition", "Competition"),
    ("market_opportunity", "Market opportunity"),
    ("profit_model", "Profit model"),
    ("implementation_plan", "Implementation plan"),
]


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _deck_runtime(provider: str, model: str, api_key: str | None) -> tuple[str, str, str | None, bool]:
    override_provider = os.environ.get("SIFT_DECK_REVIEW_PROVIDER", "").strip()
    override_model = os.environ.get("SIFT_DECK_REVIEW_MODEL", "").strip()
    override_key = os.environ.get("SIFT_DECK_REVIEW_API_KEY", "").strip()
    if override_provider:
        deck_provider = normalize_provider(override_provider)
        deck_model = override_model or recommended_deck_model_for_provider(deck_provider) or default_model_for_provider(deck_provider, "balanced")
        return deck_provider, deck_model, override_key or None, True
    deck_provider = normalize_provider(provider)
    deck_model = model.strip() or recommended_deck_model_for_provider(deck_provider) or default_model_for_provider(deck_provider, "balanced")
    return deck_provider, deck_model, api_key, False


def normalize_evaluator_mode(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    return normalized if normalized in EVALUATOR_MODES else "idea_review"


def empty_deck_report(*, review_mode: str = "text_transcript", limitations: list[str] | None = None) -> dict[str, Any]:
    return {
        "overallScore": 0.0,
        "confidence": 0.0,
        "reviewMode": review_mode,
        "reviewLimitations": list(limitations or []),
        "verdict": "",
        "summary": "",
        "whatWorks": [],
        "weakPoints": [],
        "unprovenClaims": [],
        "storyFlow": "",
        "templateCoverage": [],
        "constraintChecks": [],
        "focusedAssessments": [],
        "slideReviews": [],
        "topFixes": [],
        "londonWhaleAssessment": "",
        "stopReason": "",
        "runtimeUsage": empty_runtime_usage()["last"],
    }


def present_deck_review_report(metadata: dict[str, Any]) -> dict[str, Any]:
    stored = metadata.get("deckReviewReport")
    if isinstance(stored, dict):
        return stored
    return empty_deck_report()


def _extract_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(text[index:])
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            continue
    return {}


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _truncate(value: str, limit: int = 700) -> str:
    cleaned = _normalize_text(value)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _slide_label(slide: dict[str, Any]) -> str:
    return slide.get("label", f"Slide {slide.get('index', '?')}")


def _all_slide_refs(slides: list[dict[str, Any]]) -> list[str]:
    return [_slide_label(slide) for slide in slides]


def _segments_for_slide(slide: dict[str, Any]) -> list[str]:
    segments: list[str] = []
    for raw_line in (slide.get("extractedText", "") or "").splitlines():
        cleaned_line = _normalize_text(raw_line).strip(" -\u2022")
        if not cleaned_line:
            continue
        pieces = re.split(r"(?<=[.;:])\s+(?=[A-Z0-9])", cleaned_line)
        for piece in pieces:
            normalized_piece = _normalize_text(piece).strip(" -\u2022")
            if normalized_piece:
                segments.append(normalized_piece)
    if not segments:
        summary = _normalize_text(slide.get("summary", ""))
        if summary:
            segments.append(summary)
    return segments[:10]


def _join_labels(labels: list[str], limit: int = 3) -> str:
    trimmed = labels[:limit]
    if not trimmed:
        return ""
    if len(trimmed) == 1:
        return trimmed[0]
    if len(trimmed) == 2:
        return f"{trimmed[0]} and {trimmed[1]}"
    return f"{', '.join(trimmed[:-1])}, and {trimmed[-1]}"


def _join_refs(refs: list[str], limit: int = 3) -> str:
    unique_refs: list[str] = []
    for ref in refs:
        if ref and ref not in unique_refs:
            unique_refs.append(ref)
    trimmed = unique_refs[:limit]
    if not trimmed:
        return ""
    if len(trimmed) == 1:
        return trimmed[0]
    if len(trimmed) == 2:
        return f"{trimmed[0]} and {trimmed[1]}"
    return f"{', '.join(trimmed[:-1])}, and {trimmed[-1]}"


def _match_opening_requirement(slides: list[dict[str, Any]], requirement: dict[str, Any]) -> dict[str, str] | None:
    if not slides:
        return None
    opening = slides[0]
    label = _slide_label(opening)
    segments = _segments_for_slide(opening)
    if not segments:
        return None

    kind = requirement.get("kind", "")
    if kind == "opening_title":
        title = segments[0]
        if _word_count(title) >= 2:
            return {"label": requirement["label"], "ref": label, "excerpt": _truncate(title, 140)}
        return None

    if kind == "opening_tagline":
        for segment in segments[1:]:
            words = _word_count(segment)
            if 3 <= words <= 16:
                return {"label": requirement["label"], "ref": label, "excerpt": _truncate(segment, 140)}
        return None

    if kind == "opening_identity":
        identity_signals = ("team", "founder", "co-founder", "company", "labs", "technologies", "ventures", "capital")
        for segment in segments[1:]:
            lowered = segment.lower()
            if any(signal in lowered for signal in identity_signals):
                return {"label": requirement["label"], "ref": label, "excerpt": _truncate(segment, 140)}
        return None

    return None


def _match_requirement(slides: list[dict[str, Any]], requirement: dict[str, Any]) -> dict[str, str] | None:
    if requirement.get("kind", "").startswith("opening_"):
        return _match_opening_requirement(slides, requirement)

    signals = tuple(str(signal).lower() for signal in requirement.get("signals", ()))
    best_match: dict[str, Any] | None = None
    for slide in slides:
        label = _slide_label(slide)
        for segment in _segments_for_slide(slide):
            lowered = segment.lower()
            score = sum(1 for signal in signals if signal in lowered)
            if score <= 0:
                continue
            candidate = {
                "label": requirement["label"],
                "ref": label,
                "excerpt": _truncate(segment, 160),
                "score": score,
                "length": len(segment),
            }
            if (
                best_match is None
                or candidate["score"] > best_match["score"]
                or (candidate["score"] == best_match["score"] and candidate["length"] < best_match["length"])
            ):
                best_match = candidate
    if best_match is None:
        return None
    return {
        "label": best_match["label"],
        "ref": best_match["ref"],
        "excerpt": best_match["excerpt"],
    }


def _match_template_section(slides: list[dict[str, Any]], section: dict[str, Any]) -> dict[str, Any]:
    requirements = section.get("requirements", [])
    matches = [match for requirement in requirements if (match := _match_requirement(slides, requirement))]
    found_labels = [match["label"] for match in matches]
    missing_labels = [requirement["label"] for requirement in requirements if requirement["label"] not in found_labels]
    refs = list(dict.fromkeys(match["ref"] for match in matches))
    evidence = [f"{match['ref']}: {match['excerpt']}" for match in matches[:3]]

    if not requirements:
        status = "missing"
    else:
        coverage_ratio = len(matches) / max(len(requirements), 1)
        if coverage_ratio >= 0.75 and len(missing_labels) <= 1:
            status = "covered"
        elif matches:
            status = "partial"
        else:
            status = "missing"

    if status == "covered":
        note = f"Covers {_join_labels(found_labels)} on {_join_refs(refs)}."
        if missing_labels:
            note += f" Still unclear on {_join_labels(missing_labels, 2)}."
    elif status == "partial":
        note = f"Shows {_join_labels(found_labels)} on {_join_refs(refs)}, but still misses {_join_labels(missing_labels)}."
    else:
        note = f"Not shown clearly. Still missing {_join_labels(missing_labels)}."
    return {
        "section": section["section"],
        "status": status,
        "note": note,
        "refs": refs[:4],
        "evidence": evidence,
        "missingItems": missing_labels[:4],
    }


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text or ""))


def _paragraph_like_lines(text: str) -> int:
    return sum(1 for line in (text or "").splitlines() if _word_count(line) >= 18)


def _build_constraint_checks(
    slides: list[dict[str, Any]],
    *,
    review_mode: str,
    limitations: list[str],
    template_coverage: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    slide_count = len(slides)
    total_words = sum(_word_count(slide.get("extractedText", "")) for slide in slides)
    avg_words = total_words / max(slide_count, 1)
    paragraph_heavy = [slide for slide in slides if _paragraph_like_lines(slide.get("extractedText", "")) >= 2]
    covered_count = sum(1 for item in template_coverage if item["status"] == "covered")
    missing_count = sum(1 for item in template_coverage if item["status"] == "missing")

    checks = [
        {
            "key": "slide_limit",
            "label": "Slide limit",
            "status": "pass" if slide_count <= 9 else "fail",
            "note": f"The deck has {slide_count} slide/page units. The constraint is max 9 including title.",
            "refs": _all_slide_refs(slides[:9]),
        },
        {
            "key": "concision",
            "label": "Concision",
            "status": "pass" if avg_words <= 65 else ("partial" if avg_words <= 95 else "fail"),
            "note": f"Average extracted density is about {int(avg_words)} words per slide/page.",
            "refs": _all_slide_refs(slides[:4]),
        },
        {
            "key": "paragraph_density",
            "label": "Paragraph heaviness",
            "status": "pass" if not paragraph_heavy else ("partial" if len(paragraph_heavy) <= 2 else "fail"),
            "note": "Dense text was detected on " + ", ".join(_slide_label(slide) for slide in paragraph_heavy[:4]) if paragraph_heavy else "The extracted text does not look overly paragraph-heavy.",
            "refs": [_slide_label(slide) for slide in paragraph_heavy[:4]],
        },
        {
            "key": "visual_clarity",
            "label": "Visual clarity",
            "status": "reviewed" if review_mode == "multimodal" else "unverified",
            "note": "Reviewed with slide images." if review_mode == "multimodal" else "Visual layout was not assessed directly in this run.",
            "refs": _all_slide_refs(slides[:3]),
        },
        {
            "key": "presentation_readiness",
            "label": "Presentation readiness",
            "status": "pass" if covered_count >= 6 and missing_count <= 1 and avg_words <= 80 else ("partial" if covered_count >= 4 else "fail"),
            "note": "This is based on coverage, density, and whether key sections are still missing.",
            "refs": [],
        },
    ]
    if limitations:
        checks[-1]["note"] += " Current review limitations were also applied."
    return checks


def _score_deck(template_coverage: list[dict[str, Any]], constraint_checks: list[dict[str, Any]]) -> float:
    coverage_points = 0.0
    for item in template_coverage:
        if item["status"] == "covered":
            coverage_points += 1.0
        elif item["status"] == "partial":
            coverage_points += 0.5
    constraint_points = 0.0
    for item in constraint_checks:
        if item["status"] in {"pass", "reviewed"}:
            constraint_points += 1.0
        elif item["status"] in {"partial", "unverified"}:
            constraint_points += 0.5
    coverage_score = (coverage_points / max(len(template_coverage), 1)) * 75
    constraint_score = (constraint_points / max(len(constraint_checks), 1)) * 25
    return round(min(100.0, coverage_score + constraint_score), 1)


def _confidence_for_mode(review_mode: str, slide_count: int) -> float:
    base = 78.0 if review_mode == "multimodal" else 61.0
    if slide_count <= 0:
        return 18.0
    return round(min(96.0, base + min(slide_count, 9) * 1.2), 1)


def _deck_review_mode(provider: str, model: str, artifact: dict[str, Any]) -> tuple[str, list[str]]:
    limitations = list(artifact.get("limitations", []))
    supports_visual = model_supports_vision(provider, model)
    has_renderable = bool(artifact.get("hasRenderableSlides", False)) and any(slide.get("imagePath") for slide in artifact.get("slides", []))
    if supports_visual and has_renderable:
        return "multimodal", limitations
    if not supports_visual:
        limitations.append("The active model is text-only for this run, so the review is limited to extracted deck text.")
    if not has_renderable:
        limitations.append("Slide images were not available for this file format in this environment.")
    return "text_transcript", limitations


def _slide_outline(slides: list[dict[str, Any]]) -> str:
    parts = []
    for slide in slides:
        parts.append(
            f"{_slide_label(slide)}\nSummary: {_truncate(slide.get('summary', ''), 180)}\nText:\n{_truncate(slide.get('extractedText', ''), 850)}"
        )
    return "\n\n".join(parts)


def _focus_seed(template_coverage: list[dict[str, Any]], constraints: list[dict[str, Any]]) -> str:
    return json.dumps(
        {
            "templateCoverage": template_coverage,
            "constraintChecks": constraints,
            "focusedAreas": FOCUSED_AREAS,
        },
        indent=2,
    )


def _review_system_prompt(review_mode: str) -> str:
    visual_rule = (
        "You saw ordered slide images and extracted text. Make visual clarity judgments only when the image evidence supports them."
        if review_mode == "multimodal"
        else "You only have extracted deck text. Do not pretend you saw layout, charts, color, or visual polish."
    )
    return (
        "You are a sharp but fair startup pitch-deck reviewer. "
        "Review decks like an experienced mentor or investor judge, using the actual deck as evidence. "
        "Be natural, direct, and practical. No fake encouragement. No generic startup filler. "
        "Do not guess. If something is missing, say not shown, unclear, or unverified. "
        "Blend the user's rubric with public deck heuristics inspired by YC, Sequoia, Peak XV, and Accel-style guidance, "
        "but do not claim you are using their private internal scorecards. "
        f"{visual_rule} "
        "Return valid JSON only."
    )


def _review_user_prompt(
    artifact: dict[str, Any],
    *,
    review_mode: str,
    limitations: list[str],
    template_coverage: list[dict[str, Any]],
    constraint_checks: list[dict[str, Any]],
    user_context: str,
) -> str:
    context_block = _truncate(user_context, 900) if user_context else ""
    instructions = [
        "Review this startup pitch deck against the required template and constraints.",
        "The output must stay evidence-grounded and reference slides/pages when possible.",
        "Use labels like Deck-level or Not shown when there is no precise slide reference.",
        "Do not invent TAM, traction, interviews, implementation detail, or competition if the deck does not show them.",
        "If the London Whale hook is not present in the deck or user context, say it is not shown instead of forcing commentary.",
        "For each focused area, return status as strong, partial, missing, or unverified.",
        "For each slide review, keep it concise and specific.",
        "JSON shape:",
        json.dumps(
            {
                "verdict": "string",
                "summary": "string",
                "whatWorks": ["string with slide/page or Deck-level reference"],
                "weakPoints": ["string with slide/page or Not shown reference"],
                "unprovenClaims": ["string with slide/page or Not shown reference"],
                "storyFlow": "string",
                "focusedAssessments": [
                    {"key": "customer_discovery", "label": "Customer discovery", "status": "partial", "assessment": "string", "refs": ["Slide 4"]}
                ],
                "slideReviews": [
                    {
                        "index": 1,
                        "label": "Slide 1",
                        "summary": "string",
                        "whatWorks": ["string"],
                        "issues": ["string"],
                        "suggestions": ["string"],
                        "refs": ["Slide 1"],
                    }
                ],
                "topFixes": ["string"],
                "londonWhaleAssessment": "string",
            },
            indent=2,
        ),
        f"Review mode: {review_mode}",
        f"Known limitations: {json.dumps(limitations)}",
        "Deterministic template and constraint scan:",
        _focus_seed(template_coverage, constraint_checks),
        "Ordered deck content:",
        _slide_outline(artifact.get("slides", [])),
    ]
    if context_block:
        instructions.extend(["Extra user context:", context_block])
    return "\n\n".join(part for part in instructions if part)


def _fallback_focused_assessments(template_coverage: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lookup = {item["section"]: item for item in template_coverage}
    mapping = {
        "customer_discovery": lookup.get("Customer Discovery"),
        "competition": lookup.get("Existing Solutions and Competition"),
        "market_opportunity": lookup.get("Market Opportunity"),
        "profit_model": lookup.get("Profit Model"),
        "implementation_plan": lookup.get("Implementation Plan"),
    }
    items = []
    for key, label in FOCUSED_AREAS:
        coverage = mapping.get(key)
        status = "missing"
        note = "Not shown clearly."
        refs: list[str] = []
        if coverage:
            status = coverage["status"]
            note = coverage["note"]
            refs = coverage["refs"]
        items.append({"key": key, "label": label, "status": status, "assessment": note, "refs": refs[:3]})
    return items


def _fallback_slide_reviews(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = []
    for slide in slides:
        label = _slide_label(slide)
        text = slide.get("extractedText", "")
        summary = _truncate(text or f"{label} has little extracted text.", 220)
        issues = []
        suggestions = []
        if not text.strip():
            issues.append(f"{label}: extracted text is minimal, so the claim content is hard to judge.")
            suggestions.append(f"{label}: add a clearer headline and one concrete proof point.")
        elif _word_count(text) > 110:
            issues.append(f"{label}: the slide looks dense in text and likely needs tightening.")
            suggestions.append(f"{label}: cut this to the few bullets the audience must remember.")
        else:
            suggestions.append(f"{label}: keep one sharper proof point or number visible.")
        items.append(
            {
                "index": int(slide.get("index", 0) or 0),
                "label": label,
                "summary": summary,
                "whatWorks": [f"{label}: the extracted content is at least readable and scoped."] if text.strip() else [],
                "issues": issues,
                "suggestions": suggestions,
                "refs": [label],
            }
        )
    return items


def _fallback_review_payload(
    artifact: dict[str, Any],
    *,
    review_mode: str,
    limitations: list[str],
    template_coverage: list[dict[str, Any]],
    constraint_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    slides = artifact.get("slides", [])
    missing = [item["section"] for item in template_coverage if item["status"] == "missing"]
    score = _score_deck(template_coverage, constraint_checks)
    return {
        "verdict": "Promising raw material, but the deck is not pitch-ready yet." if score >= 45 else "Too many key sections are still missing or under-proven.",
        "summary": "This review is evidence-bounded. The deck has useful material, but several sections are still too thin to carry a serious investor-style story.",
        "whatWorks": [
            f"Deck-level: the deck stays within a recognizable startup-story structure across {len(slides)} slides/pages."
        ],
        "weakPoints": [f"Not shown: {section} is still missing or too thin in the current deck." for section in missing[:4]],
        "unprovenClaims": ["Deck-level: strong claims should be backed by interviews, traction, benchmarks, or citations inside the deck."],
        "storyFlow": "The story reads in order, but several transitions still feel like assertions instead of earned proof.",
        "focusedAssessments": _fallback_focused_assessments(template_coverage),
        "slideReviews": _fallback_slide_reviews(slides),
        "topFixes": [
            "Tighten the story to one clear user, one painful problem, and one concrete value claim.",
            "Show evidence for customer discovery instead of implying it.",
            "Make competition and status-quo gaps explicit.",
            "Reduce text density and turn paragraphs into sharper bullets or visuals.",
            "Make the implementation plan concrete with milestones, testing, and timing.",
        ],
        "londonWhaleAssessment": "Not shown in the current deck or context, so there is nothing to assess yet.",
        "runtimeUsage": empty_runtime_usage()["last"],
    }


def _normalize_model_review(raw: dict[str, Any], slides: list[dict[str, Any]], template_coverage: list[dict[str, Any]]) -> dict[str, Any]:
    focused_defaults = {key: label for key, label in FOCUSED_AREAS}
    focused = []
    for key, label in FOCUSED_AREAS:
        item = next((entry for entry in raw.get("focusedAssessments", []) if entry.get("key") == key), {})
        focused.append(
            {
                "key": key,
                "label": label,
                "status": str(item.get("status", "missing") or "missing"),
                "assessment": str(item.get("assessment", "") or ""),
                "refs": [str(ref) for ref in item.get("refs", []) if str(ref).strip()],
            }
        )

    slide_lookup = {int(slide.get("index", 0) or 0): slide for slide in slides}
    slide_reviews = []
    for slide in slides:
        index = int(slide.get("index", 0) or 0)
        item = next((entry for entry in raw.get("slideReviews", []) if int(entry.get("index", 0) or 0) == index), {})
        label = str(item.get("label", _slide_label(slide)) or _slide_label(slide))
        slide_reviews.append(
            {
                "index": index,
                "label": label,
                "summary": str(item.get("summary", "") or ""),
                "whatWorks": [str(value) for value in item.get("whatWorks", []) if str(value).strip()],
                "issues": [str(value) for value in item.get("issues", []) if str(value).strip()],
                "suggestions": [str(value) for value in item.get("suggestions", []) if str(value).strip()],
                "refs": [str(ref) for ref in item.get("refs", []) if str(ref).strip()] or [label],
            }
        )

    return {
        "verdict": str(raw.get("verdict", "") or ""),
        "summary": str(raw.get("summary", "") or ""),
        "whatWorks": [str(value) for value in raw.get("whatWorks", []) if str(value).strip()],
        "weakPoints": [str(value) for value in raw.get("weakPoints", []) if str(value).strip()],
        "unprovenClaims": [str(value) for value in raw.get("unprovenClaims", []) if str(value).strip()],
        "storyFlow": str(raw.get("storyFlow", "") or ""),
        "focusedAssessments": focused,
        "slideReviews": slide_reviews,
        "topFixes": [str(value) for value in raw.get("topFixes", []) if str(value).strip()],
        "londonWhaleAssessment": str(raw.get("londonWhaleAssessment", "") or ""),
        "runtimeUsage": normalize_usage(raw.get("runtimeUsage")),
    }


async def review_deck_session(
    *,
    session_id: str,
    provider: str,
    model: str,
    api_key: str | None = None,
    user_context: str = "",
) -> dict[str, Any]:
    artifact = load_deck_artifact(session_id)
    if artifact is None:
        raise RuntimeError("Upload a PDF or PPTX deck before running deck review.")

    review_provider, review_model, review_api_key, runtime_overridden = _deck_runtime(provider, model, api_key)
    slides = artifact.get("slides", [])
    review_mode, limitations = _deck_review_mode(review_provider, review_model, artifact)
    if runtime_overridden:
        limitations.append(f"Deck review used {review_provider} / {review_model} instead of the session chat model.")
    template_coverage = [_match_template_section(slides, section) for section in DECK_TEMPLATE]
    constraint_checks = _build_constraint_checks(
        slides,
        review_mode=review_mode,
        limitations=limitations,
        template_coverage=template_coverage,
    )
    score = _score_deck(template_coverage, constraint_checks)
    confidence = _confidence_for_mode(review_mode, len(slides))

    review_prompt = _review_user_prompt(
        artifact,
        review_mode=review_mode,
        limitations=limitations,
        template_coverage=template_coverage,
        constraint_checks=constraint_checks,
        user_context=user_context,
    )

    raw_review: dict[str, Any] = {}
    response_usage = empty_runtime_usage()["last"]
    max_tokens = _env_int("SIFT_DECK_REVIEW_MAX_TOKENS", 2600)
    timeout_seconds = _env_float("SIFT_DECK_REVIEW_TIMEOUT_SECONDS", 52.0)
    try:
        if review_mode == "multimodal":
            image_paths = [slide.get("imagePath", "") for slide in slides if slide.get("imagePath")]
            response = await generate_provider_multimodal_text(
                provider=review_provider,
                model=review_model,
                system=_review_system_prompt(review_mode),
                prompt=review_prompt,
                image_paths=image_paths[:9],
                api_key=review_api_key,
                max_tokens=max_tokens,
                temperature=0.2,
                timeout_seconds=timeout_seconds,
            )
        else:
            response = await generate_provider_text(
                provider=review_provider,
                model=review_model,
                system=_review_system_prompt(review_mode),
                messages=[{"role": "user", "content": review_prompt}],
                api_key=review_api_key,
                max_tokens=max_tokens,
                temperature=0.2,
                timeout_seconds=timeout_seconds,
            )
        response_usage = normalize_usage(response.get("usage"))
        raw_review = _extract_json_object(response.get("message", ""))
    except Exception:
        raw_review = {}

    if not raw_review:
        raw_review = _fallback_review_payload(
            artifact,
            review_mode=review_mode,
            limitations=limitations,
            template_coverage=template_coverage,
            constraint_checks=constraint_checks,
        )

    normalized = _normalize_model_review(raw_review, slides, template_coverage)
    return {
        "overallScore": score,
        "confidence": confidence,
        "reviewProvider": review_provider,
        "reviewModel": review_model,
        "reviewMode": review_mode,
        "reviewLimitations": limitations,
        "verdict": normalized["verdict"] or ("Promising but not fully pitch-ready." if score >= 45 else "Still too under-proven for a strong deck."),
        "summary": normalized["summary"] or "This review stayed inside the actual deck evidence and flagged what is still missing.",
        "whatWorks": normalized["whatWorks"],
        "weakPoints": normalized["weakPoints"],
        "unprovenClaims": normalized["unprovenClaims"],
        "storyFlow": normalized["storyFlow"] or "The story flow needs stronger proof handoffs between slides.",
        "templateCoverage": template_coverage,
        "constraintChecks": constraint_checks,
        "focusedAssessments": normalized["focusedAssessments"] or _fallback_focused_assessments(template_coverage),
        "slideReviews": normalized["slideReviews"] or _fallback_slide_reviews(slides),
        "topFixes": normalized["topFixes"][:5],
        "londonWhaleAssessment": normalized["londonWhaleAssessment"] or "Not shown in the current deck or context.",
        "stopReason": "Deck review complete.",
        "runtimeUsage": response_usage,
    }


async def answer_deck_follow_up(
    *,
    session_id: str,
    report: dict[str, Any],
    question: str,
    provider: str,
    model: str,
    api_key: str | None = None,
) -> dict[str, Any]:
    artifact = load_deck_artifact(session_id)
    if artifact is None:
        return {"message": "There is no deck artifact available in this session yet.", "runtimeUsage": empty_runtime_usage()["last"]}

    prompt = "\n\n".join(
        [
            "Answer the user's follow-up about the reviewed deck.",
            "Stay evidence-grounded. Cite slide/page labels when you can. If the answer is not in the deck, say not shown or unverified.",
            f"Review mode: {report.get('reviewMode', 'text_transcript')}",
            "Deck report summary:",
            _truncate(json.dumps(report, ensure_ascii=True), 3500),
            "Ordered deck outline:",
            _slide_outline(artifact.get("slides", [])),
            f"User follow-up: {question.strip()}",
        ]
    )
    response = await generate_provider_text(
        provider=provider,
        model=model,
        system=(
            "You are continuing a deck review conversation. "
            "Be direct, calm, and specific. Do not guess. Do not rewrite the whole deck unless asked."
        ),
        messages=[{"role": "user", "content": prompt}],
        api_key=api_key,
        max_tokens=900,
        temperature=0.25,
        timeout_seconds=75.0,
    )
    return {
        "message": (response.get("message", "") or "").strip(),
        "runtimeUsage": normalize_usage(response.get("usage")),
    }
