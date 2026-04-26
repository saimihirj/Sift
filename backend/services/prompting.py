"""Compact prompt builders for the local-first mentor backend."""

from __future__ import annotations

import re
from typing import Iterable

from backend.core.knowledge import D2C_KNOWLEDGE, FINTECH_KNOWLEDGE, MARKETPLACE_KNOWLEDGE, SAAS_KNOWLEDGE
from backend.core.state import ConversationState
from backend.services.refinement import summarize_answer_record


DEFAULT_RESPONSE_PROFILE = "speed"

CONFUSION_CUES = (
    "i don't understand",
    "dont understand",
    "not sure",
    "confused",
    "can you explain",
    "too technical",
    "simpler",
    "what does that mean",
    "i'm lost",
)

PHRASING_CUES = (
    "how do i say",
    "how should i say",
    "how do i ask",
    "how should i ask",
    "how do i frame",
    "how should i frame",
    "help me phrase",
    "help me frame",
    "word this",
    "articulate",
    "phrase this",
    "frame this",
)

WRAP_UP_CUES = (
    "wrap up",
    "summarize",
    "summary",
    "next steps",
    "action plan",
    "what should we do next",
    "what next",
    "end session",
    "close session",
    "done for now",
    "that's all",
    "thats all",
)

BASE_MENTOR_PROMPT = """You are Sift, a founder-facing research partner.

Use the knowledge base and recent thread as the source of truth. Retrieve only what matters for this turn. Never invent facts, numbers, quotes, or experiments.

Sound warm, sharp, and natural. One main move per turn. At most one direct question. No bullets in chat. No stock praise. If the founder is messy but the intent is clear, help with the intended startup question instead of blocking on wording.
"""

MENTOR_ROLE_PROMPT = """Mentor role:
- clarify the real problem
- test assumptions with evidence
- stay anchored on user, workflow, and proof
- use short practical examples only when they help
- close with concrete next steps only when the founder wants to wrap up
"""

MENTOR_CORE_BEHAVIOR = """Ideate behavior:
- feel like a smart peer, not an interviewer
- usually answer in 2 to 4 sentences
- use one short reflection only when it adds clarity
- if the founder is vague, stay on the same point
- if they are all narrative, ask for one proof point
- if they are all numbers, ask what user or workflow reality those numbers represent
- keep the conversation open-ended unless the founder asks to close it
"""

VC_LENS_BEHAVIOR = """VC lens:
- care about pain, proof, wedge, founder-product fit, and why now
- push harder for later-stage founders
- keep newer founders in plain language
"""

ANTI_TEMPLATE_BEHAVIOR = """Anti-template rules:
- avoid repeating the same opener or question stem
- do not sound like a checklist
- use an answer-shape helper only if the founder is clearly stuck
"""

FOUNDER_STYLE = {
    "student": "Use simple language, teach lightly, avoid jargon unless immediately explained, and ask the most basic useful question first.",
    "operator": "Assume they think in execution terms. Focus on tradeoffs, bottlenecks, and what would actually work.",
    "professional": "Assume work experience but not startup fluency. Translate business jargon into plain startup logic.",
    "founder": "Assume commitment and some context. Push on the highest-leverage weakness without over-explaining basics.",
    "investor": "Assume they care about evidence quality, downside, and whether the story is internally consistent.",
    "other": "Default to plain, direct language and adapt quickly to how they reason.",
    "serial": "Skip basics, challenge assumptions fast, and ask what is genuinely different this time.",
    "unknown": "Default to plain, direct language and do not assume expertise.",
}

MODE_STYLE = {
    "think_it_through": "Follow the thread that matters most. Depth beats coverage.",
    "quick_stress_test": "Pressure-test the weakest claim fast. Be tighter, shorter, and more direct.",
}

SIMPLE_TERM_TRANSLATIONS = {
    "customer acquisition cost (CAC)": (
        "how much money it takes to get one user. "
        "Example: spend Rs500 on posters, get 10 users, so each user costs Rs50."
    ),
    "lifetime value (LTV)": (
        "the total value one user gives over time. "
        "Example: one student stays for 6 months and pays each month."
    ),
    "retention": (
        "whether users keep coming back. "
        "Example: after one mock interview, do they return next week?"
    ),
    "runway": (
        "how many months you can keep going before money runs out. "
        "Example: Rs3 lakh in the bank and Rs50k monthly burn gives about 6 months."
    ),
    "unit economics": (
        "whether one user leaves enough money after delivery cost. "
        "Example: charge Rs100, spend Rs30 to serve them, keep Rs70 before overhead."
    ),
    "value proposition": (
        "the main reason a user should care. "
        "Example: this saves a student 2 hours of interview prep each week."
    ),
    "hypothesis": (
        "a belief you are testing, not a fact yet. "
        "Example: we think final-year students will pay for mock interviews."
    ),
    "pretotype": (
        "a rough, quick version used to test interest before building the real product. "
        "Example: a simple landing page or WhatsApp signup form."
    ),
    "market size ladder (TAM/SAM/SOM)": (
        "the full market, the part you can serve, and the smaller part you can win first. "
        "Example: all students, then engineering students, then final-year students in one city."
    ),
}

SECTION_QUESTION_LENSES = {
    "Problem": (
        "Problem lens: ask what problem exists, who feels it, how often it happens, what it costs them, "
        "and what specific pain shows this is real."
    ),
    "Solution": (
        "Solution lens: ask what they are offering, how it helps better than current options, "
        "what result the user gets, and what is actually novel or feasible."
    ),
    "Market": (
        "Customer and market lens: ask why this customer segment matters, how they narrowed to it, "
        "what interviews or experiments support it, how the market is segmented, and why now."
    ),
    "Business Model": (
        "Profit lens: ask what users may pay for, main costs, revenue shape, key assumptions, "
        "and whether the economics can work in simple believable terms."
    ),
    "Traction": (
        "Validation lens: ask what interviews, experiments, pretotypes, pivots, or early signals "
        "support the idea today."
    ),
    "Team": (
        "Team lens: ask who is on the team, proposed roles, why they can execute, and what gap still exists."
    ),
    "Ask": (
        "Action-plan lens: ask what success looks like this semester, what the next timeline looks like, "
        "which customer-discovery steps happen next, and why this deserves support."
    ),
}

STAGE_STYLE = {
    "idea": (
        "Stay concept-first. Focus on user pain, current workaround, target segment, why now, "
        "and the first believable wedge. Do not ask for CAC, LTV, or growth metrics."
    ),
    "pre-revenue": (
        "Treat this as pre-proof. Focus on value created, key feature, who changes behavior, "
        "what they may pay, and what it costs to deliver in plain language."
    ),
    "early-revenue": (
        "Use proof carefully. Tie early traction back to the value created, repeat behavior, "
        "pricing logic, and whether the business gets healthier with use."
    ),
    "growth": (
        "Push for precision. Ask for the strongest proof, weak spot, and the operating logic "
        "behind retention, expansion, and efficient growth."
    ),
    "unknown": (
        "Until the stage is clear, start with problem, customer, value, and current workaround "
        "before asking for scale metrics."
    ),
}

SECTOR_SNIPPETS = {
    "saas": (
        SAAS_KNOWLEDGE,
        "SaaS investors care about painful workflows, repeat use, product pull, and why this wins beyond feature parity.",
    ),
    "d2c": (
        D2C_KNOWLEDGE,
        "D2C investors care about product pull, repeat behavior, channel dependence, and whether the brand has real pull.",
    ),
    "fintech": (
        FINTECH_KNOWLEDGE,
        "Fintech investors care about trust, compliance, adoption trust, and what regulation can break.",
    ),
    "marketplace": (
        MARKETPLACE_KNOWLEDGE,
        "Marketplace investors care about liquidity, supply-demand density, repeat behavior, and disintermediation risk.",
    ),
}

OPENING_PREFIX = {
    "student": "You are early, which is useful.",
    "operator": "You know execution. The question is what is durable and defensible here.",
    "professional": "You know work; now we test whether this is a startup-scale problem.",
    "founder": "Good. Let us make the story harder to break.",
    "investor": "You know the pattern language. The question is what is actually true here.",
    "other": "Let us get concrete quickly.",
    "serial": "You know where decks fail. The real question is what is true here.",
    "unknown": "Let us sharpen the idea before you turn it into slides.",
}

STAGE_PROMPTS = {
    "idea": "Start with the pain, the user, and the current workaround.",
    "pre-revenue": "Stay concrete: who is this for, what changes for them, and what have you learned?",
    "early-revenue": "Early signal matters only if it is the right signal. What is real already?",
    "growth": "At this stage the story needs proof. Which part is strongest, and which part still breaks?",
    "unknown": "Tell me what you are building and why it needs to exist now.",
}

STARTER_CHIPS = {
    "idea": [
        "The user pain is...",
        "They solve it today by...",
        "The first customer is...",
        "Why now matters because...",
    ],
    "pre-revenue": [
        "We tested this by...",
        "Users care because...",
        "The key feature is...",
        "We may charge for...",
    ],
    "early-revenue": [
        "Our strongest signal is...",
        "Customers stay because...",
        "The weak spot is...",
        "The next proof point is...",
    ],
    "growth": [
        "Our strongest proof is...",
        "Growth is driven by...",
        "The story still breaks at...",
        "We are raising to...",
    ],
    "unknown": [
        "The problem we see is...",
        "The user is...",
        "The current workaround is...",
        "I need help shaping this",
    ],
}

STUDENT_STARTER_CHIPS = [
    "Can you help simplify my idea?",
    "The user pain is...",
    "They solve it today by...",
    "I am unsure who needs this most",
]

PROFESSIONAL_STARTER_CHIPS = [
    "The problem in my industry is...",
    "Current teams handle it by...",
    "The first buyer is...",
    "I need help pressure-testing this",
]

SERIAL_STARTER_CHIPS = [
    "The wedge this time is...",
    "The market changed because...",
    "The real risk is...",
    "The strongest proof so far is...",
]

QUESTION_CHIPS = [
    (("market", "tam", "sam", "customer", "who is the buyer"), [
        "The first customer is...",
        "They switch because...",
        "I sized it bottom-up like...",
        "I am still unsure on size",
    ]),
    (("pricing", "revenue", "monet", "business model", "charge"), [
        "Users would pay for...",
        "Pricing may look like...",
        "It costs us most to...",
        "We have not priced it yet",
    ]),
    (("traction", "users", "customers", "retention", "growth"), [
        "The early signal is...",
        "Users come back because...",
        "A pilot taught us...",
        "We are still pre-launch",
    ]),
    (("team", "founder", "why you", "co-founder"), [
        "We are right for this because...",
        "My background is...",
        "The missing hire is...",
        "Our unfair access is...",
    ]),
    (("competition", "alternative", "incumbent", "moat"), [
        "Users solve it today by...",
        "The main competitor is...",
        "Our edge is...",
        "The hardest thing to copy is...",
    ]),
    (("ask", "raise", "funding", "runway"), [
        "We would raise for...",
        "The next milestone is...",
        "Round size is still open",
        "The money would buy...",
    ]),
]

THIN_ANSWER_CUES = {
    "yes",
    "no",
    "maybe",
    "not sure",
    "unsure",
    "idk",
    "don't know",
    "dont know",
}

USER_PAIN_CUES = (
    "user",
    "customer",
    "pain",
    "problem",
    "friction",
    "manual",
    "workflow",
    "workaround",
    "today",
    "currently",
)

PROOF_CUES = (
    "interview",
    "pilot",
    "prototype",
    "pretotype",
    "test",
    "experiment",
    "observed",
    "users",
    "customers",
    "signed",
    "revenue",
    "paid",
    "retention",
    "waitlist",
    "trial",
    "usage",
    "feedback",
)

BUSINESS_MODEL_CUES = (
    "price",
    "pricing",
    "charge",
    "pay",
    "revenue",
    "cost",
    "margin",
    "economics",
)

TEAM_CUES = (
    "founder",
    "team",
    "co-founder",
    "background",
    "experience",
    "built",
    "worked",
)

WORKFLOW_CUES = (
    "workflow",
    "process",
    "today",
    "currently",
    "manual",
    "spreadsheet",
    "excel",
    "email",
    "handoff",
    "back and forth",
)

EMOTION_CUES = (
    "frustrated",
    "stressed",
    "anxious",
    "painful",
    "annoying",
    "unacceptable",
    "panic",
    "hate",
    "afraid",
    "surprised",
)

RISK_CUES = (
    "risk",
    "constraint",
    "blocker",
    "hardest",
    "failure mode",
    "compliance",
    "security",
    "trust",
)

STEM_ROTATION = {
    "reflect_and_deepen": (
        "So it sounds like...",
        "If I'm hearing you right...",
        "It seems the real issue is...",
    ),
    "ask_for_story": (
        "Can you remember a time when...",
        "Walk me through the last time this happened.",
        "If I sat with this user for a day, what would I notice?",
    ),
    "ask_for_proof": (
        "What real signal have you seen so far?",
        "What actually happened that makes you believe this?",
        "Which concrete proof point would you trust most here?",
    ),
    "ask_for_tradeoff": (
        "What do they sacrifice today to work around it?",
        "What tradeoff are they accepting right now?",
        "What are they giving up to keep the current process alive?",
    ),
    "ask_for_emotion": (
        "When did this become unacceptable rather than just annoying?",
        "What felt painful or surprising about that moment?",
        "When did the problem stop feeling manageable?",
    ),
    "clarify_same_point": (
        "Can you say that one step more concretely?",
        "Stay on the same point for a moment and make it more specific.",
        "Narrow that down for me with one real example.",
    ),
    "translate_jargon": (
        "Say that in plain language first.",
        "What does that mean in a simple real-world example?",
        "How would you explain that without startup jargon?",
    ),
    "move_to_next_gap": (
        "The next thing I still need to understand is...",
        "The part that still feels open is...",
        "Before this story holds up, I still need...",
    ),
}

SECTION_CHIPS = {
    "Problem": [
        "The user pain is...",
        "They solve it today by...",
        "A concrete example is...",
        "I still need to validate this",
    ],
    "Solution": [
        "We are building...",
        "The key feature is...",
        "The wedge is...",
        "It matters because...",
    ],
    "Market": [
        "The beachhead customer is...",
        "I sized it bottom-up like...",
        "The timing is good because...",
        "This segment matters because...",
    ],
    "Business Model": [
        "Users would pay for...",
        "The business improves when...",
        "Our main cost is...",
        "This part is still shaky",
    ],
    "Traction": [
        "The signal I trust is...",
        "Users behave differently after...",
        "Revenue right now is...",
        "We validated this by...",
    ],
    "Team": [
        "The team is credible because...",
        "My co-founder handles...",
        "The missing hire is...",
        "Founder-market fit comes from...",
    ],
    "Ask": [
        "The raise would fund...",
        "The next milestone is...",
        "I am still deciding size",
        "This becomes fundable when...",
    ],
}

ARTICULATION_CHIPS = {
    "Problem": [
        "User -> pain -> current workaround",
        "A strong problem statement would be...",
        "Help me frame this pain clearly",
        "One real example is...",
    ],
    "Solution": [
        "We help [user] do [job] without [pain]",
        "The result for the user is...",
        "The wedge is...",
        "Help me explain the value better",
    ],
    "Market": [
        "We start with [segment] because...",
        "The first buyer is...",
        "Why now: ...",
        "Help me narrow the customer",
    ],
    "Business Model": [
        "They would pay for...",
        "The business works because...",
        "Main cost per user is...",
        "Help me explain pricing simply",
    ],
    "Traction": [
        "We learned this from...",
        "The strongest proof is...",
        "One number that matters is...",
        "Help me show real proof",
    ],
    "Team": [
        "We are right for this because...",
        "Our unfair edge is...",
        "The missing hire is...",
        "Help me explain founder fit",
    ],
    "Ask": [
        "The next milestone is...",
        "We need support with...",
        "This becomes real when...",
        "Help me frame the next step",
    ],
}

EXPERT_THINKING_LENSES = {
    "Problem": "Strong founders think in this order: user, pain, current workaround, cost of the problem.",
    "Solution": "Strong founders think in this order: outcome first, then product, then why it wins.",
    "Market": "Strong founders start narrow: first segment, urgent reason, then expansion path.",
    "Business Model": "Strong founders explain value, what gets paid for, and what it costs to deliver.",
    "Traction": "Strong founders use proof over opinion: interviews, tests, pilots, usage, or numbers.",
    "Team": "Strong founders explain why this team has earned the right to solve this problem.",
    "Ask": "Strong founders define the next proof point before talking about a big raise or vision.",
}

SECTION_QUESTION_KEYWORDS = {
    "Problem": ("problem", "pain", "user", "customer", "workaround", "friction"),
    "Solution": ("solution", "product", "feature", "value", "workflow", "build"),
    "Market": ("market", "segment", "buyer", "customer", "why now", "go to market"),
    "Business Model": ("pricing", "revenue", "business model", "charge", "cost", "economics"),
    "Traction": ("proof", "validation", "traction", "users", "test", "pilot", "interview"),
    "Team": ("team", "founder", "co-founder", "why you"),
    "Ask": ("ask", "raise", "funding", "milestone", "next step"),
}

OUTLINE_PROMPT = """Turn the transcript into a founder-ready markdown working draft called Refined Pitch.

Use these sections exactly:
# Company Name — Refined Pitch
## One-line pitch
## Problem
## Current workaround
## Why now
## Solution
## Why this wins
## First wedge
## Business model
## Proof so far
## Team
## Near-term plan
## What still needs work

Rules:
- write like a sharp working draft, not a slide outline
- use the founder's framing where it is sharp
- if something is weak or missing, mark it as [Needs sharpening]
- keep the writing specific, concrete, and founder-friendly
- no marketing fluff
- do not say the conversation is finished or complete
"""


def build_personalized_opening(founder_type: str, sector: str, stage: str) -> str:
    prompt = STAGE_PROMPTS.get(stage, STAGE_PROMPTS["unknown"])
    sector_line = get_sector_prompt_snippet(sector)
    parts = ["Hi. What are you building?"]
    if founder_type in {"student", "professional"}:
        parts.append("Feel free to think out loud. If you're unsure how to say it, start with user -> pain -> current workaround.")
    if prompt:
        parts.append(prompt)
    if sector_line:
        parts.append(sector_line)
    return " ".join(parts[:4])


def get_starter_chips(state: ConversationState) -> list[str]:
    if state.founder_type == "student":
        return STUDENT_STARTER_CHIPS + ARTICULATION_CHIPS["Problem"][:2]
    if state.founder_type == "operator":
        return PROFESSIONAL_STARTER_CHIPS + SECTION_CHIPS["Solution"][:2]
    if state.founder_type == "professional":
        return PROFESSIONAL_STARTER_CHIPS + ARTICULATION_CHIPS["Problem"][:2]
    if state.founder_type == "investor":
        return SERIAL_STARTER_CHIPS
    if state.founder_type == "serial":
        return SERIAL_STARTER_CHIPS
    return STARTER_CHIPS.get(state.stage, STARTER_CHIPS["unknown"])


def founder_needs_simple_language(state: ConversationState, last_user_message: str = "") -> bool:
    if state.founder_type == "student":
        return True
    message = (last_user_message or "").lower()
    return any(cue in message for cue in CONFUSION_CUES)


def founder_needs_articulation_help(state: ConversationState, last_user_message: str = "") -> bool:
    if state.founder_type in {"student", "professional", "operator"}:
        return True
    message = (last_user_message or "").lower()
    return any(cue in message for cue in PHRASING_CUES)


def build_simple_language_instruction() -> str:
    examples = "; ".join(
        f"{term}: {meaning}"
        for term, meaning in SIMPLE_TERM_TRANSLATIONS.items()
    )
    return (
        "Use plain language first. Avoid startup shorthand when possible. "
        "If a startup term is useful, say the full term first, define it immediately, and add one short everyday example. "
        "Prefer student-friendly examples like posters, college clubs, hostel life, classes, or WhatsApp groups when helpful. "
        f"Useful translations: {examples}"
    )


def build_articulation_instruction(state: ConversationState) -> str:
    if state.coverage:
        weakest_section = min(state.coverage.items(), key=lambda item: item[1])[0]
    else:
        weakest_section = "Problem"
    weakest_lens = get_section_question_lens(state)
    expert_lens = EXPERT_THINKING_LENSES.get(weakest_section, EXPERT_THINKING_LENSES["Problem"])
    return (
        "Assume the founder may understand the idea but may not phrase it cleanly yet. "
        "If the intent is inferable, answer the intended startup question instead of blocking on messy wording. "
        "When helpful, give one short founder-style frame such as 'user -> pain -> workaround' or "
        "'proof -> learning -> next step'. "
        "Borrow how experienced founders think: start narrow, stay concrete, and turn opinions into evidence. "
        f"Current lens: {weakest_lens} Expert framing: {expert_lens}"
    )


def is_wrap_up_turn(last_user_message: str = "") -> bool:
    message = (last_user_message or "").lower()
    return any(cue in message for cue in WRAP_UP_CUES)


def get_section_question_lens(state: ConversationState) -> str:
    if not state.coverage:
        return SECTION_QUESTION_LENSES["Problem"]
    weakest = min(state.coverage.items(), key=lambda item: item[1])[0]
    return SECTION_QUESTION_LENSES.get(weakest, SECTION_QUESTION_LENSES["Problem"])


def get_weakest_section(state: ConversationState) -> str:
    if not state.coverage:
        return "Problem"
    return min(state.coverage.items(), key=lambda item: item[1])[0]


def _has_number(text: str) -> bool:
    return bool(re.search(r"\b\d+(?:\.\d+)?%?\b", text))


def _contains_any(text: str, cues: tuple[str, ...]) -> bool:
    return any(cue in text for cue in cues)


def _is_thin_answer(text: str) -> bool:
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return True
    if cleaned.lower() in THIN_ANSWER_CUES:
        return True
    return len(cleaned.split()) <= 5


def _recent_stem_memory(recent_assistant_turns: list[str] | None = None) -> set[str]:
    recent = [turn.strip().lower() for turn in (recent_assistant_turns or []) if turn and turn.strip()]
    seen: set[str] = set()
    for turn in recent[-3:]:
        for options in STEM_ROTATION.values():
            for stem in options:
                if stem.lower().replace("...", "") in turn:
                    seen.add(stem)
    return seen


def derive_mentor_turn_plan(
    state: ConversationState,
    last_user_message: str = "",
    recent_assistant_turns: list[str] | None = None,
) -> dict[str, str | list[str] | bool]:
    text = (last_user_message or "").strip()
    lowered = text.lower()
    weakest_section = get_weakest_section(state)
    has_number = _has_number(lowered)
    has_user_pain = _contains_any(lowered, USER_PAIN_CUES)
    has_proof = _contains_any(lowered, PROOF_CUES)
    has_business_model = _contains_any(lowered, BUSINESS_MODEL_CUES)
    has_team_signal = _contains_any(lowered, TEAM_CUES)
    has_workflow = _contains_any(lowered, WORKFLOW_CUES)
    has_emotion = _contains_any(lowered, EMOTION_CUES)
    has_risk = _contains_any(lowered, RISK_CUES)
    has_story = _contains_any(lowered, ("last time", "once", "when", "yesterday", "today", "this week", "incident", "example"))
    articulation_help = founder_needs_articulation_help(state, last_user_message)
    seems_uncertain = founder_needs_simple_language(state, last_user_message) or _contains_any(
        lowered,
        ("half-baked", "rough", "messy", "still figuring", "not sure", "figuring out"),
    )
    seen_stems = _recent_stem_memory(recent_assistant_turns)

    tags: list[str] = []
    if has_user_pain:
        tags.append("pain")
    if has_workflow:
        tags.append("workflow")
    if has_proof:
        tags.append("proof")
    if has_number:
        tags.append("quant")
    if has_team_signal:
        tags.append("team")
    if has_business_model:
        tags.append("pricing")
    if has_risk:
        tags.append("risk")
    if has_emotion:
        tags.append("emotion")
    if _is_thin_answer(text) or not tags:
        tags.append("unclear")

    if _is_thin_answer(text):
        move_type = "clarify_same_point"
        recommended_move = "The founder is thin or unclear. Stay on the same point and narrow it with one concrete example."
    elif has_number and not has_user_pain:
        move_type = "reflect_and_deepen"
        recommended_move = "The founder gave numbers without enough human context. Tie the metric back to user behavior or value created."
    elif has_user_pain and has_workflow and not has_story:
        move_type = "ask_for_story"
        recommended_move = "The founder has the outline of the pain. Ask for the last real incident so the story becomes concrete."
    elif has_user_pain and not has_emotion and state.founder_type != "serial":
        move_type = "ask_for_emotion"
        recommended_move = "The founder has described the pain, but not the moment it became unacceptable. Ask what made it emotionally or operationally costly."
    elif has_user_pain and not has_proof:
        move_type = "ask_for_proof"
        recommended_move = "The founder described the problem but has not grounded it in evidence yet. Ask for one concrete interview, observed behavior, pilot, or example."
    elif has_workflow and not has_user_pain:
        move_type = "reflect_and_deepen"
        recommended_move = "Reflect the workflow back briefly, then ask who feels the pain most and where it breaks hardest."
    elif has_proof and not has_number and state.stage in {"early-revenue", "growth"}:
        move_type = "ask_for_proof"
        recommended_move = "The founder has proof but not enough measurement. Ask for one number that sharpens the strongest claim."
    elif weakest_section == "Business Model" and not has_business_model:
        move_type = "ask_for_tradeoff"
        recommended_move = "Move toward business logic in plain language: value created, what gets paid for, and cost to deliver."
    elif weakest_section == "Team" and not has_team_signal:
        move_type = "move_to_next_gap"
        recommended_move = "Move toward founder-product fit: why this team has earned the right to solve it."
    elif founder_needs_simple_language(state, last_user_message):
        move_type = "translate_jargon"
        recommended_move = "Translate the startup logic into simple words before pushing further."
    else:
        move_type = "move_to_next_gap"
        recommended_move = f"Use the founder's strongest signal, mirror it briefly if helpful, then move into the current weak spot: {weakest_section}."

    preferred_stems = [stem for stem in STEM_ROTATION.get(move_type, ()) if stem not in seen_stems][:2]
    if not preferred_stems:
        preferred_stems = list(STEM_ROTATION.get(move_type, ())[:2])
    reflection_stem = preferred_stems[0] if move_type in {"reflect_and_deepen", "ask_for_story", "ask_for_emotion", "move_to_next_gap"} else ""
    question_stem = preferred_stems[-1] if preferred_stems else ""
    answer_shape = ""
    if articulation_help or move_type in {"clarify_same_point", "translate_jargon"}:
        if weakest_section == "Problem":
            answer_shape = "user -> pain -> current workaround"
        elif weakest_section == "Traction":
            answer_shape = "proof -> learning -> next step"
        else:
            answer_shape = "user -> pain -> result"

    return {
        "tags": tags[:2],
        "moveType": move_type,
        "recommendedMove": recommended_move,
        "questionStem": question_stem,
        "reflectionStem": reflection_stem,
        "inviteMessy": seems_uncertain,
        "answerShape": answer_shape,
    }


def build_conversation_move(
    state: ConversationState,
    last_user_message: str = "",
    recent_assistant_turns: list[str] | None = None,
) -> str:
    plan = derive_mentor_turn_plan(state, last_user_message, recent_assistant_turns)
    tag_text = ", ".join(plan["tags"]) if plan["tags"] else "unclear"
    stem_text = plan["questionStem"] or "choose a fresh natural stem"
    reflection_text = plan["reflectionStem"] or "reflect only if it truly helps"
    answer_shape = plan["answerShape"]

    return (
        "Conversation move:\n"
        f"- Latest turn tags: {tag_text}.\n"
        f"- Move type: {plan['moveType']}.\n"
        f"- Best next move: {plan['recommendedMove']}\n"
        f"- Preferred reflection style: {reflection_text}.\n"
        f"- Preferred question style: {stem_text}.\n"
        "- Ask one focused question that feels like a continuation of the founder's last answer, not a form.\n"
        "- If you reflect, do it briefly and then push deeper.\n"
        + (
            f"- Offer this answer shape only if the founder still seems stuck: {answer_shape}.\n"
            if answer_shape
            else ""
        )
        + (
            "- Half-baked answers are welcome; make that feel safe if the founder sounds uncertain.\n"
            if plan["inviteMessy"]
            else ""
        )
    )


def build_recent_memory_instruction(recent_assistant_turns: list[str] | None = None) -> str:
    recent = [turn.strip().replace("\n", " ") for turn in (recent_assistant_turns or []) if turn and turn.strip()]
    if not recent:
        return "Recent assistant history: none yet."
    trimmed = recent[-3:]
    return (
        "Recent assistant lines to avoid echoing too closely:\n"
        + "\n".join(f"- {line[:180]}" for line in trimmed)
    )


def _trim_text(text: str, max_chars: int) -> str:
    value = (text or "").strip()
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + "..."


def _compact_state_summary(state: ConversationState) -> str:
    weakest_section = get_weakest_section(state)
    strongest_facts = []
    for key, value in list((state.facts or {}).items())[:3]:
        fact = f"{key}: {value}"
        strongest_facts.append(_trim_text(fact.replace("\n", " "), 120))
    facts_text = "; ".join(strongest_facts) if strongest_facts else "none yet"
    return (
        f"Phase={state.phase}; sector={state.sector}; stage={state.stage}; founder={state.founder_type}; "
        f"mode={state.mode}; geography={state.geography}; weakest={weakest_section}; "
        f"urgency={'yes' if state.urgency else 'no'}; facts={facts_text}"
    )


def derive_mentor_turn_metadata(
    state: ConversationState,
    last_user_message: str = "",
    recent_assistant_turns: list[str] | None = None,
    *,
    needs_info: list[str] | None = None,
    retrieval_gap: str = "",
    source_conflict: str = "",
    domain_focus: list[str] | None = None,
    assumptions_to_verify: list[str] | None = None,
    answer_record: dict | None = None,
) -> dict[str, str | list[str]]:
    plan = derive_mentor_turn_plan(state, last_user_message, recent_assistant_turns)
    return {
        "conversationMove": str(plan["recommendedMove"]),
        "needsInfo": list(needs_info or []),
        "retrievalGap": retrieval_gap,
        "sourceConflict": source_conflict,
        "domainFocus": list(domain_focus or []),
        "assumptionsToVerify": list(assumptions_to_verify or []),
        "answerRecordSummary": summarize_answer_record(answer_record),
        "lastQuestionStem": str(plan["questionStem"]),
        "lastMoveType": str(plan["moveType"]),
        "lastReflectionUsed": str(plan["reflectionStem"]),
    }


def build_system_prompt(
    state: ConversationState,
    retrieval_context: str = "",
    last_user_message: str = "",
    recent_assistant_turns: list[str] | None = None,
    needs_info: list[str] | None = None,
    retrieval_gap: str = "",
    source_conflict: str = "",
    domain_focus: list[str] | None = None,
    assumptions_to_verify: list[str] | None = None,
    answer_record: dict | None = None,
    stable_workflow: bool = False,
) -> str:
    turn_plan = derive_mentor_turn_plan(state, last_user_message, recent_assistant_turns)
    answer_record_summary = summarize_answer_record(answer_record)
    parts = [
        BASE_MENTOR_PROMPT,
        MENTOR_ROLE_PROMPT,
        MENTOR_CORE_BEHAVIOR,
        VC_LENS_BEHAVIOR,
        ANTI_TEMPLATE_BEHAVIOR,
        f"Founder profile: {FOUNDER_STYLE.get(state.founder_type, FOUNDER_STYLE['unknown'])}",
        f"Conversation mode: {MODE_STYLE.get(state.mode, MODE_STYLE['think_it_through'])}",
        f"Stage lens: {STAGE_STYLE.get(state.stage, STAGE_STYLE['unknown'])}",
        get_section_question_lens(state),
        build_conversation_move(state, last_user_message, recent_assistant_turns),
        build_recent_memory_instruction(recent_assistant_turns),
        "Runtime state: " + _compact_state_summary(state),
    ]
    if stable_workflow:
        parts = [
            BASE_MENTOR_PROMPT,
            "Stable workflow: use the simpler proven mentoring path. Keep the reply concrete, grounded, and low-variance.",
            f"Founder profile: {FOUNDER_STYLE.get(state.founder_type, FOUNDER_STYLE['unknown'])}",
            f"Stage lens: {STAGE_STYLE.get(state.stage, STAGE_STYLE['unknown'])}",
            get_section_question_lens(state),
            build_conversation_move(state, last_user_message, recent_assistant_turns),
            "Runtime state: " + _compact_state_summary(state),
        ]
    if domain_focus:
        parts.append("Current business-domain focus: " + ", ".join(domain_focus) + ".")
    if assumptions_to_verify:
        parts.append(
            "Assumptions to verify, not facts:\n" + "\n".join(f"- {item}" for item in assumptions_to_verify[:3])
        )
    if answer_record_summary:
        parts.append("Internal answer record so far:\n" + answer_record_summary)
    if needs_info:
        parts.append("Current KB lookup focus: " + ", ".join(needs_info) + ".")
    if retrieval_gap:
        parts.append(
            f"Knowledge base gap: {retrieval_gap} Say this directly instead of guessing, then ask one narrow follow-up."
        )
    if source_conflict:
        parts.append(
            f"Knowledge base tension: {source_conflict} Surface the conflict explicitly and ask which version is closer to reality."
        )
    if founder_needs_simple_language(state, last_user_message):
        parts.append("The founder needs plain language. Use simpler words and ask a narrower question.")
        parts.append(build_simple_language_instruction())
    if founder_needs_articulation_help(state, last_user_message):
        parts.append(build_articulation_instruction(state))
    if any(cue in (last_user_message or "").lower() for cue in PHRASING_CUES):
        parts.append(
            "The founder is explicitly asking for phrasing help. First give the cleaner founder-style framing or answer shape, "
            "then continue with one short next-step question."
        )
    if is_wrap_up_turn(last_user_message):
        parts.append(
            "The founder is wrapping up. Do not ask a question. Give 1 to 3 concrete next steps "
            "they can realistically do next, each short and specific."
        )
    if turn_plan["inviteMessy"]:
        parts.append(
            "The founder sounds uncertain or under-specified. Make it safe to think out loud with one short permission line such as "
            "'Feel free to think out loud here' or 'Half-baked answers are fine.'"
        )
    if retrieval_context:
        parts.append(_trim_text(retrieval_context, 900 if stable_workflow else 1400))
    parts.append("Keep the answer compact enough to stream quickly on a local model, but do not sound clipped or robotic.")
    prompt = "\n\n".join(part for part in parts if part and part.strip())
    return _trim_text(prompt, 2800 if stable_workflow else 4200)


def build_outline_prompt(
    state: ConversationState,
    history: Iterable[dict],
    *,
    answer_record: dict | None = None,
    assumptions_to_verify: list[str] | None = None,
) -> str:
    transcript = []
    for msg in history:
        speaker = "Founder" if msg["role"] == "user" else "Mentor"
        transcript.append(f"{speaker}: {msg['content']}")
    return "\n\n".join(
        [
            OUTLINE_PROMPT
            + "\n## Channel / GTM hypothesis"
            + "\n## 90-day plan"
            + "\n\nAdditional rules:\n"
            + "- if business model, GTM, or roadmap details are weak, mark them clearly as hypotheses instead of facts\n"
            + "- use the answer record when it helps compress what the founder already said\n"
            + "- keep the conversation open-ended; this is a working draft, not a completion signal",
            f"State: {state.to_json(compact=True)}",
            (
                "Internal answer record:\n" + summarize_answer_record(answer_record, limit_domains=5)
                if answer_record
                else ""
            ),
            (
                "Assumptions still to verify:\n" + "\n".join(f"- {item}" for item in (assumptions_to_verify or [])[:4])
                if assumptions_to_verify
                else ""
            ),
            "Transcript:",
            "\n".join(transcript),
        ]
    )


def get_sector_prompt_snippet(sector: str) -> str:
    sector = (sector or "unknown").lower()
    data = SECTOR_SNIPPETS.get(sector)
    if not data:
        return ""
    _, opening = data
    if sector == "saas":
        return f"{opening} Focus first on user pain, wedge, and why this is better than current behavior."
    if sector == "d2c":
        return f"{opening} Focus first on repeat behavior, channel dependence, and whether the product has real pull."
    if sector == "fintech":
        return f"{opening} Focus first on trust, regulation, and what makes users adopt this safely."
    if sector == "marketplace":
        return f"{opening} Focus first on which side is hardest, why liquidity forms, and why people stay."
    return opening


def get_chip_suggestions(state: ConversationState, mentor_message: str = "") -> list[str]:
    if not (mentor_message or "").strip():
        return get_starter_chips(state)

    message_lower = (mentor_message or "").lower()
    for section, keywords in SECTION_QUESTION_KEYWORDS.items():
        if any(keyword in message_lower for keyword in keywords):
            if state.founder_type in {"student", "professional"}:
                return ARTICULATION_CHIPS.get(section, SECTION_CHIPS["Problem"])
            break
    for keywords, chips in QUESTION_CHIPS:
        if any(keyword in message_lower for keyword in keywords):
            return chips

    weakest = min(state.coverage.items(), key=lambda item: item[1])[0]
    if state.founder_type in {"student", "professional"}:
        return ARTICULATION_CHIPS.get(weakest, ARTICULATION_CHIPS["Problem"])
    if state.stage in ("idea", "pre-revenue") and weakest in {"Problem", "Solution", "Market", "Business Model"}:
        return SECTION_CHIPS.get(weakest, SECTION_CHIPS["Problem"])
    return SECTION_CHIPS.get(weakest, SECTION_CHIPS["Problem"])
