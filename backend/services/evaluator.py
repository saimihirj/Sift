"""Adaptive evaluator engine for SignalX."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from state import ConversationState

from backend.services.model_router import default_model_for_provider, generate_provider_text, normalize_provider
from backend.services.refinement import (
    detect_evidence_balance,
    empty_answer_record,
    refine_founder_input,
    summarize_answer_record,
    update_answer_record,
)
from knowledge import VC_STAGE_MAP, get_stage_metrics_context, get_vc_pass_reasons_context, get_yc_frameworks_context


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

CLARIFICATION_REQUEST_CUES = (
    "clarify",
    "what do you mean",
    "what does that mean",
    "can you explain",
    "explain the question",
    "repeat the question",
    "rephrase the question",
    "say that simply",
    "simplify the question",
    "i don't understand the question",
    "i dont understand the question",
    "not sure what you mean",
)

DEFAULT_MAX_QUESTIONS = 12
DEEPER_QUESTION_BATCH = 3
REPORT_NARRATIVE_VERSION = 2

LENS_CONFIG: dict[str, dict[str, Any]] = {
    "founder_product_fit": {
        "label": "Founder-product fit",
        "group": "core",
        "weight": 1.35,
        "priority": 10,
        "why": "This judges whether the founder has a credible right to solve this problem.",
        "fix": "Show why this team understands the problem unusually well and can win here.",
    },
    "one_sentence_pitch": {
        "label": "One-sentence pitch",
        "group": "core",
        "weight": 1.35,
        "priority": 10,
        "why": "This checks whether the idea can be stated clearly in one tight sentence.",
        "fix": "State the user, the pain, and the outcome in one sharp line.",
    },
    "growth_readiness": {
        "label": "Growth / proof readiness",
        "group": "core",
        "weight": 1.35,
        "priority": 10,
        "why": "This asks whether the company has enough proof to justify the next phase.",
        "fix": "Show the next real proof point that makes the idea more investable.",
    },
    "user_problem": {
        "label": "User pain",
        "group": "supporting",
        "weight": 1.0,
        "priority": 9,
        "why": "This checks whether the user and the pain are concrete enough.",
        "fix": "Name the exact user, what breaks, and the current workaround.",
    },
    "icp_wedge": {
        "label": "ICP / wedge",
        "group": "supporting",
        "weight": 0.95,
        "priority": 8,
        "why": "This checks whether the first customer wedge is focused and believable.",
        "fix": "Start narrower. Name the first segment and why they will care first.",
    },
    "proof_validation": {
        "label": "Proof / validation",
        "group": "supporting",
        "weight": 1.05,
        "priority": 9,
        "why": "This checks whether the idea is grounded in observed behavior rather than opinion.",
        "fix": "Add proof from interviews, pilots, usage, or one measured result.",
    },
    "business_model": {
        "label": "Business model",
        "group": "supporting",
        "weight": 0.9,
        "priority": 7,
        "why": "This checks whether there is a believable path to getting paid and serving customers.",
        "fix": "Explain what gets paid for, what it costs to deliver, and why the unit works.",
    },
    "why_now": {
        "label": "Why now",
        "group": "supporting",
        "weight": 0.75,
        "priority": 6,
        "why": "This checks whether there is a real timing reason for the company to exist now.",
        "fix": "Name the shift in behavior, technology, or regulation that creates the opening.",
    },
    "execution_risk": {
        "label": "Execution risk",
        "group": "supporting",
        "weight": 0.75,
        "priority": 6,
        "why": "This checks whether the biggest blocker and next proof milestone are understood.",
        "fix": "Be direct about the biggest risk and the next milestone that would reduce it.",
    },
}

CORE_LENSES = ["founder_product_fit", "one_sentence_pitch", "growth_readiness"]
SUPPORTING_LENSES = ["user_problem", "icp_wedge", "proof_validation", "business_model", "why_now", "execution_risk"]

INVESTOR_LENS_BONUS: dict[str, dict[str, int]] = {
    "pre_seed_seed": {
        "founder_product_fit": 4,
        "one_sentence_pitch": 4,
        "user_problem": 3,
        "proof_validation": 2,
        "icp_wedge": 2,
        "why_now": 2,
        "business_model": -2,
    },
    "early_stage": {
        "founder_product_fit": 2,
        "one_sentence_pitch": 2,
        "growth_readiness": 2,
        "proof_validation": 3,
        "icp_wedge": 2,
        "business_model": 1,
        "why_now": 1,
    },
    "multi_stage": {
        "growth_readiness": 3,
        "proof_validation": 2,
        "business_model": 2,
        "execution_risk": 2,
        "why_now": 1,
    },
    "growth_late": {
        "growth_readiness": 5,
        "business_model": 4,
        "proof_validation": 3,
        "execution_risk": 3,
        "one_sentence_pitch": 1,
        "user_problem": -1,
    },
}

INVESTOR_QUESTION_BONUS: dict[str, dict[str, int]] = {
    "pre_seed_seed": {
        "one_sentence_pitch": 16,
        "problem_specific": 14,
        "current_workaround": 12,
        "segment_focus": 10,
        "testing_method": 10,
        "team_right_to_win": 10,
        "why_now": 8,
        "next_milestone": 8,
        "quantified_outcome": -4,
        "cost_to_serve": -8,
        "usage_frequency": -6,
    },
    "early_stage": {
        "one_sentence_pitch": 10,
        "validation_signal": 14,
        "segment_focus": 10,
        "willingness_to_pay": 10,
        "acquisition_path": 8,
        "testing_method": 8,
        "team_right_to_win": 8,
        "next_milestone": 6,
        "cost_to_serve": 4,
    },
    "multi_stage": {
        "quantified_outcome": 12,
        "validation_signal": 10,
        "acquisition_path": 10,
        "cost_to_serve": 8,
        "willingness_to_pay": 6,
        "differentiation": 8,
        "key_risk": 6,
        "next_milestone": 6,
    },
    "growth_late": {
        "quantified_outcome": 16,
        "usage_frequency": 14,
        "acquisition_path": 12,
        "cost_to_serve": 12,
        "key_risk": 10,
        "differentiation": 8,
        "next_milestone": 8,
        "problem_specific": -4,
        "current_workaround": -4,
    },
}


QUESTION_BANK: list[dict[str, Any]] = [
    {
        "id": "one_sentence_pitch",
        "text": "Give me the one-sentence pitch. What are you building, for whom, and what changes for them?",
        "variants": {
            "stage:idea": "Give me the one-line version of the idea. Who is it for, what pain does it remove, and why would they care?",
            "stage:pre-revenue": "In one sentence, explain the company clearly enough that a smart outsider would understand the user, pain, and value.",
            "stage:early-revenue": "State the company in one sentence: user, pain, and measurable value.",
            "stage:growth": "Give me the crisp investor version: customer, pain, product, and outcome in one line.",
            "founderType:student": "Say it simply in one sentence: who is this for, what problem does it solve, and what gets better?",
            "founderType:serial": "Compress the company into one sentence. Make it investor-clean.",
        },
        "category": "Pitch",
        "weightTier": "critical",
        "stages": ["all"],
        "founderTypes": ["all"],
        "sectors": ["all"],
        "tags": ["pitch", "clarity"],
        "expectsQuantification": False,
    },
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
        "id": "antler_founder_spike",
        "text": "What is your founder spike, and what concrete evidence proves it?",
        "variants": {
            "founderType:student": "What is the strongest thing about you as a founder here, and what has happened in your life or work that proves it?",
            "founderType:serial": "State the founder spike precisely. What have you done before that makes you unusually credible here?",
        },
        "category": "Team",
        "weightTier": "critical",
        "stages": ["all"],
        "founderTypes": ["all"],
        "sectors": ["all"],
        "tags": ["antler", "founder spike", "team", "differentiation"],
        "triggerTerms": ["antler"],
        "expectsQuantification": False,
    },
    {
        "id": "antler_coachability",
        "text": "Tell me about a time feedback changed your view, plan, or product decision.",
        "variants": {
            "founderType:student": "Have you ever changed your mind because feedback or evidence showed you were wrong? What happened?",
            "founderType:serial": "Give me one example where evidence overruled your founder instinct. What changed in your decision-making?",
        },
        "category": "Team",
        "weightTier": "important",
        "stages": ["all"],
        "founderTypes": ["all"],
        "sectors": ["all"],
        "tags": ["antler", "coachability", "feedback", "founder psychology"],
        "triggerTerms": ["antler"],
        "expectsQuantification": False,
    },
    {
        "id": "antler_why_antler",
        "text": "Why Antler specifically, and what would you use the program for in the next 6 months?",
        "variants": {
            "founderType:student": "Why Antler specifically, and what would you use the program for if they backed you?",
            "founderType:serial": "Why is Antler the right platform for this company right now, beyond generic capital and network access?",
        },
        "category": "Ask",
        "weightTier": "important",
        "stages": ["all"],
        "founderTypes": ["all"],
        "sectors": ["all"],
        "tags": ["antler", "why antler", "program fit", "milestone"],
        "triggerTerms": ["antler"],
        "expectsQuantification": False,
    },
    {
        "id": "antler_team_dynamic",
        "text": "If you are solo, what founder gap do you still need to fill? If you have co-founders, why is this pairing unusually strong?",
        "variants": {
            "founderType:student": "If you are building this alone, what kind of co-founder or skill partner do you still need? If you already have one, why do you work well together?",
        },
        "category": "Team",
        "weightTier": "important",
        "stages": ["all"],
        "founderTypes": ["all"],
        "sectors": ["all"],
        "tags": ["antler", "cofounder", "solo founder", "team dynamic"],
        "triggerTerms": ["antler"],
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

QUESTION_LENS_MAP: dict[str, list[str]] = {
    "one_sentence_pitch": ["one_sentence_pitch"],
    "problem_specific": ["user_problem", "one_sentence_pitch"],
    "current_workaround": ["user_problem", "icp_wedge"],
    "why_now": ["why_now"],
    "segment_focus": ["icp_wedge"],
    "value_outcome": ["one_sentence_pitch"],
    "quantified_outcome": ["growth_readiness", "proof_validation"],
    "validation_signal": ["proof_validation", "growth_readiness"],
    "testing_method": ["proof_validation", "execution_risk"],
    "willingness_to_pay": ["business_model", "growth_readiness"],
    "cost_to_serve": ["business_model"],
    "differentiation": ["icp_wedge", "one_sentence_pitch"],
    "acquisition_path": ["growth_readiness", "icp_wedge"],
    "usage_frequency": ["growth_readiness"],
    "team_right_to_win": ["founder_product_fit"],
    "antler_founder_spike": ["founder_product_fit"],
    "antler_coachability": ["founder_product_fit", "execution_risk"],
    "antler_why_antler": ["founder_product_fit", "execution_risk"],
    "antler_team_dynamic": ["founder_product_fit"],
    "next_milestone": ["execution_risk", "growth_readiness"],
    "key_risk": ["execution_risk"],
    "saas_workflow": ["one_sentence_pitch", "growth_readiness"],
    "saas_technical_risk": ["execution_risk"],
    "marketplace_liquidity": ["growth_readiness", "icp_wedge"],
    "fintech_trust": ["execution_risk"],
    "sustainability_signal": ["proof_validation"],
}

LENS_DOMAIN_MAP = {
    "founder_product_fit": "founder",
    "one_sentence_pitch": "problem",
    "growth_readiness": "business",
    "user_problem": "problem",
    "icp_wedge": "market",
    "proof_validation": "problem",
    "business_model": "business",
    "why_now": "market",
    "execution_risk": "solution",
}

CATEGORY_BELIEF_KEYS = {
    "Pitch": "clarity",
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
            return "Keep it simple: one user, one problem, one concrete moment."
        return "Stay concrete and use one real example."
    if conversation_state == "validate":
        if question["category"] == "Traction":
            return "Answer shape: who you spoke to -> what they said -> what changed."
        return "Anchor this in real behavior, not just a belief."
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
            return "Think in one sharp story: user -> pain -> current workaround."
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
            return "Think like a strong founder: who hurts, what breaks, and when it became unacceptable."
        if question["category"] == "Market":
            return "Think like a strong founder: start narrow before talking about scale."
        if question["category"] == "Solution":
            return "Think like a strong founder: outcome first, feature second."
        if question["category"] == "Traction":
            return "Think like a strong founder: proof beats opinion."
    return "Go one layer deeper with a concrete story or proof point."


def _question_probe_intent(question: dict[str, Any], state: "ConversationState | None", metadata: dict[str, Any] | None) -> str:
    category = question.get("category", "")
    question_id = question.get("id", "")
    if question_id == "one_sentence_pitch":
        return "tighten the one-line pitch and make it easier to repeat"
    if category == "Problem":
        return "reflect the pain briefly, then ask for a concrete user story"
    if category == "Market":
        return "narrow to the first customer and why they care first"
    if category == "Solution":
        return "tie the product back to the user outcome in plain language"
    if category == "Traction":
        return "ask for the strongest real proof or observed behavior"
    if category == "Business Model":
        return "test willingness to pay and the tradeoff behind delivery"
    if category == "Team":
        return "show why this team has earned the right to solve this"
    if category == "Ask":
        return "surface the next milestone or main risk"
    return "go one level deeper on the missing evidence"


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


def _context_source_text(metadata: dict[str, Any]) -> str:
    return " ".join(
        bit
        for bit in [
            metadata.get("setupContext", ""),
            metadata.get("website", {}).get("text", ""),
            " ".join(str(item.get("answer", "")) for item in metadata.get("answers", [])[-4:]),
        ]
        if bit
    ).lower()


def _firm_aliases(name: str) -> set[str]:
    aliases = {name.strip().lower()}
    compact = re.sub(r"\s*\([^)]*\)", "", name).strip().lower()
    if compact:
        aliases.add(compact)
    match = re.search(r"\(([^)]+)\)", name)
    if match:
        aliases.add(match.group(1).strip().lower())
    return {alias for alias in aliases if alias}


def _accelerator_target(metadata: dict[str, Any]) -> str:
    source_text = _context_source_text(metadata)
    if "antler" in source_text:
        return "antler"
    return ""


def _investor_target(metadata: dict[str, Any]) -> str:
    source_text = _context_source_text(metadata)

    if "antler" in source_text:
        return "pre_seed_seed"

    for stage_key in ("growth_late", "multi_stage", "early_stage", "pre_seed_seed"):
        for firm in VC_STAGE_MAP.get(stage_key, []):
            if any(alias in source_text for alias in _firm_aliases(firm)):
                return stage_key

    if any(term in source_text for term in ("accelerator", "pre-seed", "pre seed", "angel investor", "angel round", "batch", "demo day", "scout")):
        return "pre_seed_seed"
    if any(term in source_text for term in ("growth equity", "late stage", "late-stage", "pre-ipo", "series c", "series d", "series e")):
        return "growth_late"
    if any(term in source_text for term in ("multi-stage", "multistage", "institutional vc", "series b")):
        return "multi_stage"
    if any(term in source_text for term in ("seed vc", "early stage", "early-stage", "series a", "first institutional")):
        return "early_stage"

    stage = metadata.get("stage", "unknown")
    if stage in {"idea", "pre-revenue"}:
        return "pre_seed_seed"
    if stage == "early-revenue":
        return "early_stage"
    if stage == "growth":
        return "growth_late"
    return "multi_stage"


def _sentences(text: str) -> list[str]:
    return [chunk.strip() for chunk in re.split(r"(?<=[.!?])\s+|\n+", text or "") if chunk.strip()]


def _best_sentence(text: str, keywords: tuple[str, ...] | list[str]) -> str:
    for sentence in _sentences(text):
        lowered = sentence.lower()
        if any(keyword in lowered for keyword in keywords):
            return sentence[:220]
    return (_sentences(text)[:1] or [""])[0][:220]


def _empty_lens_entry(key: str) -> dict[str, Any]:
    config = LENS_CONFIG[key]
    return {
        "key": key,
        "label": config["label"],
        "group": config["group"],
        "score": 0.0,
        "status": "unknown",
        "why": "",
        "evidence": [],
        "improvement": config["fix"],
    }


def _status_from_score(score: float, evidence_count: int, blocked: bool = False) -> str:
    if blocked:
        return "blocked"
    if evidence_count == 0 and score < 35:
        return "unknown"
    if score >= 72:
        return "strong"
    if score >= 42:
        return "partial"
    return "blocked" if evidence_count > 0 else "unknown"


def _report_status(status: str) -> str:
    if status == "strong":
        return "strong"
    if status == "partial":
        return "partial"
    return "weak"


def normalize_budget(value: int | None) -> int:
    if value in {10, 12, 15, 20}:
        return min(int(value), DEFAULT_MAX_QUESTIONS)
    return DEFAULT_MAX_QUESTIONS


def normalize_session_type(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized == "evaluator":
        return "evaluator"
    if normalized == "expert":
        return "expert"
    return "mentor"


def initial_evaluation_metadata(
    *,
    question_budget: int,
    provider: str,
    model: str,
    setup_context: str = "",
    website: dict | None = None,
    founder_type: str = "unknown",
    sector: str = "unknown",
    stage: str = "unknown",
    mode: str = "think_it_through",
    geography: str = "unspecified",
) -> dict[str, Any]:
    return {
        "questionBudget": normalize_budget(question_budget),
        "maxQuestionsHidden": normalize_budget(question_budget),
        "provider": provider,
        "model": model,
        "setupContext": (setup_context or "").strip(),
        "website": website or {},
        "founderType": founder_type,
        "sector": sector,
        "stage": stage,
        "mode": mode,
        "geography": geography or "unspecified",
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
        "initialEvidenceMap": {key: _empty_lens_entry(key) for key in LENS_CONFIG},
        "lensStates": {key: _empty_lens_entry(key) for key in LENS_CONFIG},
        "confidenceScore": 0.0,
        "stopReason": "Gathering evidence.",
        "deeperRounds": 0,
        "deeperQuestionsRemaining": 0,
        "conversationMove": "",
        "domainFocus": [],
        "answerRecord": empty_answer_record(),
        "assumptionsToVerify": [],
        "needsInfo": [],
        "retrievalGap": "",
        "sourceConflict": "",
        "lastQuestionStem": "",
        "lastMoveType": "",
        "lastReflectionUsed": "",
        "stableWorkflow": False,
        "runtimeHealth": {"readTimeouts": 0, "slowTurns": 0},
    }


def _required_lenses(metadata: dict[str, Any]) -> list[str]:
    investor_target = _investor_target(metadata)
    if investor_target == "pre_seed_seed":
        required = ["founder_product_fit", "one_sentence_pitch", "growth_readiness", "user_problem", "proof_validation", "icp_wedge", "why_now"]
    elif investor_target == "early_stage":
        required = ["founder_product_fit", "one_sentence_pitch", "growth_readiness", "user_problem", "proof_validation", "icp_wedge", "business_model", "why_now"]
    elif investor_target == "growth_late":
        required = ["founder_product_fit", "one_sentence_pitch", "growth_readiness", "proof_validation", "business_model", "execution_risk", "why_now"]
    else:
        required = ["founder_product_fit", "one_sentence_pitch", "growth_readiness", "user_problem", "proof_validation", "icp_wedge", "business_model", "why_now", "execution_risk"]
    if _accelerator_target(metadata) == "antler" and "execution_risk" not in required:
        required.append("execution_risk")
    return list(dict.fromkeys(required))


def _lens_priority(lens_key: str, metadata: dict[str, Any]) -> int:
    base = int(LENS_CONFIG[lens_key]["priority"])
    stage = metadata.get("stage", "unknown")
    accelerator = _accelerator_target(metadata)
    investor_target = _investor_target(metadata)

    base += int(INVESTOR_LENS_BONUS.get(investor_target, {}).get(lens_key, 0))

    if accelerator == "antler":
        if lens_key == "founder_product_fit":
            base += 5
        elif lens_key == "execution_risk":
            base += 4
        elif lens_key == "one_sentence_pitch":
            base += 3
        elif lens_key == "growth_readiness" and stage in {"idea", "pre-revenue", "unknown"}:
            base += 1
        elif lens_key == "business_model":
            base -= 3
        elif lens_key == "why_now":
            base -= 1

    if lens_key == "growth_readiness" and stage in {"idea", "pre-revenue"}:
        base += 2
    if lens_key == "business_model" and stage == "idea":
        base -= 2
    return base


def _merge_lens_signal(entry: dict[str, Any], score: float, evidence: str, why: str = "", blocked: bool = False) -> None:
    entry["score"] = round(max(float(entry.get("score", 0.0)), float(score)), 1)
    if evidence and evidence not in entry["evidence"]:
        entry["evidence"].append(evidence)
    if why and not entry.get("why"):
        entry["why"] = why
    entry["status"] = _status_from_score(entry["score"], len(entry["evidence"]), blocked=blocked)


def _score_text_lenses(text: str, metadata: dict[str, Any]) -> dict[str, Any]:
    result = {key: _empty_lens_entry(key) for key in LENS_CONFIG}
    lowered = (text or "").lower()
    if not lowered.strip():
        return result
    evidence_balance = detect_evidence_balance(text)

    first_sentence = (_sentences(text)[:1] or [""])[0]
    has_user = _contains_any(lowered, ("user", "customer", "buyer", "seller", "employee", "student", "team", "finance"))
    has_problem = _contains_any(lowered, ("problem", "pain", "slow", "manual", "duplicate", "error", "expensive", "friction", "broken"))
    has_workaround = _contains_any(lowered, ("today", "currently", "manual", "spreadsheet", "excel", "workaround", "status quo", "without"))
    has_value = _contains_any(lowered, ("save", "reduce", "improve", "increase", "faster", "easier", "automate", "prevent"))
    has_segment = _contains_any(lowered, ("first customer", "segment", "buyer", "team", "company size", "icp", "beachhead"))
    has_distribution = _contains_any(lowered, ("channel", "outbound", "sales", "pilot", "waitlist", "community", "referral", "distribution", "launch"))
    has_payment = _contains_any(lowered, ("pay", "pricing", "revenue", "subscription", "fee", "margin", "cost", "budget"))
    has_why_now = _contains_any(lowered, ("now", "recent", "shift", "regulation", "ai", "adoption", "behavior", "change"))
    has_team = _contains_any(
        lowered,
        ("we built", "built internal", "our team", "founder", "founders", "worked at", "experience", "background", "domain", "years", "founded", "operator"),
    )
    has_risk = _contains_any(lowered, ("risk", "blocker", "milestone", "next", "need to prove", "uncertain", "hardest"))
    has_numbers = bool(NUMBER_PATTERN.search(text))
    has_evidence = _contains_any(lowered, EVIDENCE_MARKERS) or evidence_balance["status"] == "evidence"
    concise_pitch = 8 <= len(_tokens(first_sentence)) <= 32 and has_user and (has_problem or has_value)

    if concise_pitch:
        _merge_lens_signal(
            result["one_sentence_pitch"],
            78,
            first_sentence[:220],
            "The intake already states the company in a reasonably crisp sentence.",
        )
    elif first_sentence and (has_user or has_value):
        _merge_lens_signal(
            result["one_sentence_pitch"],
            48,
            first_sentence[:220],
            "The intake hints at the pitch, but it is still not sharp enough.",
        )

    if has_user and has_problem:
        score = 74 if has_workaround else 58
        _merge_lens_signal(
            result["user_problem"],
            score,
            _best_sentence(text, ("problem", "pain", "manual", "slow", "duplicate", "error")),
            "The intake explains the user pain with enough specificity to judge the problem.",
        )

    if has_segment or _contains_any(lowered, ("who", "for finance teams", "for founders", "for students", "for clinics", "for retailers")):
        _merge_lens_signal(
            result["icp_wedge"],
            62 if has_segment else 46,
            _best_sentence(text, ("segment", "customer", "buyer", "first", "for ")),
            "The intake points to an initial customer wedge.",
        )

    if has_evidence or has_numbers:
        _merge_lens_signal(
            result["proof_validation"],
            72 if (has_evidence and has_numbers) else 52,
            _best_sentence(text, EVIDENCE_MARKERS),
            "The intake already includes some proof rather than only opinion.",
        )
        _merge_lens_signal(
            result["growth_readiness"],
            66 if (has_evidence and (has_distribution or has_numbers)) else 48,
            _best_sentence(text, ("pilot", "test", "customer", "revenue", "users", "waitlist", "channel")),
            "The intake contains signs of proof or distribution readiness.",
        )
    elif has_distribution:
        _merge_lens_signal(
            result["growth_readiness"],
            45,
            _best_sentence(text, ("channel", "outbound", "sales", "pilot", "community", "launch")),
            "The intake hints at a go-to-market path, but proof is still thin.",
        )

    if has_payment:
        _merge_lens_signal(
            result["business_model"],
            58 if has_numbers else 44,
            _best_sentence(text, ("pay", "pricing", "subscription", "revenue", "cost", "margin")),
            "The intake contains some pricing or delivery-cost logic.",
        )

    if has_why_now:
        _merge_lens_signal(
            result["why_now"],
            54,
            _best_sentence(text, ("now", "recent", "shift", "regulation", "ai", "adoption", "change")),
            "The intake explains why this company could matter now.",
        )

    if has_team:
        _merge_lens_signal(
            result["founder_product_fit"],
            60 if has_problem else 45,
            _best_sentence(text, ("experience", "background", "worked", "domain", "team", "founded", "founder", "built")),
            "The intake gives some reason this founder or team can credibly solve the problem.",
        )

    if has_risk:
        _merge_lens_signal(
            result["execution_risk"],
            52,
            _best_sentence(text, ("risk", "blocker", "milestone", "next", "prove")),
            "The intake already identifies an execution risk or next milestone.",
        )

    if evidence_balance["status"] == "hypothesis":
        for key in ("proof_validation", "growth_readiness", "business_model"):
            result[key]["score"] = min(float(result[key]["score"]), 38.0)
            result[key]["status"] = _status_from_score(result[key]["score"], len(result[key]["evidence"]))
            if not result[key]["why"]:
                result[key]["why"] = "Most of this section is still a future plan or hypothesis, not evidence yet."

    return result


def _refresh_intake_state(metadata: dict[str, Any]) -> dict[str, Any]:
    source_text = "\n\n".join(
        bit
        for bit in [
            metadata.get("setupContext", "").strip(),
            metadata.get("website", {}).get("text", "").strip(),
        ]
        if bit
    )
    refinement = refine_founder_input(
        source_text,
        state=ConversationState(
            founder_type=metadata.get("founderType", "unknown"),
            sector=metadata.get("sector", "unknown"),
            stage=metadata.get("stage", "unknown"),
            mode=metadata.get("mode", "think_it_through"),
            geography=metadata.get("geography", "unspecified"),
        ),
    )
    metadata["domainFocus"] = refinement["domainFocus"]
    metadata["assumptionsToVerify"] = refinement["assumptionsToVerify"]
    metadata["answerRecord"] = update_answer_record(
        metadata.get("answerRecord"),
        source_text,
        refinement["domainFocus"],
        source="setup",
        evidence_status=refinement["evidenceStatus"],
        assumptions=refinement["assumptionsToVerify"],
    )
    intake_map = _score_text_lenses(source_text, metadata)
    metadata["initialEvidenceMap"] = intake_map
    return intake_map


def _build_lens_states(metadata: dict[str, Any]) -> dict[str, Any]:
    snapshots = {
        key: {
            **_empty_lens_entry(key),
            **{
                "score": float((metadata.get("initialEvidenceMap", {}).get(key) or {}).get("score", 0.0)),
                "why": str((metadata.get("initialEvidenceMap", {}).get(key) or {}).get("why", "")),
                "evidence": list((metadata.get("initialEvidenceMap", {}).get(key) or {}).get("evidence", [])),
            },
        }
        for key in LENS_CONFIG
    }
    for key, entry in snapshots.items():
        entry["status"] = _status_from_score(entry["score"], len(entry["evidence"]))

    contradictions = 0
    for answer in metadata.get("answers", []):
        qid = answer.get("questionId", "")
        answer_text = str(answer.get("answer", "")).strip()
        answer_score = float(answer.get("overallScore", 0.0))
        question_lenses = QUESTION_LENS_MAP.get(qid, [])
        blocked = bool(answer.get("contradictions"))
        contradictions += len(answer.get("contradictions", []))
        for lens_key in question_lenses:
            snapshot = snapshots[lens_key]
            score = answer_score
            if lens_key in {"growth_readiness", "proof_validation"}:
                score = max(score, float(answer.get("scores", {}).get("evidence", 0.0)) / 5.0 * 100.0)
            if lens_key == "one_sentence_pitch":
                score = max(score, float(answer.get("scores", {}).get("clarity", 0.0)) / 5.0 * 100.0)
            if lens_key == "business_model":
                score = max(score, float(answer.get("scores", {}).get("quantification", 0.0)) / 5.0 * 100.0)
            _merge_lens_signal(
                snapshot,
                score,
                answer_text[:220],
                str(answer.get("why", "")).strip(),
                blocked=blocked,
            )
        if blocked:
            for lens_key in question_lenses:
                snapshots[lens_key]["status"] = "blocked"

    for key, entry in snapshots.items():
        if not entry["why"]:
            entry["why"] = LENS_CONFIG[key]["why"]
        entry["improvement"] = LENS_CONFIG[key]["fix"]

    metadata["lensStates"] = snapshots
    completeness = sum(1 for key in _required_lenses(metadata) if snapshots[key]["status"] in {"partial", "strong"}) / max(len(_required_lenses(metadata)), 1)
    strong_core = sum(1 for key in CORE_LENSES if snapshots[key]["status"] == "strong")
    contradiction_penalty = min(contradictions * 8, 24)
    metadata["confidenceScore"] = max(0.0, min(round((completeness * 55) + (strong_core * 12) + (len(metadata.get("answers", [])) * 4) - contradiction_penalty, 1), 100.0))
    return snapshots


def _report_readiness(metadata: dict[str, Any]) -> tuple[bool, str]:
    lens_states = _build_lens_states(metadata)
    required = _required_lenses(metadata)
    if len(metadata.get("answers", [])) >= normalize_budget(metadata.get("maxQuestionsHidden")):
        return True, f"Stopped at the {normalize_budget(metadata.get('maxQuestionsHidden'))}-question safety cap."

    if metadata.get("deeperQuestionsRemaining", 0) > 0:
        return False, "Pressure-testing deeper."

    unknown_required = [key for key in required if lens_states[key]["status"] == "unknown"]
    core_strong = [key for key in CORE_LENSES if lens_states[key]["status"] == "strong"]
    core_partial = [key for key in CORE_LENSES if lens_states[key]["status"] in {"partial", "strong"}]
    supportive_ready = sum(1 for key in required if lens_states[key]["status"] in {"partial", "strong"})
    has_starting_context = bool(metadata.get("setupContext", "").strip() or metadata.get("website", {}).get("text", "").strip())

    if not unknown_required and len(core_strong) >= 2 and len(core_partial) == len(CORE_LENSES):
        answered = len(metadata.get("answers", []))
        if answered == 0 and has_starting_context:
            return True, "Enough evidence from the intake alone."
        return True, f"Enough evidence from intake and {answered} follow-up question{'s' if answered != 1 else ''}."

    if supportive_ready >= max(len(required) - 1, 1) and len(core_partial) == len(CORE_LENSES) and metadata["confidenceScore"] >= 72:
        return True, "Enough evidence to issue a useful report without more repetition."

    return False, "More evidence is still needed on the weakest lens."

def public_question(
    question: dict[str, Any],
    state: "ConversationState | None" = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base_text = get_question_text(question, state)
    surface_text = base_text
    context_hint = _question_context_hint(question, state, metadata)
    if metadata and question.get("id") == metadata.get("currentQuestionId"):
        surface_text = str(metadata.get("currentQuestionSurfaceText", "") or base_text)
        context_hint = str(metadata.get("currentQuestionContextHint", "") or context_hint)
    return {
        "id": question["id"],
        "text": surface_text,
        "baseText": base_text,
        "contextHint": context_hint,
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
                " ".join(str(item.get("answer", "")) for item in metadata.get("answers", [])[-4:]),
            ]
        ).lower()
        if not any(term in source_text for term in trigger_terms):
            return False
    return True


def select_next_question(state: ConversationState, metadata: dict[str, Any]) -> dict[str, Any] | None:
    asked_ids = set(metadata.get("askedQuestionIds", []))
    answers = metadata.get("answers", [])
    beliefs = _belief_state(metadata)
    max_questions = normalize_budget(metadata.get("maxQuestionsHidden"))
    lens_states = _build_lens_states(metadata)
    ready, _ = _report_readiness(metadata)
    accelerator = _accelerator_target(metadata)
    investor_target = _investor_target(metadata)

    if len(answers) >= max_questions:
        return None
    if ready and metadata.get("deeperQuestionsRemaining", 0) <= 0:
        return None

    if not asked_ids and not metadata.get("setupContext", "").strip() and "one_sentence_pitch" in QUESTION_LOOKUP:
        question = QUESTION_LOOKUP["one_sentence_pitch"]
        if _applicable(question, state, metadata):
            return question
    if accelerator == "antler" and not answers and lens_states["founder_product_fit"]["status"] != "strong":
        question = QUESTION_LOOKUP.get("antler_founder_spike")
        if question and _applicable(question, state, metadata):
            return question
    if investor_target == "growth_late" and not answers:
        for question_id in ("quantified_outcome", "usage_frequency", "acquisition_path"):
            question = QUESTION_LOOKUP.get(question_id)
            if question and _applicable(question, state, metadata):
                return question
    if investor_target == "early_stage" and not answers and lens_states["proof_validation"]["status"] != "strong":
        question = QUESTION_LOOKUP.get("validation_signal")
        if question and _applicable(question, state, metadata):
            return question
    if investor_target == "multi_stage" and not answers:
        for question_id in ("validation_signal", "acquisition_path"):
            question = QUESTION_LOOKUP.get(question_id)
            if question and _applicable(question, state, metadata):
                return question

    weak_tags: list[str] = []
    last_answer = answers[-1] if answers else {}
    last_lenses = QUESTION_LENS_MAP.get(last_answer.get("questionId", ""), [])
    if answers:
        if last_answer.get("scores", {}).get("quantification", 0) < 2.5:
            weak_tags.append("quantification")
        if last_answer.get("scores", {}).get("evidence", 0) < 2.5:
            weak_tags.append("validation")
        if last_answer.get("scores", {}).get("comprehension", 0) < 2.5:
            weak_tags.append(last_answer.get("category", "").lower())

    candidates = []
    for question in QUESTION_BANK:
        if question["id"] in asked_ids:
            continue
        if not _applicable(question, state, metadata):
            continue

        score = WEIGHT_MULTIPLIERS[question["weightTier"]] * 10
        question_lenses = QUESTION_LENS_MAP.get(question["id"], [])
        question_tags = set(question.get("tags", []))
        if not question_lenses:
            continue

        for lens_key in question_lenses:
            lens_state = lens_states[lens_key]
            score += _lens_priority(lens_key, metadata) * 3
            if lens_key in _required_lenses(metadata):
                score += 12
            if lens_state["status"] == "unknown":
                score += 24
            elif lens_state["status"] == "blocked":
                score += 18
            elif lens_state["status"] == "partial":
                score += 10
            elif lens_state["status"] == "strong":
                score -= 20
            if lens_key in last_lenses and float(last_answer.get("overallScore", 0.0)) >= 68:
                score -= 12
            if lens_key in last_lenses and float(last_answer.get("overallScore", 0.0)) < 55:
                score += 8

        if question["category"] in {"Problem", "Traction"} and len(answers) < 4:
            score += 6
        if len(answers) == 0 and question["id"] == "one_sentence_pitch" and lens_states["one_sentence_pitch"]["status"] != "strong":
            score += 18
        if len(answers) == 0 and question["id"] == "problem_specific" and lens_states["user_problem"]["status"] != "strong":
            score += 14
        if len(answers) < 2 and question.get("expectsQuantification"):
            score -= 14
        if len(answers) < 2 and question["id"] in {"willingness_to_pay", "cost_to_serve"}:
            score -= 10
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
        if question["id"] == "next_milestone" and len(answers) < 2:
            score -= 3
        if metadata.get("deeperQuestionsRemaining", 0) > 0 and any(
            lens_states[lens_key]["status"] in {"partial", "blocked"} for lens_key in question_lenses
        ):
            score += 6

        score += int(INVESTOR_QUESTION_BONUS.get(investor_target, {}).get(question["id"], 0))

        if accelerator == "antler":
            if "antler" in question_tags:
                score += 16
            if question["id"] == "antler_founder_spike" and lens_states["founder_product_fit"]["status"] != "strong":
                score += 18
            if len(answers) == 0 and question["id"] == "antler_founder_spike":
                score += 10
            if question["id"] == "antler_coachability" and lens_states["execution_risk"]["status"] in {"unknown", "partial", "blocked"}:
                score += 12
            if len(answers) == 0 and question["id"] == "antler_coachability":
                score -= 6
            if question["id"] == "antler_why_antler":
                score += 10 if len(answers) >= 1 else 4
            if question["id"] == "antler_team_dynamic" and state.founder_type in {"student", "unknown"}:
                score += 8
            if len(answers) < 2 and question["id"] in {"willingness_to_pay", "cost_to_serve", "market_size"}:
                score -= 12
            if question["category"] == "Ask" and "antler" not in question_tags:
                score -= 5

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
    evidence_balance = detect_evidence_balance(text)
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
    if evidence_balance["status"] == "hypothesis":
        evidence -= 1.0

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
    if evidence_balance["status"] == "hypothesis":
        logic -= 0.4

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


def _is_clarification_request(answer: str) -> bool:
    lowered = (answer or "").strip().lower()
    if not lowered:
        return False
    if any(cue in lowered for cue in CLARIFICATION_REQUEST_CUES):
        return True
    if lowered.endswith("?") and any(term in lowered for term in ("question", "mean", "asking", "clarify", "explain")):
        return True
    return False


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


def _clarified_question_text(question: dict[str, Any], state: ConversationState) -> str:
    founder_type = state.founder_type
    if question.get("expectsQuantification"):
        if founder_type in {"student", "professional"}:
            return "In simple terms: give me one rough number or estimate that shows the impact. Time saved, money saved, errors reduced, or users helped all count."
        return "Restate this with one believable number, estimate, or measured outcome."

    if question["category"] == "Problem":
        if founder_type in {"student", "professional"}:
            return "In simple terms: who has this problem, what exactly goes wrong for them, and how do they handle it today?"
        return "Restate the user, the exact pain, and the current workaround."
    if question["category"] == "Market":
        if founder_type in {"student", "professional"}:
            return "In simple terms: who is the first kind of customer most likely to say yes, and why them first?"
        return "Restate the first segment, why they care most, and why now."
    if question["category"] == "Solution":
        if founder_type in {"student", "professional"}:
            return "In simple terms: what result does the user get, and why is this better than what they use now?"
        return "Restate the user outcome first, then why the product wins."
    if question["category"] == "Traction":
        if founder_type in {"student", "professional"}:
            return "In simple terms: what proof do you have so far from interviews, tests, pilots, or early usage?"
        return "Restate the strongest proof point and what it shows."
    if question["category"] == "Business Model":
        if founder_type in {"student", "professional"}:
            return "In simple terms: what would someone pay for, and what would it roughly cost you to deliver it?"
        return "Restate what gets paid for and what it costs to serve."
    if question["category"] == "Team":
        return "In simple terms: why is your team the right one for this problem?"
    if question["category"] == "Ask":
        return "In simple terms: what is the one next milestone that matters most?"
    return "Let me restate it simply: answer the core point in one concrete sentence."


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


def _why_for_scores_with_balance(scores: dict[str, float], answer: str) -> str:
    evidence_balance = detect_evidence_balance(answer)
    if evidence_balance["status"] == "hypothesis":
        return "Most of this answer is still a plan or belief. I need evidence from something already observed, tested, or done."
    return _why_for_scores(scores)


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


def _suggestions_for_scores_with_balance(scores: dict[str, float], question: dict[str, Any], answer: str) -> list[str]:
    suggestions = _suggestions_for_scores(scores, question)
    evidence_balance = detect_evidence_balance(answer)
    if evidence_balance["status"] == "hypothesis":
        plan_fix = "Separate what you plan to do next from what you have already observed, tested, or measured."
        if plan_fix not in suggestions:
            suggestions.insert(0, plan_fix)
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


def _parse_phrased_turn(text: str) -> dict[str, str]:
    cleaned = (text or "").strip()
    try:
        parsed = _json_blob(cleaned)
        reciprocal = str(parsed.get("reciprocal", "")).strip()
        question = str(parsed.get("question", "")).strip()
        if reciprocal or question:
            return {"reciprocal": reciprocal, "question": question}
    except Exception:
        pass

    reciprocal = ""
    question = ""
    for line in cleaned.splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        if lower.startswith("reciprocal:"):
            reciprocal = stripped.split(":", 1)[1].strip()
        elif lower.startswith("question:"):
            question = stripped.split(":", 1)[1].strip()
    if reciprocal or question:
        return {"reciprocal": reciprocal, "question": question}

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", cleaned) if part.strip()]
    if len(paragraphs) >= 2:
        candidate_question = paragraphs[-1]
        if "?" in candidate_question:
            reciprocal = " ".join(paragraphs[:-1]).strip()
            question = candidate_question.strip()
            return {"reciprocal": reciprocal, "question": question}

    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if len(lines) >= 2 and "?" in lines[-1]:
        reciprocal = " ".join(lines[:-1]).strip()
        question = lines[-1].strip()
        return {"reciprocal": reciprocal, "question": question}

    if "?" in cleaned:
        before, _, after = cleaned.rpartition("\n")
        if before.strip() and after.strip():
            return {"reciprocal": before.strip(), "question": after.strip()}
    return {"reciprocal": reciprocal, "question": question}


def _stem_prefix(text: str, words: int = 6) -> str:
    cleaned = " ".join((text or "").strip().split())
    if not cleaned:
        return ""
    return " ".join(cleaned.split()[:words])


def _remember_phrase_metadata(
    metadata: dict[str, Any],
    *,
    move_type: str,
    reciprocal: str,
    question: str,
    probe_intent: str,
    needs_info: list[str] | None = None,
    retrieval_gap: str = "",
    source_conflict: str = "",
) -> None:
    metadata["conversationMove"] = probe_intent
    metadata["needsInfo"] = list(needs_info or [])
    metadata["retrievalGap"] = retrieval_gap
    metadata["sourceConflict"] = source_conflict
    metadata["lastQuestionStem"] = _stem_prefix(question)
    metadata["lastMoveType"] = move_type
    metadata["lastReflectionUsed"] = _stem_prefix(reciprocal)


def _fallback_phrased_question(question: dict[str, Any], state: ConversationState, move_type: str) -> str:
    category = question.get("category", "")
    founder_type = state.founder_type
    if move_type == "ask_for_story":
        if category == "Problem":
            return "Can you walk me through the last time this problem showed up for one real user?"
        return "Can you walk me through one recent example so this feels more concrete?"
    if move_type == "ask_for_emotion":
        return "When did this stop feeling manageable and become something people really wanted fixed?"
    if move_type == "ask_for_tradeoff":
        return "What are they giving up today to work around this?"
    if move_type == "clarify_same_point":
        if founder_type in {"student", "professional"}:
            return "Can you say that again in one simple, concrete line?"
        return "Can you make that one step more concrete?"
    if move_type == "translate_jargon":
        return "How would you explain that in plain language to someone outside the startup world?"
    if "proof" in move_type:
        return "What real signal have you seen that makes you believe this is true?"
    if "number" in move_type or "price" in move_type:
        return "What is one believable number or estimate that makes this easier to judge?"
    if category == "Market":
        return "Who says yes first, and why them before everyone else?"
    if category == "Solution":
        return "What changes for the user after they use this?"
    return get_question_text(question, state)


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
        "You are SignalX's evaluator grader. Score only the founder's latest answer. Return valid JSON only. "
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


def _lowest_dimension(scores: dict[str, float]) -> str:
    ordered = ["comprehension", "evidence", "quantification", "clarity", "logic"]
    return min(ordered, key=lambda key: scores.get(key, 5.0))


def _dedupe_coach_line(candidates: list[str], answers: list[dict[str, Any]]) -> str:
    cleaned = [candidate.strip() for candidate in candidates if candidate and candidate.strip()]
    if not cleaned:
        return "Go one step deeper with something more concrete."
    previous = str(answers[-1].get("reciprocal", "")).strip() if answers else ""
    for candidate in cleaned:
        if candidate != previous:
            return candidate
    return cleaned[0]


def _student_variant(line: str) -> str:
    replacements = {
        "quantify": "put a simple number on it",
        "measured outcome": "simple result",
        "proof point": "real example",
        "observation": "thing you saw happen",
    }
    result = line
    lowered = result.lower()
    for source, target in replacements.items():
        if source in lowered:
            result = re.sub(source, target, result, flags=re.IGNORECASE)
            lowered = result.lower()
    if "number" in lowered or "estimate" in lowered or "before-and-after" in lowered:
        return "Add one simple number, like time saved, money saved, or users helped."
    return result


def _coach_line_for_scores(
    scores: dict[str, float],
    state: ConversationState,
    question: dict[str, Any],
    answers: list[dict[str, Any]],
) -> str:
    weakest = _lowest_dimension(scores)
    question_id = question.get("id", "")
    category = question.get("category", "")
    expects_quant = bool(question.get("expectsQuantification"))
    tags = set(question.get("tags", []))

    if weakest == "comprehension" and scores["comprehension"] < 2.5:
        candidates = [
            "Answer the exact question first, then add the rest.",
            "Stay on the question before adding extra context.",
            "Lead with the direct answer, then explain it.",
        ]
    elif weakest == "evidence" and scores["evidence"] < 2.5:
        if question_id in {"validation_signal", "testing_method"} or "validation" in tags:
            candidates = [
                "Use one real interview, test, pilot, or observed user behavior.",
                "Anchor this in one concrete signal you have actually seen.",
                "Give one specific example from a real conversation, test, or prototype.",
            ]
        elif category == "Problem":
            candidates = [
                "Use one real user case so the problem feels concrete.",
                "Name one person or team that faces this pain today.",
                "Ground this in one real example of the problem happening.",
            ]
        elif category == "Team":
            candidates = [
                "Point to one concrete experience that makes you credible here.",
                "Use one specific example that proves your team can solve this.",
                "Show one real reason your team is unusually suited to this problem.",
            ]
        else:
            candidates = [
                "Add one real example instead of a broad claim.",
                "Use one concrete proof point from something you have seen or tested.",
                "Ground this in one specific observation, not just the general idea.",
            ]
    elif weakest == "quantification" and scores["quantification"] < 2.5:
        if question_id in {"willingness_to_pay", "cost_to_serve"} or category == "Business Model":
            candidates = [
                "Give one rough number for price or delivery cost.",
                "Use a simple estimate for what someone pays or what it costs you to serve them.",
                "Put one believable business number on this so it feels real.",
            ]
        elif expects_quant or category == "Traction":
            candidates = [
                "Add one number, estimate, or before-and-after result.",
                "Use one simple metric that shows the change more clearly.",
                "Put one believable number on the impact.",
            ]
        else:
            candidates = [
                "Add one rough number so the claim feels more grounded.",
                "Use one estimate to make the impact easier to judge.",
                "Put a simple number on the value here.",
            ]
    elif weakest == "clarity" and scores["clarity"] < 2.5:
        if question_id in {"one_sentence_pitch", "value_outcome", "differentiation"}:
            candidates = [
                "Say it in one clean line: user, pain, and outcome.",
                "Tighten this into one sharper sentence.",
                "Make the user, pain, and value easier to follow.",
            ]
        else:
            candidates = [
                "Tighten the wording so the point lands faster.",
                "Keep it simpler and more specific.",
                "Strip this down to the clearest version of the answer.",
            ]
    elif weakest == "logic" and scores["logic"] < 2.5:
        candidates = [
            "Make the cause-and-effect clearer so the reasoning holds up.",
            "Show why the conclusion follows from the evidence.",
            "Connect the steps in the argument more clearly.",
        ]
    else:
        if question_id in {"segment_focus", "acquisition_path"}:
            candidates = [
                "Go one level deeper on who says yes first and why.",
                "Push further on the first segment instead of the broad market.",
                "Sharpen the first-customer logic one more step.",
            ]
        elif question_id in {"team_right_to_win", "antler_founder_spike"}:
            candidates = [
                "Go one level deeper on why you are unusually credible here.",
                "Push further on the founder advantage behind this idea.",
                "Make your founder edge more explicit.",
            ]
        elif question_id in {"next_milestone", "key_risk"}:
            candidates = [
                "Be even more direct about the next milestone that matters most.",
                "Push one step deeper on the main risk or milestone.",
                "Sharpen the next move so it is easier to evaluate.",
            ]
        else:
            candidates = [
                "Go one level deeper on the strongest part of that answer.",
                "Push the best point in that answer one step further.",
                "Take the strongest point there and make it more concrete.",
            ]

    line = _dedupe_coach_line(candidates, answers)
    if state.founder_type == "student":
        line = _student_variant(line)
    if state.mode == "think_it_through" and not line.lower().startswith(("answer ", "stay ", "lead ", "use ", "add ", "give ", "say ", "make ", "go ", "be ", "push ", "point ", "ground ", "put ", "show ", "strip ", "keep ")):
        return f"That helps. {line}"
    return line


def _probe_intent_for_question(scores: dict[str, float], question: dict[str, Any], state: ConversationState) -> str:
    weakest = _lowest_dimension(scores)
    category = question.get("category", "")
    question_id = question.get("id", "")

    if weakest == "comprehension" and scores["comprehension"] < 2.5:
        return "clarify the exact answer before moving on"
    if weakest == "evidence" and scores["evidence"] < 2.5:
        if category == "Problem":
            return "reflect the pain briefly, then ask for one real incident that shows it happening"
        if category == "Team":
            return "ask for one concrete experience that makes this team credible"
        return "ask for one real proof point instead of a broad claim"
    if weakest == "quantification" and scores["quantification"] < 2.5:
        if category == "Business Model":
            return "ask for one rough price or delivery-cost estimate"
        return "ask what user outcome or impact can be measured with one believable number"
    if weakest == "clarity" and scores["clarity"] < 2.5:
        if question_id == "one_sentence_pitch":
            return "tighten the pitch into one sharp line that is easy to repeat"
        return "make the answer simpler and more direct"
    if weakest == "logic" and scores["logic"] < 2.5:
        return "make the reasoning cleaner and more cause-and-effect"
    if category == "Problem":
        return "stay with the pain and ask what made it feel unacceptable in real life"
    if category == "Market":
        return "narrow to the first customer and the tradeoff they accept today"
    if category == "Solution":
        return "connect the product to the user outcome in a concrete before-and-after story"
    if state.mode == "quick_stress_test":
        return "pressure-test the strongest unresolved claim"
    return "go one level deeper on the strongest useful signal"


def _recent_answer_summary(metadata: dict[str, Any], limit: int = 3) -> str:
    answers = metadata.get("answers", [])[-limit:]
    if not answers:
        return "No prior evaluated answers yet."
    lines = []
    for item in answers:
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        lines.append(f"- Q: {question[:90]} | A: {answer[:120]}")
    return "\n".join(lines)


async def phrase_evaluator_turn(
    *,
    provider: str,
    model: str,
    api_key: str | None,
    state: ConversationState,
    metadata: dict[str, Any],
    question: dict[str, Any],
    probe_intent: str,
    default_reciprocal: str,
    context_hint: str,
    latest_answer: str = "",
    opening_style: str = "",
    retrieval_context: str = "",
    needs_info: list[str] | None = None,
    retrieval_gap: str = "",
    source_conflict: str = "",
    move_type: str = "",
) -> dict[str, str]:
    stable_workflow = normalize_provider(provider) == "ollama" and bool(metadata.get("stableWorkflow"))
    if stable_workflow:
        return {
            "reciprocal": default_reciprocal,
            "question": _fallback_phrased_question(question, state, move_type),
        }
    system = (
        "You are SignalX's live evaluator interviewer. "
        "You sound like a sharp early-stage VC operator: concise, natural, specific, and human. "
        "Use the knowledge base and conversation history as the primary source of truth. "
        "If the knowledge base is thin, say so briefly instead of pretending. "
        "You may use one short reflective sentence before the next question when it helps the founder feel heard. "
        "Keep the tone firmer than Ideate, but not robotic or interrogative. "
        "Write one short reciprocal line and one short next question. "
        "Do not say 'good start', 'next question', 'question 2', or similar scripted labels. "
        "Do not over-praise. Do not lecture. "
        "Use plain language for students and newer founders. "
        "Keep the next question single-focus and faithful to the probe intent. "
        "Prefer a concrete story, proof point, tradeoff, or lived moment over abstract analysis when possible. "
        "Return exactly two lines in this format:\n"
        "RECIPROCAL: <one short line>\n"
        "QUESTION: <one short question>"
    )
    prompt = {
        "founderType": state.founder_type,
        "sector": state.sector,
        "stage": state.stage,
        "mode": state.mode,
        "geography": getattr(state, "geography", metadata.get("geography", "unspecified")),
        "openingStyle": opening_style,
        "moveType": move_type,
        "probeIntent": probe_intent,
        "canonicalQuestion": get_question_text(question, state),
        "contextHint": context_hint,
        "latestFounderAnswer": latest_answer,
        "domainFocus": metadata.get("domainFocus", []),
        "assumptionsToVerify": metadata.get("assumptionsToVerify", []),
        "answerRecordSummary": summarize_answer_record(metadata.get("answerRecord"), limit_domains=3),
        "knowledgeBaseFocus": needs_info or [],
        "retrievalGap": retrieval_gap,
        "sourceConflict": source_conflict,
        "retrievalContext": retrieval_context[:420],
        "recentEvaluatedTurns": _recent_answer_summary(metadata, limit=2),
        "avoidEchoing": [
            str(item.get("reciprocal", "")).strip()[:90]
            for item in metadata.get("answers", [])[-2:]
            if str(item.get("reciprocal", "")).strip()
        ],
        "responseShape": {
            "reciprocal": "string",
            "question": "string",
        },
    }
    try:
        result = await generate_provider_text(
            provider=provider,
            model=model or default_model_for_provider(provider),
            api_key=api_key,
            system=system,
            messages=[{"role": "user", "content": json.dumps(prompt, ensure_ascii=True)}],
            max_tokens=140,
            temperature=0.45,
            top_p=0.92,
            timeout_seconds=16.0,
        )
        parsed = _parse_phrased_turn(result["message"])
        reciprocal = str(parsed.get("reciprocal", "")).strip() or default_reciprocal
        question_text = str(parsed.get("question", "")).strip() or get_question_text(question, state)
        return {
            "reciprocal": reciprocal,
            "question": question_text,
        }
    except Exception:
        metadata["stableWorkflow"] = True
        runtime_health = metadata.setdefault("runtimeHealth", {"readTimeouts": 0, "slowTurns": 0})
        runtime_health["readTimeouts"] = int(runtime_health.get("readTimeouts", 0) or 0) + 1
        return {
            "reciprocal": default_reciprocal,
            "question": _fallback_phrased_question(question, state, move_type),
        }


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


def _evidence_snippet(entry: dict[str, Any], limit: int = 140) -> str:
    evidence = [str(item).strip() for item in entry.get("evidence", []) if str(item).strip()]
    if not evidence:
        return ""
    snippet = evidence[0].replace("\n", " ").strip().strip('"')
    if len(snippet) > limit:
        snippet = snippet[: limit - 1].rstrip() + "..."
    return snippet


def _snippet_clause(entry: dict[str, Any]) -> str:
    snippet = _evidence_snippet(entry)
    return f", especially around \"{snippet}\"" if snippet else ""


def _report_lens_why(entry: dict[str, Any], metadata: dict[str, Any]) -> str:
    key = entry["key"]
    status = _report_status(entry["status"])
    stage = str(metadata.get("stage", "unknown"))
    has_evidence = bool(entry.get("evidence"))
    clause = _snippet_clause(entry)
    domain_key = LENS_DOMAIN_MAP.get(key, "")
    answer_record = metadata.get("answerRecord", {})
    domain_entry = answer_record.get(domain_key, {}) if isinstance(answer_record, dict) else {}
    hypothesis_only = bool(domain_entry.get("hypotheses")) and not bool(domain_entry.get("evidence"))

    if key == "founder_product_fit":
        if hypothesis_only and status != "strong":
            return "The founder fit story is still mostly asserted. I need a concrete example that proves this team has earned the right to solve it."
        if status == "strong":
            return f"There is a credible founder edge here{clause}. It feels earned, not just claimed."
        if status == "partial":
            return f"There is some founder credibility here{clause}, but it does not yet feel like a decisive edge."
        return "I still do not have enough to believe this team has an unusual right to win on this problem."

    if key == "one_sentence_pitch":
        if status == "strong":
            return f"The company can be explained cleanly enough that the user, pain, and outcome are easy to follow{clause}."
        if status == "partial":
            return f"The pitch is directionally clear{clause}, but it still needs to be tighter and easier to repeat."
        return "The core story is still too fuzzy. I cannot repeat the company back in one sharp line yet."

    if key == "growth_readiness":
        if hypothesis_only and status != "strong":
            return "Most of the growth or proof story is still future plan. I need evidence from real behavior, testing, or completed work."
        if stage in {"idea", "pre-revenue"}:
            if status == "strong":
                return f"There is enough early proof here to justify deeper pressure-testing{clause}."
            if status == "partial":
                return f"There are early signals of demand or learning{clause}, but not enough yet to make the next step feel earned."
            return "I still do not see enough proof of demand, distribution readiness, or learning velocity."
        if status == "strong":
            return f"The traction story has enough substance to support the next phase{clause}."
        if status == "partial":
            return f"There are some useful traction signals{clause}, but the growth story is not strong enough yet."
        return "The growth case is still too soft. I do not have enough proof that this is scaling in a durable way."

    if key == "user_problem":
        if status == "strong":
            return f"The pain is concrete and believable{clause}. I can see who feels it and why it matters."
        if status == "partial":
            return f"The problem is visible{clause}, but it still needs stronger proof that the pain is frequent and urgent."
        return "The problem statement is still too loose. I cannot yet see the user pain sharply enough."

    if key == "icp_wedge":
        if status == "strong":
            return f"There is a believable first wedge here{clause}. The initial customer story feels focused."
        if status == "partial":
            return f"I can see the outline of a first segment{clause}, but the entry wedge is not narrow enough yet."
        return "The customer wedge is still too broad. I do not yet know who says yes first and why."

    if key == "proof_validation":
        if hypothesis_only and status != "strong":
            return "Validation is still mostly hypothetical. I need proof from real users, tests, pilots, or observed behavior."
        if status == "strong":
            return f"There is real validation here{clause}. This reads more like observed behavior than opinion."
        if status == "partial":
            return f"There are some useful proof points{clause}, but the validation story still feels early and uneven."
        return "Validation is still thin. I need stronger proof from real users, tests, or behavior."

    if key == "business_model":
        if hypothesis_only and status != "strong":
            return "The business model is still mostly a hypothesis. I need a clearer story on what gets paid for and what it costs in reality."
        if status == "strong":
            return f"The payment and delivery logic is starting to hold up{clause}. I can see how value could turn into a business."
        if status == "partial":
            return f"There is some business-model logic here{clause}, but it is not robust enough yet."
        return "I still cannot see a believable path to getting paid and serving customers cleanly."

    if key == "why_now":
        if status == "strong":
            return f"The timing argument feels real{clause}. There is a believable reason this matters now."
        if status == "partial":
            return f"There is some timing logic here{clause}, but the urgency of \"why now\" is not fully convincing yet."
        return "The timing argument is still weak. I do not yet see the shift that makes this especially urgent now."

    if key == "execution_risk":
        if status == "strong":
            return f"The main risk and next milestone are fairly clear{clause}. That makes execution easier to underwrite."
        if status == "partial":
            return f"There is some awareness of the main blocker{clause}, but the de-risking plan still feels loose."
        return "Execution risk is still under-defined. I do not yet know the main blocker or the next milestone that reduces it."

    if has_evidence and status == "strong":
        return f"This section holds up reasonably well{clause}."
    if has_evidence and status == "partial":
        return f"This section is moving in the right direction{clause}, but it still needs stronger support."
    return str(entry.get("why") or LENS_CONFIG[key]["why"])


def _lens_section(entry: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": entry["key"],
        "label": entry["label"],
        "status": _report_status(entry["status"]),
        "score": round(float(entry["score"]), 1),
        "why": _report_lens_why(entry, metadata),
        "evidence": entry["evidence"][:3],
        "improvement": entry["improvement"],
    }


def _report_verdict(overall_score: float, confidence: float, core_sections: list[dict[str, Any]]) -> str:
    weak_core = [item for item in core_sections if item["status"] == "weak"]
    if overall_score >= 80 and confidence >= 70 and not weak_core:
        return "Clear early signal. The core story is investable enough to keep pressure-testing specifics."
    if overall_score >= 65 and len(weak_core) <= 1:
        return "Promising, but one or two core parts still need sharper proof before the story lands cleanly."
    if overall_score >= 50:
        return "Directionally interesting, but still too soft in the core story to rely on as stated."
    return "Not ready yet. The story still needs clearer basics before moving into more advanced investor detail."


def _report_experiments(snapshots: dict[str, Any], metadata: dict[str, Any]) -> list[str]:
    experiments: list[str] = []
    investor_target = _investor_target(metadata)
    weakest = sorted(
        snapshots.values(),
        key=lambda item: (
            0 if item["key"] in CORE_LENSES else 1,
            float(item["score"]),
        ),
    )[:3]
    for item in weakest:
        suggestion = str(item.get("improvement", "")).strip()
        if suggestion and suggestion not in experiments:
            experiments.append(suggestion)
    investor_fixes: list[str] = []
    if investor_target == "pre_seed_seed":
        investor_fixes = [
            "Rewrite the story so a pre-seed investor can repeat it in one line: user, pain, and outcome.",
            "Prepare 3 proof points from interviews, prototypes, or founder experience that show this problem is real.",
            "Name the first wedge clearly: who says yes first, and why them before everyone else.",
        ]
    elif investor_target == "early_stage":
        investor_fixes = [
            "Show the strongest early validation signal and what it says about customer pull.",
            "Tighten the first-customer story: segment, willingness to pay, and why this segment converts first.",
            "State the next milestone that would make the next institutional check easier to justify.",
        ]
    elif investor_target == "multi_stage":
        investor_fixes = [
            "Clarify the repeatable go-to-market path, not just the product story.",
            "Make the value and business model logic tighter enough for a multi-stage investor to underwrite.",
            "Be explicit about the biggest execution risk and what would reduce it in the next 6 months.",
        ]
    elif investor_target == "growth_late":
        investor_fixes = [
            "Lead with the strongest proof of durable growth: retention, expansion, or repeat usage.",
            "Break down the growth engine clearly by channel, efficiency, and what scales repeatably.",
            "Show where the business model gets stronger at scale and where the current fragility still sits.",
        ]
    for suggestion in reversed(investor_fixes):
        if suggestion not in experiments:
            experiments.insert(0, suggestion)
    if _accelerator_target(metadata) == "antler":
        antler_fixes = []
        if snapshots["founder_product_fit"]["status"] != "strong":
            antler_fixes.append("Write a founder-spike answer with one concrete proof point that shows why you are unusually credible here.")
        if snapshots["one_sentence_pitch"]["status"] != "strong":
            antler_fixes.append("Practice a one-sentence company description that states user, pain, and outcome without jargon.")
        if snapshots["execution_risk"]["status"] != "strong":
            antler_fixes.append("Prepare an honest answer on the biggest founder or team gap, and how you would close it during Antler.")
        for suggestion in antler_fixes:
            if suggestion not in experiments:
                experiments.insert(0, suggestion)
    if metadata.get("stage") in {"idea", "pre-revenue"} and len(experiments) < 3:
        experiments.append("Talk to 5 target users this week and capture the exact language they use to describe the pain.")
    return experiments[:3]


def _report_fingerprint(metadata: dict[str, Any], report: dict[str, Any]) -> str:
    answers = metadata.get("answers", [])
    last_answer = answers[-1] if answers else {}
    payload = {
        "version": REPORT_NARRATIVE_VERSION,
        "completed": bool(metadata.get("completed")),
        "answeredQuestions": len(answers),
        "overallScore": float(report.get("overallScore", 0.0)),
        "stopReason": str(report.get("stopReason", "")),
        "lastQuestionId": str(last_answer.get("questionId", "")),
        "lastAnsweredAt": str(last_answer.get("answeredAt", "")),
    }
    return json.dumps(payload, sort_keys=True)


def _report_cache(metadata: dict[str, Any]) -> dict[str, Any]:
    cache = metadata.get("naturalReportCache")
    return cache if isinstance(cache, dict) else {}


def has_cached_presentable_report(metadata: dict[str, Any], report: dict[str, Any]) -> bool:
    cache = _report_cache(metadata)
    return cache.get("fingerprint") == _report_fingerprint(metadata, report) and isinstance(cache.get("report"), dict)


def present_evaluation_report(metadata: dict[str, Any]) -> dict[str, Any]:
    base = build_evaluation_report(metadata)
    if has_cached_presentable_report(metadata, base):
        return _report_cache(metadata)["report"]
    return base


def _merge_report_rewrite(base_report: dict[str, Any], rewrite: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(base_report))

    for field in ("verdict", "summary", "stopReason"):
        value = str(rewrite.get(field, "")).strip()
        if value:
            merged[field] = value

    for field, limit in (("why", 4), ("suggestions", 5), ("missingEvidence", 4), ("nextExperiments", 5)):
        value = rewrite.get(field)
        if isinstance(value, list):
            cleaned = [str(item).strip() for item in value if str(item).strip()]
            if cleaned:
                merged[field] = cleaned[:limit]

    core_updates = rewrite.get("coreLensText", {})
    if isinstance(core_updates, list):
        core_updates = {item.get("key", ""): item for item in core_updates if isinstance(item, dict)}
    if isinstance(core_updates, dict):
        for item in merged.get("coreLenses", []):
            update = core_updates.get(item.get("key", ""))
            if not isinstance(update, dict):
                continue
            why = str(update.get("why", "")).strip()
            improvement = str(update.get("improvement", "")).strip()
            if why:
                item["why"] = why
            if improvement:
                item["improvement"] = improvement

    supporting_updates = rewrite.get("supportingLensText", {})
    if isinstance(supporting_updates, list):
        supporting_updates = {item.get("key", ""): item for item in supporting_updates if isinstance(item, dict)}
    if isinstance(supporting_updates, dict):
        for item in merged.get("supportingLenses", []):
            update = supporting_updates.get(item.get("key", ""))
            if not isinstance(update, dict):
                continue
            why = str(update.get("why", "")).strip()
            improvement = str(update.get("improvement", "")).strip()
            if why:
                item["why"] = why
            if improvement:
                item["improvement"] = improvement

    question_updates = rewrite.get("questionText", {})
    if isinstance(question_updates, list):
        question_updates = {item.get("questionId", ""): item for item in question_updates if isinstance(item, dict)}
    if isinstance(question_updates, dict):
        for item in merged.get("questions", []):
            update = question_updates.get(item.get("questionId", ""))
            if not isinstance(update, dict):
                continue
            why = str(update.get("why", "")).strip()
            suggestions = update.get("suggestions")
            if why:
                item["why"] = why
            if isinstance(suggestions, list):
                cleaned = [str(entry).strip() for entry in suggestions if str(entry).strip()]
                if cleaned:
                    item["suggestions"] = cleaned[:3]

    return merged


async def naturalize_evaluation_report(
    *,
    report: dict[str, Any],
    metadata: dict[str, Any],
    state: ConversationState,
    provider: str,
    model: str,
    api_key: str | None = None,
) -> dict[str, Any]:
    if not metadata.get("completed"):
        return report
    if normalize_provider(provider) == "ollama" and metadata.get("stableWorkflow"):
        metadata["naturalReportCache"] = {
            "fingerprint": _report_fingerprint(metadata, report),
            "report": report,
            "provider": provider,
            "model": model or default_model_for_provider(provider),
            "naturalized": False,
        }
        return report

    fingerprint = _report_fingerprint(metadata, report)
    if has_cached_presentable_report(metadata, report):
        return _report_cache(metadata)["report"]

    system = (
        "You rewrite startup evaluation reports for founders. "
        "Keep the assessment grounded in the provided evidence, scores, and statuses. "
        "Make the wording natural, specific, non-repetitive, and founder-facing. "
        "Use plain language that a student founder can understand. "
        "When a business or investor term matters, explain it simply instead of sounding academic. "
        "If a short example would make a point clearer, include one. "
        "Write like a sharp but helpful memo, not a consultant scorecard or a template. "
        "Prioritize: verdict, why this score, what is working, what still needs work, top fixes, and next experiments. "
        "Do not change the score, statuses, evidence meaning, or overall judgment. "
        "Avoid robotic repetition and avoid generic lines that could fit every section. "
        "Each section must sound specific to that lens and its evidence, not like a reused template. "
        "Return valid JSON only."
    )
    prompt = {
        "founderType": state.founder_type,
        "sector": state.sector,
        "stage": state.stage,
        "mode": state.mode,
        "geography": getattr(state, "geography", metadata.get("geography", "unspecified")),
        "domainFocus": metadata.get("domainFocus", []),
        "assumptionsToVerify": metadata.get("assumptionsToVerify", []),
        "answerRecordSummary": summarize_answer_record(metadata.get("answerRecord"), limit_domains=5),
        "knowledgeBaseFocus": metadata.get("needsInfo", []),
        "retrievalGap": metadata.get("retrievalGap", ""),
        "sourceConflict": metadata.get("sourceConflict", ""),
        "report": report,
        "instructions": {
            "rewriteVerdict": True,
            "rewriteWhyBullets": True,
            "rewriteCoreLensText": True,
            "rewriteSupportingLensText": True,
            "rewriteQuestionAppendix": True,
            "keepStructure": True,
            "plansAreHypotheses": True,
        },
        "responseShape": {
            "verdict": "string",
            "summary": "string",
            "stopReason": "string",
            "why": ["string"],
            "suggestions": ["string"],
            "missingEvidence": ["string"],
            "nextExperiments": ["string"],
            "coreLensText": [{"key": "string", "why": "string", "improvement": "string"}],
            "supportingLensText": [{"key": "string", "why": "string", "improvement": "string"}],
            "questionText": [{"questionId": "string", "why": "string", "suggestions": ["string"]}],
        },
    }
    try:
        result = await generate_provider_text(
            provider=provider,
            model=model or default_model_for_provider(provider),
            api_key=api_key,
            system=system,
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(prompt, ensure_ascii=True),
                }
            ],
            max_tokens=1400,
            temperature=0.35,
            top_p=0.9,
            timeout_seconds=35.0,
        )
        parsed = _json_blob(result["message"])
        merged = _merge_report_rewrite(report, parsed)
        metadata["naturalReportCache"] = {
            "fingerprint": fingerprint,
            "report": merged,
            "provider": result["provider"],
            "model": result["model"],
            "naturalized": True,
        }
        return merged
    except Exception:
        metadata["naturalReportCache"] = {
            "fingerprint": fingerprint,
            "report": report,
            "provider": provider,
            "model": model or default_model_for_provider(provider),
            "naturalized": False,
        }
        return report


def build_evaluation_report(metadata: dict[str, Any]) -> dict[str, Any]:
    answers = metadata.get("answers", [])
    budget = normalize_budget(metadata.get("maxQuestionsHidden") or metadata.get("questionBudget"))
    lens_states = _build_lens_states(metadata)
    core_sections = [_lens_section(lens_states[key], metadata) for key in CORE_LENSES]
    supporting_sections = [_lens_section(lens_states[key], metadata) for key in SUPPORTING_LENSES]
    has_intake_evidence = any(float(item["score"]) >= 35 or item["evidence"] for item in lens_states.values())
    if not answers and not has_intake_evidence:
        confidence = float(metadata.get("confidenceScore", 0.0))
        stop_reason = metadata.get("stopReason", "No evaluation yet.")
        verdict = "No evaluation yet."
        return {
            "overallScore": 0.0,
            "partial": True,
            "answeredQuestions": 0,
            "questionBudget": budget,
            "dimensionScores": [],
            "why": ["No answers captured yet."],
            "suggestions": ["Start the assessment to generate a score."],
            "questions": [],
            "summary": verdict,
            "verdict": verdict,
            "confidence": confidence,
            "stopReason": stop_reason,
            "coreLenses": core_sections,
            "supportingLenses": supporting_sections,
            "missingEvidence": ["Add a pitch summary or answer the first adaptive question."],
            "nextExperiments": ["Start with the core story: user, pain, proof, and why now."],
        }

    total_weight = 0.0
    weighted_sum = 0.0
    for key, entry in lens_states.items():
        weight = float(LENS_CONFIG[key]["weight"])
        total_weight += weight
        weighted_sum += float(entry["score"]) * weight
    overall_score = round(weighted_sum / max(total_weight, 1.0), 1)

    dimension_scores = _dimension_averages(answers)
    confidence = float(metadata.get("confidenceScore", 0.0))
    weakest_sections = sorted(
        [*core_sections, *supporting_sections],
        key=lambda item: (
            0 if item["key"] in CORE_LENSES else 1,
            item["score"],
        ),
    )
    why = [section["why"] for section in weakest_sections[:4] if section["why"]]
    missing_evidence = [section["label"] for section in weakest_sections if section["status"] == "weak"][:4]
    suggestions = [section["improvement"] for section in weakest_sections if section["improvement"]][:3]
    stop_reason = metadata.get("stopReason", "Gathering evidence.")
    partial = not bool(metadata.get("completed"))
    verdict = _report_verdict(overall_score, confidence, core_sections)
    next_experiments = _report_experiments(lens_states, metadata)

    return {
        "overallScore": overall_score,
        "partial": partial,
        "answeredQuestions": len(answers),
        "questionBudget": budget,
        "dimensionScores": [
            {"key": key, "label": DIMENSION_LABELS[key], "score": score}
            for key, score in dimension_scores.items()
        ],
        "why": why[:4] or ["The assessment still needs clearer proof and more exact language in the weakest sections."],
        "suggestions": suggestions[:5] or ["Tighten the user, proof, and value story before going deeper."],
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
        "summary": verdict,
        "verdict": verdict,
        "confidence": confidence,
        "stopReason": stop_reason,
        "coreLenses": core_sections,
        "supportingLenses": supporting_sections,
        "missingEvidence": missing_evidence or ["No major evidence gaps remain."],
        "nextExperiments": next_experiments,
    }


def public_progress(metadata: dict[str, Any], state: "ConversationState | None" = None) -> dict[str, Any]:
    answers = metadata.get("answers", [])
    report = build_evaluation_report(metadata)
    completed = bool(metadata.get("completed"))
    current_question = None if completed else (metadata.get("clarifyingQuestion") or QUESTION_LOOKUP.get(metadata.get("currentQuestionId", "")))
    return {
        "questionBudget": normalize_budget(metadata.get("questionBudget")),
        "answeredQuestions": len(answers),
        "questionsAsked": len(answers),
        "maxQuestions": normalize_budget(metadata.get("maxQuestionsHidden") or metadata.get("questionBudget")),
        "completed": completed,
        "partial": bool(report.get("partial", False)),
        "currentQuestion": public_question(current_question, state, metadata) if current_question else None,
        "currentScore": report["overallScore"] if completed else 0.0,
        "dimensionScores": report["dimensionScores"] if completed else [],
        "website": metadata.get("website", {}),
        "lastFeedback": answers[-1]["reciprocal"] if answers else "",
        "stopReason": metadata.get("stopReason", ""),
        "canGoDeeper": completed and len(answers) < normalize_budget(metadata.get("maxQuestionsHidden") or metadata.get("questionBudget")),
    }


async def continue_evaluation_deeper(
    state: ConversationState,
    metadata: dict[str, Any],
    *,
    provider: str,
    model: str,
    api_key: str | None,
    retrieval_context: str = "",
    needs_info: list[str] | None = None,
    retrieval_gap: str = "",
    source_conflict: str = "",
) -> dict[str, Any]:
    metadata.pop("naturalReportCache", None)
    metadata.pop("currentQuestionSurfaceText", None)
    metadata.pop("currentQuestionContextHint", None)
    if len(metadata.get("answers", [])) >= normalize_budget(metadata.get("maxQuestionsHidden") or metadata.get("questionBudget")):
        metadata["completed"] = True
        metadata["stopReason"] = f"Stopped at the {normalize_budget(metadata.get('maxQuestionsHidden') or metadata.get('questionBudget'))}-question safety cap."
        return {
            "metadata": metadata,
            "question": None,
            "report": build_evaluation_report(metadata),
            "answered": {"reciprocal": "There is no room for a deeper round because the safety cap is already reached."},
        }

    metadata["completed"] = False
    metadata["completedAt"] = None
    metadata["deeperRounds"] = int(metadata.get("deeperRounds", 0) or 0) + 1
    metadata["deeperQuestionsRemaining"] = min(
        DEEPER_QUESTION_BATCH,
        normalize_budget(metadata.get("maxQuestionsHidden") or metadata.get("questionBudget")) - len(metadata.get("answers", [])),
    )
    metadata["stopReason"] = "Pressure-testing deeper."

    next_question = select_next_question(state, metadata)
    if next_question is None:
        metadata["completed"] = True
        metadata["completedAt"] = _now()
        metadata["deeperQuestionsRemaining"] = 0
        metadata["stopReason"] = "No higher-value follow-up questions remained."
        return {
            "metadata": metadata,
            "question": None,
            "report": build_evaluation_report(metadata),
            "answered": {"reciprocal": "There are no higher-value follow-ups left. The report is already as tight as it should be."},
        }

    metadata.setdefault("askedQuestionIds", []).append(next_question["id"])
    metadata["currentQuestionId"] = next_question["id"]
    probe_intent = _question_probe_intent(next_question, state, metadata)
    context_hint = _question_context_hint(next_question, state, metadata)
    move_type = "move_to_next_gap"
    phrased = await phrase_evaluator_turn(
        provider=provider,
        model=model,
        api_key=api_key,
        state=state,
        metadata=metadata,
        question=next_question,
        probe_intent=probe_intent,
        default_reciprocal="All right. Let's pressure-test the remaining edges.",
        context_hint=context_hint,
        opening_style="deeper",
        retrieval_context=retrieval_context,
        needs_info=needs_info,
        retrieval_gap=retrieval_gap,
        source_conflict=source_conflict,
        move_type=move_type,
    )
    _remember_phrase_metadata(
        metadata,
        move_type=move_type,
        reciprocal=phrased["reciprocal"],
        question=phrased["question"],
        probe_intent=probe_intent,
        needs_info=needs_info,
        retrieval_gap=retrieval_gap,
        source_conflict=source_conflict,
    )
    metadata["nextProbeIntent"] = probe_intent
    metadata["currentQuestionSurfaceText"] = phrased["question"]
    metadata["currentQuestionContextHint"] = context_hint
    return {
        "metadata": metadata,
        "question": public_question(next_question, state, metadata),
        "report": build_evaluation_report(metadata),
        "answered": {
            "reciprocal": phrased["reciprocal"],
            "questionLabel": "",
        },
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
    retrieval_context: str = "",
    needs_info: list[str] | None = None,
    retrieval_gap: str = "",
    source_conflict: str = "",
) -> dict[str, Any]:
    metadata.pop("naturalReportCache", None)
    metadata.pop("currentQuestionSurfaceText", None)
    metadata.pop("currentQuestionContextHint", None)
    if not metadata.get("intakeComplete"):
        intake_bits = [metadata.get("setupContext", "").strip(), answer.strip()]
        if upload_context.strip():
            intake_bits.append(upload_context.strip())
        metadata["setupContext"] = "\n\n".join(bit for bit in intake_bits if bit).strip()
        metadata["intakeComplete"] = True
        _refresh_intake_state(metadata)
        ready, stop_reason = _report_readiness(metadata)
        metadata["stopReason"] = stop_reason
        if ready:
            metadata["completed"] = True
            metadata["completedAt"] = _now()
            metadata["currentQuestionId"] = ""
            metadata["nextProbeIntent"] = ""
            return {
                "metadata": metadata,
                "question": None,
                "report": build_evaluation_report(metadata),
                "answered": {
                    "reciprocal": "I already have enough to evaluate this directly.",
                },
            }
        first_question = select_next_question(state, metadata)
        if first_question is None:
            metadata["completed"] = True
            metadata["completedAt"] = _now()
            metadata["stopReason"] = "There was enough evidence to evaluate without follow-up questions."
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
        probe_intent = _question_probe_intent(first_question, state, metadata)
        context_hint = _question_context_hint(first_question, state, metadata)
        move_type = "move_to_next_gap"
        phrased = await phrase_evaluator_turn(
            provider=provider,
            model=model,
            api_key=api_key,
            state=state,
            metadata=metadata,
            question=first_question,
            probe_intent=probe_intent,
            default_reciprocal="Got it. I have enough context to pressure-test the weak spots.",
            context_hint=context_hint,
            latest_answer=answer.strip(),
            opening_style="first_follow_up",
            retrieval_context=retrieval_context,
            needs_info=needs_info,
            retrieval_gap=retrieval_gap,
            source_conflict=source_conflict,
            move_type=move_type,
        )
        _remember_phrase_metadata(
            metadata,
            move_type=move_type,
            reciprocal=phrased["reciprocal"],
            question=phrased["question"],
            probe_intent=probe_intent,
            needs_info=needs_info,
            retrieval_gap=retrieval_gap,
            source_conflict=source_conflict,
        )
        metadata["nextProbeIntent"] = probe_intent
        metadata["currentQuestionSurfaceText"] = phrased["question"]
        metadata["currentQuestionContextHint"] = context_hint
        return {
            "metadata": metadata,
            "question": public_question(first_question, state, metadata),
            "report": build_evaluation_report(metadata),
            "answered": {
                "reciprocal": phrased["reciprocal"],
                "questionLabel": "",
            },
        }

    question_id = metadata.get("currentQuestionId", "")
    question = QUESTION_LOOKUP.get(question_id)
    if not question:
        question = select_next_question(state, metadata)
        if question is None:
            metadata["completed"] = True
            metadata["completedAt"] = _now()
            metadata["nextProbeIntent"] = ""
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
    refinement_state = ConversationState(
        founder_type=state.founder_type,
        sector=state.sector,
        stage=state.stage,
        mode=state.mode,
        geography=getattr(state, "geography", metadata.get("geography", "unspecified")),
    )
    refinement = refine_founder_input(answer_text, state=refinement_state)
    metadata["domainFocus"] = refinement["domainFocus"]
    metadata["assumptionsToVerify"] = refinement["assumptionsToVerify"]
    metadata["answerRecord"] = update_answer_record(
        metadata.get("answerRecord"),
        answer_text,
        refinement["domainFocus"],
        source="founder",
        evidence_status=refinement["evidenceStatus"],
        assumptions=refinement["assumptionsToVerify"],
    )

    if _is_clarification_request(answer_text):
        clarify_question = {
            "id": f"{question['id']}:clarify",
            "text": _clarified_question_text(question, state),
            "category": question["category"],
            "weightTier": question["weightTier"],
        }
        metadata["clarifyingQuestion"] = clarify_question
        _remember_phrase_metadata(
            metadata,
            move_type="clarify_same_point",
            reciprocal="Sure. Let me restate that more simply.",
            question=clarify_question["text"],
            probe_intent="restate the same question in simpler language",
            needs_info=needs_info,
            retrieval_gap=retrieval_gap,
            source_conflict=source_conflict,
        )
        return {
            "metadata": metadata,
            "answered": {
                "reciprocal": "Sure. Let me restate that more simply.",
                "questionLabel": "Same question",
            },
            "question": public_question(clarify_question, state, metadata),
            "report": build_evaluation_report(metadata),
        }

    if _is_brief_answer(answer_text):
        follow_up = {
            "id": f"{question['id']}:followup",
            "text": _clarifying_follow_up(question, state),
            "category": question["category"],
            "weightTier": question["weightTier"],
        }
        metadata["pendingAnswerPrefix"] = answer_text
        metadata["clarifyingQuestion"] = follow_up
        _remember_phrase_metadata(
            metadata,
            move_type="clarify_same_point",
            reciprocal="Got it, but I need one more specific line before I move on.",
            question=follow_up["text"],
            probe_intent="stay on the same lens and ask for one more concrete line",
            needs_info=needs_info,
            retrieval_gap=retrieval_gap,
            source_conflict=source_conflict,
        )
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

    reciprocal = _coach_line_for_scores(combined_scores, state, question, answers)
    why = _why_for_scores_with_balance(combined_scores, answer_text)
    suggestions = _suggestions_for_scores_with_balance(combined_scores, question, answer_text)
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
        "domainFocus": refinement["domainFocus"],
        "assumptionsToVerify": refinement["assumptionsToVerify"],
        "evidenceStatus": refinement["evidenceStatus"],
    }
    answers.append(answered)
    _update_belief_state(metadata, question, combined_scores, contradictions)

    if metadata.get("deeperQuestionsRemaining", 0) > 0:
        metadata["deeperQuestionsRemaining"] = max(int(metadata.get("deeperQuestionsRemaining", 0)) - 1, 0)

    ready, stop_reason = _report_readiness(metadata)
    metadata["stopReason"] = stop_reason
    budget = normalize_budget(metadata.get("maxQuestionsHidden") or metadata.get("questionBudget"))
    if len(answers) >= budget:
        metadata["completed"] = True
        metadata["completedAt"] = _now()
        metadata["currentQuestionId"] = ""
        metadata["nextProbeIntent"] = ""
        metadata["deeperQuestionsRemaining"] = 0
        report = build_evaluation_report(metadata)
        return {
            "metadata": metadata,
            "answered": answered,
            "question": None,
            "report": report,
        }

    if ready and metadata.get("deeperQuestionsRemaining", 0) <= 0:
        metadata["completed"] = True
        metadata["completedAt"] = _now()
        metadata["currentQuestionId"] = ""
        metadata["nextProbeIntent"] = ""
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
        metadata["nextProbeIntent"] = ""
        metadata["deeperQuestionsRemaining"] = 0
        report = build_evaluation_report(metadata)
        return {
            "metadata": metadata,
            "answered": answered,
            "question": None,
            "report": report,
        }

    metadata.setdefault("askedQuestionIds", []).append(next_question["id"])
    metadata["currentQuestionId"] = next_question["id"]
    probe_intent = _probe_intent_for_question(combined_scores, next_question, state)
    context_hint = _question_context_hint(next_question, state, metadata)
    move_type = probe_intent
    phrased = await phrase_evaluator_turn(
        provider=provider,
        model=model,
        api_key=api_key,
        state=state,
        metadata=metadata,
        question=next_question,
        probe_intent=probe_intent,
        default_reciprocal=reciprocal.strip(),
        context_hint=context_hint,
        latest_answer=answer_text,
        retrieval_context=retrieval_context,
        needs_info=needs_info,
        retrieval_gap=retrieval_gap,
        source_conflict=source_conflict,
        move_type=move_type,
    )
    answered["reciprocal"] = phrased["reciprocal"].strip()
    _remember_phrase_metadata(
        metadata,
        move_type=move_type,
        reciprocal=phrased["reciprocal"],
        question=phrased["question"],
        probe_intent=probe_intent,
        needs_info=needs_info,
        retrieval_gap=retrieval_gap,
        source_conflict=source_conflict,
    )
    metadata["nextProbeIntent"] = probe_intent
    metadata["currentQuestionSurfaceText"] = phrased["question"]
    metadata["currentQuestionContextHint"] = context_hint
    report = build_evaluation_report(metadata)
    return {
        "metadata": metadata,
        "answered": answered,
        "question": public_question(next_question, state, metadata),
        "report": report,
    }
