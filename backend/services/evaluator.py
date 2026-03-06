"""Adaptive evaluator engine for Signal."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from state import ConversationState

from backend.services.model_router import default_model_for_provider, generate_provider_text


DIMENSION_LABELS = {
    "comprehension": "Comprehension",
    "logic": "Logic",
    "evidence": "Evidence",
    "quantification": "Quantification",
    "clarity": "Clarity",
}

WEIGHT_MULTIPLIERS = {
    "critical": 1.5,
    "important": 1.2,
    "standard": 1.0,
}

WORD_PATTERN = re.compile(r"[a-zA-Z0-9']+")
NUMBER_PATTERN = re.compile(
    r"(?:(?:\$|₹|€)\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:k|m|b|cr|crore|lakh))?|"
    r"\d+(?:\.\d+)?\s?(?:%|percent|users|customers|months|weeks|days|years|hours|minutes|pilots|tests|interviews|rupees|rs))",
    re.IGNORECASE,
)
EVIDENCE_MARKERS = (
    "interview", "survey", "pilot", "test", "tested", "prototype", "data", "feedback",
    "customer", "user", "usage", "retention", "revenue", "paid", "measured", "experiment",
)
VAGUE_MARKERS = (
    "everyone", "anyone", "a lot", "very", "really", "basically", "kind of", "sort of",
    "many people", "huge market", "all users",
)
CONTRADICTION_RULES = [
    ("no users", "paying customers", "You said there are no users, but also mentioned paying customers."),
    ("pre-revenue", "mrr", "You described the company as pre-revenue but also mentioned recurring revenue."),
]


QUESTION_BANK: list[dict[str, Any]] = [
    {
        "id": "problem_specific",
        "text": "What exact painful problem are you solving, and for whom?",
        "category": "Problem",
        "weightTier": "critical",
        "stages": ["idea", "pre-revenue", "early-revenue", "growth", "unknown"],
        "founderTypes": ["student", "professional", "founder", "serial", "unknown"],
        "sectors": ["all"],
        "tags": ["problem", "customer"],
        "expectsQuantification": False,
    },
    {
        "id": "current_workaround",
        "text": "How does that user solve this problem today without you?",
        "category": "Problem",
        "weightTier": "critical",
        "stages": ["idea", "pre-revenue", "early-revenue", "growth", "unknown"],
        "founderTypes": ["all"],
        "sectors": ["all"],
        "tags": ["problem", "workaround"],
        "expectsQuantification": False,
    },
    {
        "id": "why_now",
        "text": "Why is this the right time for this idea to exist?",
        "category": "Market",
        "weightTier": "important",
        "stages": ["idea", "pre-revenue", "early-revenue", "growth", "unknown"],
        "founderTypes": ["all"],
        "sectors": ["all"],
        "tags": ["why-now", "market"],
        "expectsQuantification": False,
    },
    {
        "id": "segment_focus",
        "text": "Which exact customer segment will you win first?",
        "category": "Market",
        "weightTier": "critical",
        "stages": ["idea", "pre-revenue", "early-revenue", "growth", "unknown"],
        "founderTypes": ["all"],
        "sectors": ["all"],
        "tags": ["segment", "customer"],
        "expectsQuantification": False,
    },
    {
        "id": "value_outcome",
        "text": "What clear result or value does the user get from using this?",
        "category": "Solution",
        "weightTier": "critical",
        "stages": ["all"],
        "founderTypes": ["all"],
        "sectors": ["all"],
        "tags": ["value", "outcome"],
        "expectsQuantification": False,
    },
    {
        "id": "quantified_outcome",
        "text": "How would you quantify that result in a believable way?",
        "category": "Traction",
        "weightTier": "critical",
        "stages": ["idea", "pre-revenue", "early-revenue", "growth", "unknown"],
        "founderTypes": ["all"],
        "sectors": ["all"],
        "tags": ["quantification", "outcome"],
        "expectsQuantification": True,
    },
    {
        "id": "validation_signal",
        "text": "What is the strongest proof that this problem is real today?",
        "category": "Traction",
        "weightTier": "critical",
        "stages": ["idea", "pre-revenue", "early-revenue", "growth", "unknown"],
        "founderTypes": ["all"],
        "sectors": ["all"],
        "tags": ["validation", "evidence"],
        "expectsQuantification": False,
    },
    {
        "id": "testing_method",
        "text": "How have you tested this idea so far, even in a rough way?",
        "category": "Traction",
        "weightTier": "important",
        "stages": ["idea", "pre-revenue", "early-revenue", "growth", "unknown"],
        "founderTypes": ["all"],
        "sectors": ["all"],
        "tags": ["validation", "testing"],
        "expectsQuantification": False,
    },
    {
        "id": "willingness_to_pay",
        "text": "Why would someone pay for this, and what might they pay for first?",
        "category": "Business Model",
        "weightTier": "critical",
        "stages": ["pre-revenue", "early-revenue", "growth", "unknown"],
        "founderTypes": ["all"],
        "sectors": ["all"],
        "tags": ["pricing", "business-model"],
        "expectsQuantification": False,
    },
    {
        "id": "cost_to_serve",
        "text": "What does it roughly cost you to deliver this to one user?",
        "category": "Business Model",
        "weightTier": "important",
        "stages": ["pre-revenue", "early-revenue", "growth", "unknown"],
        "founderTypes": ["all"],
        "sectors": ["all"],
        "tags": ["unit-economics", "cost"],
        "expectsQuantification": True,
    },
    {
        "id": "differentiation",
        "text": "Why would a customer choose this over the current alternative?",
        "category": "Solution",
        "weightTier": "critical",
        "stages": ["all"],
        "founderTypes": ["all"],
        "sectors": ["all"],
        "tags": ["differentiation", "competition"],
        "expectsQuantification": False,
    },
    {
        "id": "acquisition_path",
        "text": "How will you realistically get your first 10 users or customers?",
        "category": "Market",
        "weightTier": "important",
        "stages": ["idea", "pre-revenue", "early-revenue", "growth", "unknown"],
        "founderTypes": ["all"],
        "sectors": ["all"],
        "tags": ["go-to-market", "customer"],
        "expectsQuantification": False,
    },
    {
        "id": "usage_frequency",
        "text": "How often would the user come back to this if it works?",
        "category": "Solution",
        "weightTier": "important",
        "stages": ["all"],
        "founderTypes": ["all"],
        "sectors": ["all"],
        "tags": ["retention", "behavior"],
        "expectsQuantification": False,
    },
    {
        "id": "team_right_to_win",
        "text": "Why is your team the right one to solve this problem?",
        "category": "Team",
        "weightTier": "important",
        "stages": ["all"],
        "founderTypes": ["all"],
        "sectors": ["all"],
        "tags": ["team"],
        "expectsQuantification": False,
    },
    {
        "id": "next_milestone",
        "text": "What is the single most important next milestone for this idea?",
        "category": "Ask",
        "weightTier": "standard",
        "stages": ["all"],
        "founderTypes": ["all"],
        "sectors": ["all"],
        "tags": ["next-steps"],
        "expectsQuantification": False,
    },
    {
        "id": "key_risk",
        "text": "What is the biggest reason this idea might fail right now?",
        "category": "Ask",
        "weightTier": "important",
        "stages": ["all"],
        "founderTypes": ["all"],
        "sectors": ["all"],
        "tags": ["risk"],
        "expectsQuantification": False,
    },
    {
        "id": "saas_workflow",
        "text": "Which workflow becomes materially easier or faster for a SaaS customer?",
        "category": "Solution",
        "weightTier": "important",
        "stages": ["all"],
        "founderTypes": ["all"],
        "sectors": ["saas", "deeptech"],
        "tags": ["saas", "workflow"],
        "expectsQuantification": True,
    },
    {
        "id": "saas_technical_risk",
        "text": "What technical risk, integration issue, or data concern could block adoption?",
        "category": "Solution",
        "weightTier": "important",
        "stages": ["pre-revenue", "early-revenue", "growth", "unknown"],
        "founderTypes": ["all"],
        "sectors": ["saas", "fintech", "healthtech", "deeptech"],
        "tags": ["technical", "risk"],
        "expectsQuantification": False,
    },
    {
        "id": "marketplace_liquidity",
        "text": "How will you get both sides of the marketplace moving at the start?",
        "category": "Market",
        "weightTier": "important",
        "stages": ["idea", "pre-revenue", "early-revenue", "growth", "unknown"],
        "founderTypes": ["all"],
        "sectors": ["marketplace"],
        "tags": ["marketplace", "liquidity"],
        "expectsQuantification": False,
    },
    {
        "id": "fintech_trust",
        "text": "What trust, compliance, or behavior barrier will users need to overcome?",
        "category": "Solution",
        "weightTier": "important",
        "stages": ["all"],
        "founderTypes": ["all"],
        "sectors": ["fintech", "healthtech"],
        "tags": ["trust", "compliance"],
        "expectsQuantification": False,
    },
    {
        "id": "sustainability_signal",
        "text": "If sustainability matters here, what concrete environmental gain would you prove first?",
        "category": "Solution",
        "weightTier": "standard",
        "stages": ["all"],
        "founderTypes": ["all"],
        "sectors": ["all"],
        "tags": ["sustainability"],
        "expectsQuantification": True,
        "triggerTerms": ["climate", "carbon", "green", "sustainable", "emissions", "energy"],
    },
]

QUESTION_LOOKUP = {question["id"]: question for question in QUESTION_BANK}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokens(text: str) -> list[str]:
    return WORD_PATTERN.findall((text or "").lower())


def _text_ratio(answer: str) -> float:
    tokens = _tokens(answer)
    if not tokens:
        return 0.0
    unique = len(set(tokens))
    return unique / max(len(tokens), 1)


def _contains_any(text: str, patterns: tuple[str, ...] | list[str]) -> bool:
    lowered = (text or "").lower()
    return any(pattern in lowered for pattern in patterns)


def normalize_budget(value: int | None) -> int:
    if value in {10, 15, 20}:
        return int(value)
    return 15


def normalize_session_type(value: str | None) -> str:
    return "evaluator" if (value or "").strip().lower() == "evaluator" else "mentor"


def initial_evaluation_metadata(
    *,
    question_budget: int,
    provider: str,
    model: str,
    setup_context: str = "",
    website: dict | None = None,
) -> dict[str, Any]:
    return {
        "questionBudget": normalize_budget(question_budget),
        "provider": provider,
        "model": model,
        "setupContext": (setup_context or "").strip(),
        "website": website or {},
        "intakeComplete": False,
        "askedQuestionIds": [],
        "currentQuestionId": "",
        "answers": [],
        "completed": False,
        "partial": False,
        "startedAt": _now(),
        "completedAt": None,
    }


def public_question(question: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": question["id"],
        "text": question["text"],
        "category": question["category"],
        "weightTier": question["weightTier"],
    }


def _applicable(question: dict[str, Any], state: ConversationState, metadata: dict[str, Any]) -> bool:
    if question["stages"] != ["all"] and state.stage not in question["stages"] and "unknown" not in question["stages"]:
        return False
    if question["founderTypes"] != ["all"] and state.founder_type not in question["founderTypes"]:
        return False
    if question["sectors"] != ["all"] and state.sector not in question["sectors"]:
        return False
    trigger_terms = question.get("triggerTerms") or []
    if trigger_terms:
        source_text = " ".join(
            [
                metadata.get("setupContext", ""),
                metadata.get("website", {}).get("text", ""),
            ]
        ).lower()
        if not any(term in source_text for term in trigger_terms):
            return False
    return True


def select_next_question(state: ConversationState, metadata: dict[str, Any]) -> dict[str, Any] | None:
    asked_ids = set(metadata.get("askedQuestionIds", []))
    answers = metadata.get("answers", [])

    if len(answers) >= normalize_budget(metadata.get("questionBudget")):
        return None

    if not asked_ids and "problem_specific" in QUESTION_LOOKUP:
        question = QUESTION_LOOKUP["problem_specific"]
        if _applicable(question, state, metadata):
            return question

    weak_tags: list[str] = []
    if answers:
        last = answers[-1]
        if last.get("scores", {}).get("quantification", 0) < 2.5:
            weak_tags.append("quantification")
        if last.get("scores", {}).get("evidence", 0) < 2.5:
            weak_tags.append("validation")
        if last.get("scores", {}).get("comprehension", 0) < 2.5:
            weak_tags.append(last.get("category", "").lower())

    candidates = []
    for question in QUESTION_BANK:
        if question["id"] in asked_ids:
            continue
        if not _applicable(question, state, metadata):
            continue

        score = WEIGHT_MULTIPLIERS[question["weightTier"]] * 10
        if question["category"] in {"Problem", "Traction"} and len(answers) < 5:
            score += 6
        if state.mode == "think_it_through" and question["category"] in {"Problem", "Solution", "Market"}:
            score += 4
        if state.mode == "quick_stress_test" and question["weightTier"] == "critical":
            score += 4
        if state.sector == "saas" and any(tag in question["tags"] for tag in ("technical", "saas", "workflow")):
            score += 4
        if state.founder_type == "student" and question["category"] in {"Problem", "Solution", "Market"}:
            score += 2
        if any(tag in question["tags"] for tag in weak_tags):
            score += 8
        if state.mode == "think_it_through" and question["id"] == "key_risk" and len(answers) < 4:
            score -= 4
        if question["id"] == "next_milestone" and len(answers) < max(metadata.get("questionBudget", 15) - 2, 1):
            score -= 3
        candidates.append((score, question))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], WEIGHT_MULTIPLIERS[item[1]["weightTier"]]), reverse=True)
    return candidates[0][1]


def _deterministic_scores(question: dict[str, Any], answer: str, answers: list[dict[str, Any]]) -> dict[str, float]:
    text = (answer or "").strip()
    tokens = _tokens(text)
    length = len(tokens)
    ratio = _text_ratio(text)
    has_numbers = bool(NUMBER_PATTERN.search(text))
    has_evidence = _contains_any(text, EVIDENCE_MARKERS)
    vague_count = sum(text.lower().count(marker) for marker in VAGUE_MARKERS)

    question_keywords = [token for token in _tokens(question["text"]) if len(token) > 3]
    overlap = len(set(tokens) & set(question_keywords))
    prior_text = " ".join(item.get("answer", "") for item in answers[-3:])
    repeated = 0
    if prior_text and text:
        repeated = sum(1 for token in set(tokens) if token in prior_text.lower())

    comprehension = 1.5
    if length >= 8:
        comprehension += 1.0
    if overlap >= 2:
        comprehension += 1.2
    if overlap >= 4:
        comprehension += 0.8

    evidence = 1.5 + (2.2 if has_evidence else 0.0)
    if has_numbers and has_evidence:
        evidence += 0.8

    if question.get("expectsQuantification"):
        quantification = 4.8 if has_numbers else 1.2
    else:
        quantification = 4.0 if has_numbers else 2.8

    clarity = 1.6
    if 12 <= length <= 120:
        clarity += 1.4
    if ratio >= 0.55:
        clarity += 1.0
    if vague_count == 0:
        clarity += 0.6
    if repeated > max(4, length // 3):
        clarity -= 1.1

    logic = 2.0
    if _contains_any(text, ("because", "therefore", "so that", "which means", "as a result")):
        logic += 1.1
    if has_numbers and has_evidence:
        logic += 0.8
    if length > 40:
        logic += 0.5

    scores = {
        "comprehension": max(0.5, min(comprehension, 5.0)),
        "logic": max(0.5, min(logic, 5.0)),
        "evidence": max(0.5, min(evidence, 5.0)),
        "quantification": max(0.5, min(quantification, 5.0)),
        "clarity": max(0.5, min(clarity, 5.0)),
    }
    return scores


def _fallback_model_scores(answer: str) -> dict[str, Any]:
    has_numbers = bool(NUMBER_PATTERN.search(answer or ""))
    why = "The answer is directionally useful but still needs sharper specifics and stronger proof."
    coach = "Make one claim specific, then support it with one concrete example."
    suggestions = [
        "Name the exact user more precisely.",
        "Add one real example or proof point.",
    ]
    if not has_numbers:
        suggestions.append("Quantify one outcome with a before-and-after number.")
    return {
        "comprehension": 2.8,
        "logic": 2.8,
        "clarity": 2.8,
        "why": why,
        "coachLine": coach,
        "suggestions": suggestions,
    }


def _is_brief_answer(answer: str) -> bool:
    tokens = _tokens(answer)
    return len(tokens) <= 4 or len((answer or "").strip()) < 22


def _clarifying_follow_up(question: dict[str, Any], state: ConversationState) -> str:
    if question["category"] == "Problem":
        return "Give me one specific sentence: who has this problem, and what exactly goes wrong for them?"
    if question["category"] == "Market":
        return "Be more specific. Which exact user or buyer are you talking about?"
    if question["category"] == "Solution":
        return "Keep it concrete. What does the product actually do for the user?"
    if question["category"] == "Business Model":
        return "Say it simply: what would someone pay for, or what does it cost you to deliver?"
    if state.founder_type == "student":
        return "Give me one simple, concrete sentence with an example."
    return "Give me one more concrete sentence so I can understand this properly."


def _why_for_scores(scores: dict[str, float]) -> str:
    if scores["evidence"] < 2.5:
        return "The answer points in the right direction, but it still lacks proof from real users or behavior."
    if scores["quantification"] < 2.5:
        return "The claim may be valid, but it is not yet measured or sized clearly enough."
    if scores["clarity"] < 2.5:
        return "The answer has the right idea, but the wording is still too broad or fuzzy."
    if scores["logic"] < 2.5:
        return "The idea is understandable, but the reasoning needs to connect more clearly."
    if scores["comprehension"] < 2.5:
        return "The response only partly addressed the question that was asked."
    return "The answer is directionally strong, but it can still be sharper and more concrete."


def _suggestions_for_scores(scores: dict[str, float], question: dict[str, Any]) -> list[str]:
    suggestions: list[str] = []
    if scores["comprehension"] < 2.5:
        suggestions.append("Answer the exact question first, then add extra context.")
    if scores["evidence"] < 2.5:
        suggestions.append("Add one real proof point, observation, or example.")
    if scores["quantification"] < 2.5:
        suggestions.append("Add one number, estimate, or before-and-after comparison.")
    if scores["clarity"] < 2.5:
        suggestions.append("Use simpler, tighter wording with fewer broad claims.")
    if scores["logic"] < 2.5:
        suggestions.append("Make the cause-and-effect clearer so the argument feels stronger.")
    if not suggestions:
        suggestions.append(f"Go one level deeper on the strongest part of your answer to `{question['category']}`.")
    return suggestions[:3]


def _json_blob(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found")
    return json.loads(cleaned[start : end + 1])


async def score_answer_with_model(
    *,
    provider: str,
    model: str,
    api_key: str | None,
    state: ConversationState,
    question: dict[str, Any],
    answer: str,
    metadata: dict[str, Any],
    upload_context: str = "",
) -> dict[str, Any]:
    website_text = metadata.get("website", {}).get("text", "")
    setup_context = metadata.get("setupContext", "")
    system = (
        "You are Signal's evaluator grader. "
        "Score only the founder's latest answer. "
        "Return valid JSON only. "
        "Use 0 to 5 scores. Keep why and coachLine short. "
        "coachLine must be one coaching sentence, not a question, and must not include the next question."
    )
    prompt = f"""
Founder type: {state.founder_type}
Sector: {state.sector}
Stage: {state.stage}
Mode: {state.mode}
Category: {question['category']}
Question: {question['text']}
Founder answer: {answer}

Session setup context:
{setup_context[:420] or 'None'}

Website context:
{website_text[:650] or 'None'}

Uploaded context:
{upload_context[:420] or 'None'}

Return JSON:
{{
  "comprehension": 0-5,
  "logic": 0-5,
  "clarity": 0-5,
  "why": "one or two short sentences",
  "coachLine": "one short coaching sentence, not a question",
  "suggestions": ["short fix 1", "short fix 2", "short fix 3"]
}}
"""
    try:
        result = await generate_provider_text(
            provider=provider,
            model=model or default_model_for_provider(provider),
            api_key=api_key,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.05,
            timeout_seconds=12.0,
        )
        parsed = _json_blob(result["message"])
        return {
            "comprehension": float(parsed.get("comprehension", 2.8)),
            "logic": float(parsed.get("logic", 2.8)),
            "clarity": float(parsed.get("clarity", 2.8)),
            "why": str(parsed.get("why", "")).strip(),
            "coachLine": str(parsed.get("coachLine", "")).strip(),
            "suggestions": [str(item).strip() for item in parsed.get("suggestions", []) if str(item).strip()][:3],
            "model": result["model"],
            "provider": result["provider"],
        }
    except Exception:
        fallback = _fallback_model_scores(answer)
        return {
            **fallback,
            "model": model or default_model_for_provider(provider),
            "provider": provider,
        }


def _combine_scores(deterministic: dict[str, float], modeled: dict[str, Any]) -> dict[str, float]:
    return {
        "comprehension": round((deterministic["comprehension"] * 0.35) + (float(modeled.get("comprehension", 2.8)) * 0.65), 2),
        "logic": round((deterministic["logic"] * 0.25) + (float(modeled.get("logic", 2.8)) * 0.75), 2),
        "evidence": round(deterministic["evidence"], 2),
        "quantification": round(deterministic["quantification"], 2),
        "clarity": round((deterministic["clarity"] * 0.4) + (float(modeled.get("clarity", 2.8)) * 0.6), 2),
    }


def _coach_line_for_scores(scores: dict[str, float], state: ConversationState) -> str:
    if scores["comprehension"] < 2.5:
        line = "Answer the exact question more directly before adding extra context."
    elif scores["evidence"] < 2.5:
        line = "Add one concrete proof point, observation, or real example."
    elif scores["quantification"] < 2.5:
        line = "Add one simple number, estimate, or before-and-after comparison."
    elif scores["clarity"] < 2.5:
        line = "Tighten the answer so the user, problem, and outcome are easier to follow."
    elif scores["logic"] < 2.5:
        line = "Make the reasoning cleaner so the claim feels more believable."
    else:
        line = "Push one level deeper on the strongest proof point in that answer."

    if state.founder_type == "student" and "number" in line.lower():
        line = "Add one simple number, like time saved, money saved, or users helped."
    if state.mode == "think_it_through":
        return f"Good start. {line}"
    return line


def _question_overall_score(scores: dict[str, float], question: dict[str, Any]) -> float:
    base = sum(scores.values()) / len(scores)
    weighted = (base / 5.0) * 100.0
    if question["weightTier"] == "critical" and min(scores["comprehension"], scores["logic"]) < 2.2:
        weighted -= 8
    return max(0.0, min(round(weighted, 1), 100.0))


def _detect_contradictions(answer: str, answers: list[dict[str, Any]]) -> list[str]:
    combined = " ".join(item.get("answer", "") for item in answers[-4:]) + " " + (answer or "")
    lowered = combined.lower()
    notes = []
    for left, right, message in CONTRADICTION_RULES:
        if left in lowered and right in lowered:
            notes.append(message)
    return notes


def _category_averages(answers: list[dict[str, Any]]) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for answer in answers:
        buckets.setdefault(answer.get("category", "Other"), []).append(float(answer.get("overallScore", 0.0)))
    return {category: round(sum(values) / len(values), 1) for category, values in buckets.items() if values}


def _dimension_averages(answers: list[dict[str, Any]]) -> dict[str, float]:
    buckets: dict[str, list[float]] = {key: [] for key in DIMENSION_LABELS}
    for answer in answers:
        scores = answer.get("scores", {})
        for dimension in DIMENSION_LABELS:
            value = scores.get(dimension)
            if isinstance(value, (int, float)):
                buckets[dimension].append(float(value))
    return {
        dimension: round((sum(values) / len(values)) / 5.0 * 100.0, 1) if values else 0.0
        for dimension, values in buckets.items()
    }


def build_evaluation_report(metadata: dict[str, Any]) -> dict[str, Any]:
    answers = metadata.get("answers", [])
    budget = normalize_budget(metadata.get("questionBudget"))
    if not answers:
        return {
            "overallScore": 0.0,
            "partial": True,
            "answeredQuestions": 0,
            "questionBudget": budget,
            "dimensionScores": [],
            "why": ["No answers captured yet."],
            "suggestions": ["Start the assessment to generate a score."],
            "questions": [],
            "summary": "No evaluation yet.",
        }

    total_weight = 0.0
    weighted_sum = 0.0
    for answer in answers:
        weight = float(answer.get("weight", 1.0))
        total_weight += weight
        weighted_sum += float(answer.get("overallScore", 0.0)) * weight
    overall_score = round(weighted_sum / max(total_weight, 1.0), 1)

    dimension_scores = _dimension_averages(answers)
    category_scores = _category_averages(answers)
    sorted_dimensions = sorted(dimension_scores.items(), key=lambda item: item[1])
    weakest_dimensions = sorted_dimensions[:2]
    weakest_categories = sorted(category_scores.items(), key=lambda item: item[1])[:2]

    why: list[str] = []
    suggestions: list[str] = []
    for dimension, score in weakest_dimensions:
        if score < 60:
            why.append(f"{DIMENSION_LABELS[dimension]} is weak at {score:.0f} because answers stayed too vague or unsupported.")
    for category, score in weakest_categories:
        if score < 65:
            why.append(f"{category} is dragging the assessment because the answers did not land clearly enough.")
    for answer in sorted(answers, key=lambda item: item.get("overallScore", 0.0))[:3]:
        for suggestion in answer.get("suggestions", []):
            if suggestion not in suggestions:
                suggestions.append(suggestion)
            if len(suggestions) >= 5:
                break
        if len(suggestions) >= 5:
            break

    partial = not bool(metadata.get("completed")) or len(answers) < budget
    if partial and "Finish the remaining questions to tighten the score." not in suggestions:
        suggestions.append("Finish the remaining questions to tighten the score.")

    summary = "Promising but not yet investor-clear."
    if overall_score >= 80:
        summary = "Strong early narrative with good proof signals."
    elif overall_score >= 65:
        summary = "Directionally solid, but still needs sharper proof and precision."
    elif overall_score < 45:
        summary = "The core story is still too weak or vague to land well."

    return {
        "overallScore": overall_score,
        "partial": partial,
        "answeredQuestions": len(answers),
        "questionBudget": budget,
        "dimensionScores": [
            {"key": key, "label": DIMENSION_LABELS[key], "score": score}
            for key, score in dimension_scores.items()
        ],
        "why": why[:4] or ["The assessment needs more specific, better-supported answers."],
        "suggestions": suggestions[:5] or ["Add clearer proof, sharper quantification, and more precise user language."],
        "questions": [
            {
                "questionId": item["questionId"],
                "question": item["question"],
                "category": item["category"],
                "score": item["overallScore"],
                "why": item["why"],
                "suggestions": item["suggestions"],
            }
            for item in answers
        ],
        "summary": summary,
    }


def public_progress(metadata: dict[str, Any]) -> dict[str, Any]:
    answers = metadata.get("answers", [])
    report = build_evaluation_report(metadata)
    current_question = metadata.get("clarifyingQuestion") or QUESTION_LOOKUP.get(metadata.get("currentQuestionId", ""))
    completed = bool(metadata.get("completed"))
    return {
        "questionBudget": normalize_budget(metadata.get("questionBudget")),
        "answeredQuestions": len(answers),
        "completed": completed,
        "partial": bool(report.get("partial", False)),
        "currentQuestion": public_question(current_question) if current_question else None,
        "currentScore": report["overallScore"] if completed else 0.0,
        "dimensionScores": report["dimensionScores"] if completed else [],
        "website": metadata.get("website", {}),
        "lastFeedback": answers[-1]["reciprocal"] if answers else "",
    }


async def evaluate_answer(
    *,
    state: ConversationState,
    metadata: dict[str, Any],
    answer: str,
    provider: str,
    model: str,
    api_key: str | None,
    upload_context: str = "",
) -> dict[str, Any]:
    if not metadata.get("intakeComplete"):
        intake_bits = [metadata.get("setupContext", "").strip(), answer.strip()]
        metadata["setupContext"] = "\n\n".join(bit for bit in intake_bits if bit).strip()
        metadata["intakeComplete"] = True
        first_question = select_next_question(state, metadata)
        if first_question is None:
            metadata["completed"] = True
            metadata["completedAt"] = _now()
            return {
                "metadata": metadata,
                "question": None,
                "report": build_evaluation_report(metadata),
                "answered": {
                    "reciprocal": "I have enough context. Let me evaluate the idea and build the report.",
                },
            }
        metadata.setdefault("askedQuestionIds", []).append(first_question["id"])
        metadata["currentQuestionId"] = first_question["id"]
        return {
            "metadata": metadata,
            "question": public_question(first_question),
            "report": build_evaluation_report(metadata),
            "answered": {
                "reciprocal": "Got it. That is enough context to dive in properly.",
                "questionLabel": "First question",
            },
        }

    question_id = metadata.get("currentQuestionId", "")
    question = QUESTION_LOOKUP.get(question_id)
    if not question:
        question = select_next_question(state, metadata)
        if question is None:
            metadata["completed"] = True
            metadata["completedAt"] = _now()
            return {
                "metadata": metadata,
                "question": None,
                "report": build_evaluation_report(metadata),
            }
        metadata.setdefault("askedQuestionIds", []).append(question["id"])
        metadata["currentQuestionId"] = question["id"]

    answers = metadata.setdefault("answers", [])
    pending_prefix = metadata.pop("pendingAnswerPrefix", "").strip()
    metadata.pop("clarifyingQuestion", None)
    answer_text = " ".join(bit for bit in [pending_prefix, answer.strip()] if bit).strip()

    if _is_brief_answer(answer_text):
        follow_up = {
            "id": f"{question['id']}:followup",
            "text": _clarifying_follow_up(question, state),
            "category": question["category"],
            "weightTier": question["weightTier"],
        }
        metadata["pendingAnswerPrefix"] = answer_text
        metadata["clarifyingQuestion"] = follow_up
        return {
            "metadata": metadata,
            "answered": {
                "reciprocal": "Got it, but I need one more specific line before I move on.",
                "questionLabel": "Quick follow-up",
            },
            "question": public_question(follow_up),
            "report": build_evaluation_report(metadata),
        }

    combined_scores = _deterministic_scores(question, answer_text, answers)
    overall_score = _question_overall_score(combined_scores, question)

    reciprocal = _coach_line_for_scores(combined_scores, state)
    why = _why_for_scores(combined_scores)
    suggestions = _suggestions_for_scores(combined_scores, question)
    contradictions = _detect_contradictions(answer_text, answers)
    for note in contradictions:
        if note not in suggestions:
            suggestions.append(note)

    answered = {
        "questionId": question["id"],
        "question": question["text"],
        "category": question["category"],
        "weightTier": question["weightTier"],
        "weight": WEIGHT_MULTIPLIERS[question["weightTier"]],
        "answer": answer_text,
        "reciprocal": reciprocal.strip(),
        "why": why.strip(),
        "suggestions": suggestions[:3],
        "scores": combined_scores,
        "overallScore": overall_score,
        "answeredAt": _now(),
        "modelProvider": provider,
        "model": model or default_model_for_provider(provider),
        "contradictions": contradictions,
    }
    answers.append(answered)

    budget = normalize_budget(metadata.get("questionBudget"))
    if len(answers) >= budget:
        metadata["completed"] = True
        metadata["completedAt"] = _now()
        metadata["currentQuestionId"] = ""
        report = build_evaluation_report(metadata)
        return {
            "metadata": metadata,
            "answered": answered,
            "question": None,
            "report": report,
        }

    next_question = select_next_question(state, metadata)
    if next_question is None:
        metadata["completed"] = True
        metadata["completedAt"] = _now()
        metadata["currentQuestionId"] = ""
        report = build_evaluation_report(metadata)
        return {
            "metadata": metadata,
            "answered": answered,
            "question": None,
            "report": report,
        }

    metadata.setdefault("askedQuestionIds", []).append(next_question["id"])
    metadata["currentQuestionId"] = next_question["id"]
    report = build_evaluation_report(metadata)
    return {
        "metadata": metadata,
        "answered": answered,
        "question": public_question(next_question),
        "report": report,
    }
