"""Compact prompt builders for the local-first mentor backend."""

from __future__ import annotations

from typing import Iterable

from knowledge import D2C_KNOWLEDGE, FINTECH_KNOWLEDGE, MARKETPLACE_KNOWLEDGE, SAAS_KNOWLEDGE
from state import ConversationState


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

BASE_MENTOR_PROMPT = """You are a sharp pitch mentor for startup founders.

You are not a generic chatbot. You are a proper mentor helping founders sharpen investor thinking.

Response rules:
- maximum 60 words total
- maximum 2 sentences before the final question
- ask exactly 1 short question
- final question must be 12 words or fewer
- never ask compound questions
- never use bullet points in chat
- do not sound corporate or theatrical
- study the core idea before chasing metrics
- do not force jargon or metrics the founder has not earned yet
- if you use a startup term, write the full phrase first, not just the acronym
- if you use a startup term, explain it immediately in simple words
- do not invent personas, labels, or facts the founder did not give you
- if the founder is vague, narrow the problem
- if the founder is clear, move to the next real weakness
- if the founder seems confused, switch to plain language immediately

Treat retrieved context as background only.
When a document is attached, react to one strong signal from it, then ask one short next-step question.
"""

MENTOR_ROLE_PROMPT = """Mentor role:
- help teams clarify the real problem they are solving
- test assumptions and ask for evidence, not just opinions
- keep the conversation anchored on problem, approach, and customer discovery, not just the final tech
- share short practical frameworks or examples to illustrate a point
- do not turn the session into a lecture, slide review, funding promise, or your favorite solution
- when the founder wants to close the session, end with 1 to 3 concrete next steps
"""

FOUNDER_STYLE = {
    "student": "Use simple language, teach lightly, avoid jargon unless immediately explained, and ask the most basic useful question first.",
    "professional": "Assume work experience but not startup fluency. Translate business jargon into plain startup logic.",
    "founder": "Assume commitment and some context. Push on the highest-leverage weakness without over-explaining basics.",
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
    "professional": "You know work; now we test whether this is a startup-scale problem.",
    "founder": "Good. Let us make the story harder to break.",
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

OUTLINE_PROMPT = """Turn the transcript into a founder-ready markdown outline for Signal.

Use these sections exactly:
# Company Name — Pitch Outline
## Problem
## Solution
## Market Opportunity
## Business Model
## Traction & Validation
## Team
## The Ask
## Strengths To Lean Into
## Gaps To Fix Before Pitching

Rules:
- use the founder's framing where it is sharp
- mark weak sections as [Needs further exploration]
- be specific and concise
- no marketing fluff
"""


def build_personalized_opening(founder_type: str, sector: str, stage: str) -> str:
    prompt = STAGE_PROMPTS.get(stage, STAGE_PROMPTS["unknown"])
    sector_line = get_sector_prompt_snippet(sector)
    parts = ["Hi. What are you building?"]
    if prompt:
        parts.append(prompt)
    if sector_line:
        parts.append(sector_line)
    return " ".join(parts[:3])


def get_starter_chips(state: ConversationState) -> list[str]:
    if state.founder_type == "student":
        return STUDENT_STARTER_CHIPS
    if state.founder_type == "professional":
        return PROFESSIONAL_STARTER_CHIPS
    if state.founder_type == "serial":
        return SERIAL_STARTER_CHIPS
    return STARTER_CHIPS.get(state.stage, STARTER_CHIPS["unknown"])


def founder_needs_simple_language(state: ConversationState, last_user_message: str = "") -> bool:
    if state.founder_type == "student":
        return True
    message = (last_user_message or "").lower()
    return any(cue in message for cue in CONFUSION_CUES)


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


def is_wrap_up_turn(last_user_message: str = "") -> bool:
    message = (last_user_message or "").lower()
    return any(cue in message for cue in WRAP_UP_CUES)


def get_section_question_lens(state: ConversationState) -> str:
    if not state.coverage:
        return SECTION_QUESTION_LENSES["Problem"]
    weakest = min(state.coverage.items(), key=lambda item: item[1])[0]
    return SECTION_QUESTION_LENSES.get(weakest, SECTION_QUESTION_LENSES["Problem"])


def build_system_prompt(
    state: ConversationState,
    retrieval_context: str = "",
    last_user_message: str = "",
) -> str:
    parts = [
        BASE_MENTOR_PROMPT,
        MENTOR_ROLE_PROMPT,
        f"Founder profile: {FOUNDER_STYLE.get(state.founder_type, FOUNDER_STYLE['unknown'])}",
        f"Conversation mode: {MODE_STYLE.get(state.mode, MODE_STYLE['think_it_through'])}",
        f"Stage lens: {STAGE_STYLE.get(state.stage, STAGE_STYLE['unknown'])}",
        get_section_question_lens(state),
        f"Current phase: {state.phase}. Sector: {state.sector}. Stage: {state.stage}. Urgency: {'yes' if state.urgency else 'no'}.",
        f"State snapshot: {state.to_json(compact=True)}",
    ]
    if founder_needs_simple_language(state, last_user_message):
        parts.append("The founder needs plain language. Use simpler words and ask a narrower question.")
        parts.append(build_simple_language_instruction())
    if is_wrap_up_turn(last_user_message):
        parts.append(
            "The founder is wrapping up. Do not ask a question. Give 1 to 3 concrete next steps "
            "they can realistically do next, each short and specific."
        )
    if retrieval_context:
        parts.append(retrieval_context)
    parts.append("Keep the answer short enough to stream quickly on a local model.")
    return "\n\n".join(parts)


def build_outline_prompt(state: ConversationState, history: Iterable[dict]) -> str:
    transcript = []
    for msg in history:
        speaker = "Founder" if msg["role"] == "user" else "Mentor"
        transcript.append(f"{speaker}: {msg['content']}")
    return "\n\n".join(
        [
            OUTLINE_PROMPT,
            f"State: {state.to_json(compact=True)}",
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
    for keywords, chips in QUESTION_CHIPS:
        if any(keyword in message_lower for keyword in keywords):
            return chips

    weakest = min(state.coverage.items(), key=lambda item: item[1])[0]
    if state.stage in ("idea", "pre-revenue") and weakest in {"Problem", "Solution", "Market", "Business Model"}:
        return SECTION_CHIPS.get(weakest, SECTION_CHIPS["Problem"])
    return SECTION_CHIPS.get(weakest, SECTION_CHIPS["Problem"])
