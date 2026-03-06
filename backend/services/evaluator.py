"""Adaptive evaluator engine for Signal."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from state import ConversationState

from backend.services.model_router import default_model_for_provider, generate_provider_text
from knowledge import get_stage_metrics_context, get_vc_pass_reasons_context, get_yc_frameworks_context


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
        "variants": {
            "stage:idea": "What problem have you spotted, and who feels it most intensely?",
            "stage:pre-revenue": "Define the problem precisely — who is the user and what exactly breaks down for them?",
            "stage:early-revenue": "Your early users came to you with a problem — what was it, stated as sharply as possible?",
            "stage:growth": "State the core problem your company exists to solve. Who is the most acute sufferer today, and what is the measurable cost to them of not solving it?",
            "founderType:student": "Tell me about the problem you've spotted — describe it like you're explaining it to someone who's never faced it.",
            "founderType:serial": "State the problem with precision — user, failure mode, measurable cost. Skip the narrative.",
        },
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
        "variants": {
            "stage:idea": "How do people deal with this today — what's the clunky workaround they're using?",
            "stage:pre-revenue": "What's the current workaround, and what does it cost them in time, money, or friction?",
            "stage:early-revenue": "When your early users found you, what were they using before? Why wasn't that good enough?",
            "stage:growth": "Map the alternative landscape — direct competitors, indirect workarounds, and the status quo. Where is the structural weakness you're exploiting?",
            "founderType:student": "How does someone deal with this problem today, even if the solution is clunky or manual?",
            "founderType:serial": "Lay out the competitive status quo. What's being used, what's the switching cost, and where is the vulnerability?",
        },
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
        "variants": {
            "stage:idea": "What's changed recently — in technology, regulation, or behavior — that makes this possible now when it wasn't 3 years ago?",
            "stage:pre-revenue": "What specific shift created the opening you're building into? And why will that shift continue?",
            "stage:early-revenue": "What made your early users ready for this now? What would have stopped them from adopting it 3 years ago?",
            "stage:growth": "What secular trend is accelerating your market — and why does your timing advantage hold against well-funded incumbents entering now?",
            "founderType:serial": "You've built before — you know timing kills companies. What's the specific inflection point that makes this window real?",
        },
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
        "variants": {
            "stage:idea": "Who is the most desperate customer for this — the one person who would pay anything for a solution?",
            "stage:pre-revenue": "Which exact type of customer are you targeting first, and why that segment over all others?",
            "stage:early-revenue": "Looking at your early users — who came back most? That's probably your beachhead. Can you describe that archetype precisely?",
            "stage:growth": "You have real customer data now — what's the single highest-value segment profile you've confirmed, and what expansion path does it unlock?",
            "founderType:student": "Picture the one person who would be most helped by this. Describe them specifically — job, situation, what they're struggling with.",
            "founderType:serial": "Define your ICP with the precision you'd put in a sales playbook — industry, company size, role, trigger event.",
        },
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
        "variants": {
            "stage:idea": "If this works perfectly, what does the user's life or work look like after using it?",
            "stage:pre-revenue": "What specific result does the user walk away with — faster, cheaper, simpler, more confident?",
            "stage:early-revenue": "What outcome are your best users actually getting? If you asked them, what's the one thing they'd say your product does for them?",
            "stage:growth": "Quantify the value you deliver to your best customers — time saved, revenue generated, cost reduced. What does your data say?",
            "founderType:student": "Imagine the user after using your product for a month. What's noticeably different about their day?",
            "founderType:serial": "State the value proposition in ROI terms. What's the measurable before-and-after for your best customer segment?",
        },
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
        "variants": {
            "stage:idea": "Even a rough estimate — how would you put a number on the value this creates for one user?",
            "stage:pre-revenue": "You don't have users yet, so estimate — what could a customer measure to know this is working? Time? Money? Error rate?",
            "stage:early-revenue": "What data do you have from early users that quantifies the impact? Even rough numbers from 3–5 users count.",
            "stage:growth": "Give me your best cohort data on customer outcomes. What's the measured improvement and how many data points back it up?",
            "founderType:student": "Can you put any number on this — even a rough estimate of time saved or money saved for one user?",
            "founderType:serial": "Show me the outcome metric. Not a qualitative claim — a before-and-after number that would hold up in a data room.",
        },
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
        "variants": {
            "stage:idea": "What's the strongest signal you have that this problem is real — even before building anything?",
            "stage:pre-revenue": "What did you learn from user conversations that convinced you this problem is painful enough to build for?",
            "stage:early-revenue": "What behavior from your early users is the most honest proof that the problem is real and acute?",
            "stage:growth": "What customer retention or revenue data most convincingly proves that this problem is recurring and worth paying to solve?",
            "founderType:student": "Have you talked to anyone who has this problem? What did they say that made you believe it's genuinely painful?",
            "founderType:serial": "What's the evidence that this is a structural market problem, not a niche edge case? What gives you confidence on the TAM?",
        },
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
        "variants": {
            "stage:idea": "What's the smallest, fastest thing you could do to find out if people actually want this?",
            "stage:pre-revenue": "What experiments have you run — landing page, manual service, prototype — to validate the idea so far?",
            "stage:early-revenue": "Walk me through how you got your first users. What did you have to promise or do manually to get them to try it?",
            "stage:growth": "How are you running product experiments now? What's your framework for deciding what to build next?",
            "founderType:student": "What's one small experiment you could run this week to test whether this is a real problem?",
            "founderType:serial": "What's your validation cadence — how quickly can you run an experiment and read a meaningful result?",
        },
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
        "variants": {
            "stage:pre-revenue": "Why would someone open their wallet for this — what pain is big enough, and what's the first thing they'd pay for?",
            "stage:early-revenue": "Are your current users paying? If not, what would it take for them to pay? If yes, what made them say yes?",
            "stage:growth": "What does your pricing architecture look like, and what data tells you that's the right number to charge?",
            "founderType:student": "If you asked someone to pay even a small amount for this right now, why would they say yes?",
            "founderType:serial": "State your pricing strategy and the data that drove it. What experiments have you run on price sensitivity?",
        },
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
        "variants": {
            "stage:pre-revenue": "Rough estimate only — what would it cost to serve one customer for a month, fully loaded?",
            "stage:early-revenue": "What does it actually cost you to deliver this to one user today — including your time, infrastructure, and support?",
            "stage:growth": "Break down your unit economics — COGS, gross margin, and where you see the biggest leverage to improve it.",
            "founderType:student": "If you had 10 paying customers tomorrow, what would you actually spend to serve each of them?",
            "founderType:serial": "Walk me through unit economics at current scale and the path to target gross margin. Where's the biggest lever?",
        },
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
        "variants": {
            "stage:idea": "What would make this meaningfully better than what exists — not 10% better, but an order of magnitude better?",
            "stage:pre-revenue": "How is this different from the alternatives — and why would a customer switch instead of staying with what they know?",
            "stage:early-revenue": "Why did your early users pick you over the alternatives? What did they say was the real reason — not your reason?",
            "stage:growth": "What's your defensible moat at this stage — switching costs, data advantages, network effects, or brand? What stops a well-funded competitor from copying you?",
            "founderType:student": "If someone built a similar product tomorrow, why would users still pick yours?",
            "founderType:serial": "Define your moat precisely. What structurally gets harder for a competitor to replicate as you scale?",
        },
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
        "variants": {
            "stage:idea": "How would you get your first 10 users — who would you call, and why would they say yes?",
            "stage:pre-revenue": "What's your plan for the first 10 customers — channel, message, and who specifically?",
            "stage:early-revenue": "How did you get your current users — and which channel is showing the most promise for the next 100?",
            "stage:growth": "What's your CAC by channel, and which acquisition channel do you have the most confidence in scaling?",
            "founderType:student": "Who would you tell about this first, and how would you convince them to try it?",
            "founderType:serial": "Walk me through your GTM motion — primary channel, CAC, and conversion economics.",
        },
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
        "variants": {
            "stage:idea": "How often would a user naturally reach for this — daily, weekly, or only during specific moments?",
            "stage:pre-revenue": "Think about your intended user's daily or weekly routine — when would this product naturally fit?",
            "stage:early-revenue": "How often are your current users coming back, and what triggers a return visit?",
            "stage:growth": "What does your DAU/WAU/MAU ratio look like, and what's the activation event that predicts long-term retention?",
            "founderType:student": "If this worked well, how often would someone use it in a week? What would bring them back?",
            "founderType:serial": "State your D1/D7/D30/D90 retention curve. What's the aha moment that separates retained users from churned ones?",
        },
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
        "variants": {
            "stage:idea": "Why are you the right person to build this — what do you know about this problem that someone else doesn't?",
            "stage:pre-revenue": "What's your unfair advantage — domain knowledge, network, technical depth, or lived experience with this problem?",
            "stage:early-revenue": "You've gotten early traction — what about you and your team made that possible in a way a well-funded competitor couldn't replicate easily?",
            "stage:growth": "What's your team composition, and what's the one hire that would most unlock your next phase of growth?",
            "founderType:student": "What drew you personally to this problem — have you experienced it yourself, or do you have deep knowledge of it from somewhere?",
            "founderType:serial": "You've built before — what's genuinely different about this team compared to your previous ventures, and why does that matter for this specific market?",
        },
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
        "variants": {
            "stage:idea": "What's the one thing you need to prove in the next 3 months to know whether this idea is worth building?",
            "stage:pre-revenue": "What milestone would tell you that you've found something real — what does that moment look like?",
            "stage:early-revenue": "What's the metric or milestone that would make a seed investor say yes — and what would it take to get there in 6 months?",
            "stage:growth": "What does the Series A milestone look like — ARR target, NRR, gross margin? What are you solving for in this round?",
            "founderType:student": "What's the one thing you'd need to prove to yourself — and to others — that this idea is worth pursuing seriously?",
            "founderType:serial": "Define the milestone this capital unlocks. What does success look like at 18 months, and what's the exit thesis from there?",
        },
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
        "variants": {
            "stage:idea": "What's the biggest reason this idea might not work — be honest with yourself?",
            "stage:pre-revenue": "What assumption in your model worries you most? If it's wrong, what happens to the business?",
            "stage:early-revenue": "What's the biggest fragility in what you've built so far — the thing that's hardest to talk about?",
            "stage:growth": "What's the existential risk at this stage — the one thing that could take this from strong growth to zero?",
            "founderType:student": "If someone tried to talk you out of this idea, what's the best argument they could make?",
            "founderType:serial": "You've seen companies fail. What pattern from those failures do you recognise in this business right now?",
        },
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
        "variants": {
            "stage:idea": "Which specific workflow are you targeting — what does the user do today that you'd make dramatically faster or easier?",
            "stage:early-revenue": "Which workflow did your early customers say improved the most — and by how much?",
            "stage:growth": "What's the measurable workflow improvement you can prove at scale — time saved, error rate reduction, or throughput increase?",
            "founderType:serial": "State the workflow ROI. What's the before-and-after that justifies the contract value?",
        },
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
        "variants": {
            "stage:pre-revenue": "What's the hardest technical problem to solve — integration, data access, security, or compliance?",
            "stage:early-revenue": "What technical or integration issue came up with your early customers that slowed them down?",
            "stage:growth": "At scale, where does your architecture or security posture become a selling risk — and how are you addressing it?",
            "founderType:serial": "What's the enterprise blocker — security review, data residency, SSO/SOC2 requirement — and what's your timeline to clear it?",
        },
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
        "variants": {
            "stage:idea": "Which side of the marketplace do you seed first — supply or demand — and why?",
            "stage:pre-revenue": "What's your cold-start strategy — how do you create enough liquidity on one side to attract the other?",
            "stage:early-revenue": "How did you crack the chicken-and-egg? What's the ratio of supply to demand you've achieved, and is it healthy?",
            "stage:growth": "What's your liquidity metric — fill rate, take rate, repeat transaction rate — and how does it benchmark against comparable marketplaces?",
            "founderType:serial": "Walk me through the liquidity flywheel. At what GMV does the marketplace become self-sustaining without acquisition spend?",
        },
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
        "variants": {
            "stage:idea": "What's the trust or regulatory barrier that could stop users from adopting this — and how do you plan to clear it?",
            "stage:pre-revenue": "What compliance requirements or user behavior changes are you building against — and have you mapped the regulatory path?",
            "stage:early-revenue": "What trust or compliance objection came up most with early users — and how did you handle it?",
            "stage:growth": "What's your regulatory posture — licenses held, audits passed, partnerships secured — and where are the remaining gaps?",
            "founderType:serial": "Map the compliance stack — what licences, certifications, and partnership agreements are required to operate at scale in your target market?",
        },
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
        "variants": {
            "stage:idea": "What's the measurable environmental outcome you're aiming for — and how would you prove it at small scale first?",
            "stage:early-revenue": "What sustainability metric have you actually measured so far — emissions avoided, waste reduced, energy saved?",
            "stage:growth": "What's your sustainability KPI and how does it compare to the incumbent's baseline? Is it audited or certified?",
            "founderType:serial": "Define the unit-level impact metric you'd report to an ESG-focused investor. What's the per-customer or per-transaction environmental delta?",
        },
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

CATEGORY_BELIEF_KEYS = {
    "Problem": "problem",
    "Market": "market",
    "Solution": "solution",
    "Traction": "traction",
    "Business Model": "business_model",
    "Team": "team",
    "Ask": "ask",
}

DEFAULT_BELIEF_STATE = {
    "problem": 0.45,
    "market": 0.45,
    "solution": 0.45,
    "traction": 0.35,
    "business_model": 0.35,
    "team": 0.45,
    "ask": 0.4,
    "evidence": 0.35,
    "quantification": 0.3,
    "clarity": 0.45,
    "logic": 0.45,
}

MARKOV_TRANSITIONS = {
    "explore": {
        "narrow": "narrow",
        "validate": "validate",
        "quantify": "quantify",
        "de-risk": "de-risk",
        "advance": "explore",
        "close": "close",
    },
    "narrow": {
        "narrow": "narrow",
        "validate": "validate",
        "quantify": "quantify",
        "de-risk": "de-risk",
        "advance": "explore",
        "close": "close",
    },
    "validate": {
        "narrow": "narrow",
        "validate": "validate",
        "quantify": "quantify",
        "de-risk": "de-risk",
        "advance": "explore",
        "close": "close",
    },
    "quantify": {
        "narrow": "narrow",
        "validate": "validate",
        "quantify": "quantify",
        "de-risk": "de-risk",
        "advance": "explore",
        "close": "close",
    },
    "de-risk": {
        "narrow": "narrow",
        "validate": "validate",
        "quantify": "quantify",
        "de-risk": "de-risk",
        "advance": "explore",
        "close": "close",
    },
    "close": {
        "narrow": "narrow",
        "validate": "validate",
        "quantify": "quantify",
        "de-risk": "de-risk",
        "advance": "close",
        "close": "close",
    },
}


def _belief_state(metadata: dict[str, Any]) -> dict[str, float]:
    state = DEFAULT_BELIEF_STATE.copy()
    for key, value in (metadata.get("beliefState") or {}).items():
        if key in state and isinstance(value, (int, float)):
            state[key] = max(0.05, min(float(value), 0.98))
    return state


def _bayesian_blend(prior: float, observed: float, strength: float) -> float:
    prior = max(0.05, min(prior, 0.95))
    observed = max(0.01, min(observed, 0.99))
    alpha = prior * 4.0
    beta = (1.0 - prior) * 4.0
    alpha += observed * strength
    beta += (1.0 - observed) * strength
    return round(alpha / max(alpha + beta, 1e-6), 4)


def _observation_label(
    question: dict[str, Any],
    scores: dict[str, float],
    contradictions: list[str],
    answer_count: int,
    budget: int,
) -> str:
    if contradictions:
        return "de-risk"
    if scores["comprehension"] < 2.5 or scores["clarity"] < 2.5:
        return "narrow"
    if scores["evidence"] < 2.5:
        return "validate"
    if question.get("expectsQuantification") or scores["quantification"] < 2.5:
        return "quantify"
    if budget - answer_count <= 2:
        return "close"
    return "advance"


def _update_belief_state(
    metadata: dict[str, Any],
    question: dict[str, Any],
    scores: dict[str, float],
    contradictions: list[str],
) -> dict[str, float]:
    beliefs = _belief_state(metadata)
    category_key = CATEGORY_BELIEF_KEYS.get(question["category"])
    question_strength = 1.2 + (WEIGHT_MULTIPLIERS[question["weightTier"]] * 1.5)
    if category_key:
        category_observation = max(0.05, min(_question_overall_score(scores, question) / 100.0, 0.99))
        beliefs[category_key] = _bayesian_blend(beliefs[category_key], category_observation, question_strength)

    for dimension in ("evidence", "quantification", "clarity", "logic"):
        beliefs[dimension] = _bayesian_blend(
            beliefs[dimension],
            max(0.05, min(scores[dimension] / 5.0, 0.99)),
            1.0 + WEIGHT_MULTIPLIERS[question["weightTier"]],
        )
    beliefs["problem"] = max(0.05, min(beliefs["problem"], 0.98))
    if contradictions:
        beliefs["logic"] = max(0.05, round(beliefs["logic"] - 0.08, 4))
        if category_key:
            beliefs[category_key] = max(0.05, round(beliefs[category_key] - 0.08, 4))

    metadata["beliefState"] = beliefs
    current_state = metadata.get("conversationState", "explore")
    observation = _observation_label(
        question,
        scores,
        contradictions,
        len(metadata.get("answers", [])),
        normalize_budget(metadata.get("questionBudget")),
    )
    metadata["conversationState"] = MARKOV_TRANSITIONS.get(current_state, MARKOV_TRANSITIONS["explore"]).get(
        observation,
        "explore",
    )
    metadata["lastObservation"] = observation
    return beliefs


def _question_context_hint(question: dict[str, Any], state: "ConversationState | None", metadata: dict[str, Any] | None) -> str:
    if metadata is None:
        return ""
    if not metadata.get("answers"):
        return ""

    beliefs = _belief_state(metadata)
    conversation_state = metadata.get("conversationState", "explore")
    category_key = CATEGORY_BELIEF_KEYS.get(question["category"], "")
    category_confidence = beliefs.get(category_key, 0.5)

    founder_type = state.founder_type if state else "unknown"

    if conversation_state == "narrow":
        if state and state.founder_type == "student":
            if question["category"] == "Problem":
                return "Answer shape: user -> pain -> current workaround."
            return "Keep it simple: one user, one problem, one concrete point."
        return "Answer narrowly and stay concrete."
    if conversation_state == "validate":
        if question["category"] == "Traction":
            return "Answer shape: who you spoke to -> what they said -> what changed."
        return "Anchor this in real behavior, not a belief."
    if conversation_state == "quantify":
        if founder_type in {"student", "professional"}:
            if question["category"] == "Business Model":
                return "Answer shape: what they pay -> what it costs -> why it works."
            return "A rough estimate is enough. Use one simple number."
        return "Use one believable number if you can."
    if conversation_state == "de-risk":
        return "Address the biggest uncertainty directly."
    if conversation_state == "close":
        return "Treat this as a make-or-break answer."

    if category_confidence < 0.42:
        if question["category"] == "Problem":
            return "Answer shape: user -> pain -> current workaround."
        if question["category"] == "Market":
            return "Answer shape: first segment -> why them -> why now."
        if question["category"] == "Solution":
            return "Answer shape: user outcome -> product -> why better."
        if question["category"] == "Traction":
            return "Answer shape: proof -> learning -> next step."
        if question["category"] == "Business Model":
            return "Answer shape: value -> price -> delivery cost."
        if question["category"] == "Team":
            return "Say why this team can win here."
        if question["category"] == "Ask":
            return "Focus on the next proof point, not the big vision."

    if founder_type in {"student", "professional"}:
        if question["category"] == "Problem":
            return "Think like a strong founder: who hurts, how often, and what breaks."
        if question["category"] == "Market":
            return "Think like a strong founder: start narrow before talking about scale."
        if question["category"] == "Solution":
            return "Think like a strong founder: outcome first, feature second."
        if question["category"] == "Traction":
            return "Think like a strong founder: proof beats opinion."
    return "Go one layer deeper."


def get_question_text(question: dict[str, Any], state: "ConversationState | None" = None) -> str:
    """Resolve the most specific question text variant for the given state.

    Priority order: stage-specific > founder-type-specific > default text.
    """
    variants = question.get("variants")
    if not variants or state is None:
        return question["text"]

    stage_key = f"stage:{state.stage}"
    if stage_key in variants:
        return variants[stage_key]

    founder_key = f"founderType:{state.founder_type}"
    if founder_key in variants:
        return variants[founder_key]

    return question["text"]


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
        "beliefState": DEFAULT_BELIEF_STATE.copy(),
        "conversationState": "explore",
        "lastObservation": "advance",
    }


def public_question(
    question: dict[str, Any],
    state: "ConversationState | None" = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base_text = get_question_text(question, state)
    return {
        "id": question["id"],
        "text": base_text,
        "baseText": base_text,
        "contextHint": _question_context_hint(question, state, metadata),
        "contextMode": metadata.get("conversationState", "explore") if metadata else "explore",
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
    beliefs = _belief_state(metadata)

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
        category_key = CATEGORY_BELIEF_KEYS.get(question["category"])
        if category_key:
            score += int((1.0 - beliefs.get(category_key, 0.5)) * 10)
        if "validation" in question["tags"]:
            score += int((1.0 - beliefs.get("evidence", 0.5)) * 8)
        if question.get("expectsQuantification"):
            score += int((1.0 - beliefs.get("quantification", 0.5)) * 10)
        if question["category"] in {"Problem", "Market", "Solution"}:
            score += int((1.0 - beliefs.get("clarity", 0.5)) * 4)
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
    stage_knowledge = get_stage_metrics_context(state.stage)
    pass_reasons = get_vc_pass_reasons_context()
    yc_benchmarks = get_yc_frameworks_context()
    system = (
        "You are Signal's evaluator grader. Score only the founder's latest answer. Return valid JSON only. "
        "Use 0 to 5 scores. Keep why and coachLine short. "
        "coachLine must be one coaching sentence, not a question, and must not include the next question.\n\n"
        "Use the following VC evaluation standards to calibrate your scoring:\n\n"
        f"{stage_knowledge[:800]}\n\n"
        f"{pass_reasons[:600]}\n\n"
        f"{yc_benchmarks[:400]}"
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


def public_progress(metadata: dict[str, Any], state: "ConversationState | None" = None) -> dict[str, Any]:
    answers = metadata.get("answers", [])
    report = build_evaluation_report(metadata)
    current_question = metadata.get("clarifyingQuestion") or QUESTION_LOOKUP.get(metadata.get("currentQuestionId", ""))
    completed = bool(metadata.get("completed"))
    return {
        "questionBudget": normalize_budget(metadata.get("questionBudget")),
        "answeredQuestions": len(answers),
        "completed": completed,
        "partial": bool(report.get("partial", False)),
        "currentQuestion": public_question(current_question, state, metadata) if current_question else None,
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
            "question": public_question(first_question, state, metadata),
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
            "question": public_question(follow_up, state, metadata),
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
        "question": get_question_text(question, state),
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
    _update_belief_state(metadata, question, combined_scores, contradictions)

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
        "question": public_question(next_question, state, metadata),
        "report": report,
    }
