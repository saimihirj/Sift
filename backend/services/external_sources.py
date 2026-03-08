"""Curated investor-questioning lenses from external startup sources."""

from __future__ import annotations

from state import ConversationState


VC_RESEARCH_SNIPPETS = [
    {
        "id": "sequoia-right-to-exist",
        "source": "Sequoia",
        "title": "Right to exist",
        "url": "https://sequoiacap.com/article/pmf-framework-2/",
        "guidance": (
            "Pressure-test the company's right to exist: why this market matters now, "
            "what wedge gets the first user, and why this founder has an edge."
        ),
        "tags": (
            "idea",
            "why now",
            "wedge",
            "category",
            "market",
            "founder-market fit",
            "right to exist",
            "unique advantage",
        ),
        "stages": ("idea", "pre-revenue", "unknown"),
        "sections": ("Problem", "Market", "Team"),
        "priority": 1,
    },
    {
        "id": "sequoia-care-enough",
        "source": "Sequoia",
        "title": "Do people care enough?",
        "url": "https://sequoiacap.com/article/pmf-framework-2/",
        "guidance": (
            "Before metrics, test whether people care enough: who feels the pain most, "
            "what they do today, and whether a few early adopters would help shape it."
        ),
        "tags": (
            "customer",
            "pain",
            "problem",
            "segment",
            "care enough",
            "current behavior",
            "workaround",
            "design partner",
            "adopter",
        ),
        "stages": ("idea", "pre-revenue", "early-revenue", "unknown"),
        "sections": ("Problem", "Market", "Solution"),
        "priority": 2,
    },
    {
        "id": "firstround-problem-space",
        "source": "First Round",
        "title": "Stay in the problem space",
        "url": "https://review.firstround.com/dont-serve-burnt-pizza-and-other-lessons-in-building-minimum-lovable-products/",
        "guidance": (
            "Keep questions in the problem space first. Ask what feels tedious, stressful, "
            "or painful, and resist jumping straight into feature lists."
        ),
        "tags": (
            "problem",
            "pain point",
            "pain",
            "tedious",
            "stressful",
            "customer discovery",
            "user interview",
            "feature",
            "solution",
        ),
        "stages": ("idea", "pre-revenue", "unknown"),
        "sections": ("Problem", "Solution", "Market"),
        "priority": 3,
    },
    {
        "id": "a16z-value-hypothesis",
        "source": "a16z",
        "title": "Value hypothesis",
        "url": "https://a16z.com/12-things-about-product-market-fit/",
        "guidance": (
            "Test the value hypothesis in plain terms: what are you building, who is most "
            "likely to care, and what business model makes the exchange believable."
        ),
        "tags": (
            "value hypothesis",
            "value",
            "feature",
            "audience",
            "business model",
            "why use",
            "why buy",
            "product-market fit",
        ),
        "stages": ("idea", "pre-revenue", "early-revenue", "unknown"),
        "sections": ("Solution", "Market", "Business Model"),
        "priority": 4,
    },
    {
        "id": "firstround-personas-pricing",
        "source": "First Round",
        "title": "Buyer personas and pricing",
        "url": "https://review.firstround.com/the-price-is-right-essential-tips-for-nailing-your-pricing-strategy/",
        "guidance": (
            "Use a few clear buyer personas and simple willingness-to-pay questions. Which "
            "feature matters most, which matters least, and what would this segment pay for?"
        ),
        "tags": (
            "persona",
            "buyer",
            "segment",
            "cohort",
            "pricing",
            "willingness to pay",
            "feature preference",
            "value metric",
        ),
        "stages": ("pre-revenue", "early-revenue", "growth", "unknown"),
        "sections": ("Market", "Business Model"),
        "priority": 5,
    },
    {
        "id": "sequoia-behavior-change",
        "source": "Sequoia",
        "title": "Behavior change",
        "url": "https://sequoiacap.com/article/pmf-framework-2/",
        "guidance": (
            "After the pain is clear, ask whether the product changes behavior. What does "
            "the user do differently, more often, or faster if this really works?"
        ),
        "tags": (
            "behavior",
            "adoption",
            "retention",
            "engagement",
            "habit",
            "prototype",
            "pilot",
            "change behavior",
        ),
        "stages": ("pre-revenue", "early-revenue", "growth", "unknown"),
        "sections": ("Solution", "Traction"),
        "priority": 6,
    },
    {
        "id": "sequoia-pay-enough",
        "source": "Sequoia",
        "title": "Value exchange",
        "url": "https://sequoiacap.com/article/pmf-framework-2/",
        "guidance": (
            "Translate unit economics into simple language: what value does the user get, "
            "what would they pay, what does it cost to deliver, and can that support a business?"
        ),
        "tags": (
            "cost",
            "costs",
            "business model",
            "unit economics",
            "pricing",
            "revenue",
            "gross margin",
            "pay enough",
        ),
        "stages": ("pre-revenue", "early-revenue", "growth", "unknown"),
        "sections": ("Business Model", "Traction"),
        "priority": 7,
    },
    {
        "id": "xraise-antler-spike",
        "source": "XRaise",
        "title": "Antler founder spike",
        "url": "https://xraise.ai/blog/your-antler-accelerator-interview-how-to-stand-out-and-succeed/",
        "guidance": (
            "For Antler-style interviews, lead with founder-first differentiation: your spike, the evidence behind it, "
            "and why you are unusually credible to build in this space. The spike can be domain depth, execution history, "
            "unique market insight, or resilience under pressure."
        ),
        "tags": (
            "antler",
            "accelerator",
            "interview",
            "founder spike",
            "spike",
            "why me",
            "differentiation",
            "founder psychology",
        ),
        "mustMatch": ("antler", "accelerator", "interview", "founder spike", "spike", "why antler"),
        "stages": ("idea", "pre-revenue", "early-revenue", "unknown"),
        "sections": ("Team", "Ask"),
        "priority": 8,
    },
    {
        "id": "xraise-antler-motivation",
        "source": "XRaise",
        "title": "Antler motivation and fit",
        "url": "https://xraise.ai/blog/your-antler-accelerator-interview-how-to-stand-out-and-succeed/",
        "guidance": (
            "Prepare four simple motivation answers: why founder, why this space, why now, and why Antler. "
            "Antler-style prep should avoid generic ambition and show real program fit, cohort fit, and self-awareness."
        ),
        "tags": (
            "antler",
            "why founder",
            "why this space",
            "why now",
            "why antler",
            "motivation",
            "program fit",
            "cohort fit",
        ),
        "mustMatch": ("antler", "why antler", "accelerator", "program fit", "founder motivation"),
        "stages": ("idea", "pre-revenue", "early-revenue", "unknown"),
        "sections": ("Problem", "Market", "Ask"),
        "priority": 9,
    },
    {
        "id": "xraise-antler-coachability",
        "source": "XRaise",
        "title": "Antler coachability and red flags",
        "url": "https://xraise.ai/blog/your-antler-accelerator-interview-how-to-stand-out-and-succeed/",
        "guidance": (
            "Antler-style interview prep should pressure-test founder coachability: think out loud, admit gaps, "
            "take pushback without becoming defensive, and avoid vague or buzzword-heavy answers. Red flags include fuzzy "
            "problem understanding, weak market insight, and generic reasons for applying."
        ),
        "tags": (
            "antler",
            "coachability",
            "feedback",
            "defensive",
            "red flags",
            "problem insight",
            "market insight",
            "founder psychology",
        ),
        "mustMatch": ("antler", "coachability", "accelerator", "interview", "feedback"),
        "stages": ("idea", "pre-revenue", "early-revenue", "unknown"),
        "sections": ("Problem", "Market", "Team"),
        "priority": 10,
    },
    {
        "id": "xraise-antler-team-dynamic",
        "source": "XRaise",
        "title": "Antler co-founder and execution dynamic",
        "url": "https://xraise.ai/blog/your-antler-accelerator-interview-how-to-stand-out-and-succeed/",
        "guidance": (
            "If the founder has a co-founder, Antler-style prep should check role clarity, conflict handling, and whether "
            "both founders tell the same story. For solo founders, the missing piece is whether they can clearly name the "
            "co-founder profile or capability gap they still need."
        ),
        "tags": (
            "antler",
            "cofounder",
            "co-founder",
            "team dynamic",
            "solo founder",
            "roles",
            "conflict",
            "execution",
        ),
        "mustMatch": ("antler", "cofounder", "co-founder", "solo founder", "accelerator"),
        "stages": ("idea", "pre-revenue", "early-revenue", "unknown"),
        "sections": ("Team", "Ask"),
        "priority": 11,
    },
]


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def _weakest_section(state: ConversationState) -> str:
    if not state.coverage:
        return "Problem"
    return min(state.coverage.items(), key=lambda item: item[1])[0]


def _score_snippet(snippet: dict, query: str, state: ConversationState, weakest_section: str) -> int:
    haystack = " ".join(
        part
        for part in (
            _normalize(query),
            _normalize(state.sector),
            _normalize(state.stage),
            _normalize(weakest_section),
        )
        if part
    )
    must_match = tuple(snippet.get("mustMatch", ()))
    if must_match and not any(term in haystack for term in must_match):
        return -999
    score = 0
    for tag in snippet["tags"]:
        if tag in haystack:
            score += 4
    if state.stage in snippet["stages"]:
        score += 5
    if weakest_section in snippet["sections"]:
        score += 4
    if state.stage in ("idea", "pre-revenue") and snippet["id"] in {
        "sequoia-right-to-exist",
        "sequoia-care-enough",
        "firstround-problem-space",
        "a16z-value-hypothesis",
    }:
        score += 3
    return score


def retrieve_external_research_context(
    state: ConversationState,
    query: str,
    top_k: int = 2,
    max_chars: int = 560,
) -> dict:
    weakest_section = _weakest_section(state)
    ranked = sorted(
        VC_RESEARCH_SNIPPETS,
        key=lambda snippet: (-_score_snippet(snippet, query, state, weakest_section), snippet["priority"]),
    )

    selected: list[dict] = []
    for snippet in ranked:
        if _score_snippet(snippet, query, state, weakest_section) < 0:
            continue
        selected.append(snippet)
        if len(selected) >= top_k:
            break

    formatted_parts = []
    selected_sources = []
    total_chars = 0
    for snippet in selected:
        part = f"[{snippet['source']} · {snippet['title']}]\n{snippet['guidance']}"
        if formatted_parts and total_chars + len(part) + 2 > max_chars:
            continue
        formatted_parts.append(part)
        total_chars += len(part) + 2
        selected_sources.append(
            {
                "source": snippet["source"],
                "title": snippet["title"],
                "url": snippet["url"],
            }
        )

    if not formatted_parts:
        return {"text": "", "sources": [], "promptChars": 0}

    text = "Investor lens:\n" + "\n\n".join(formatted_parts)
    return {
        "text": text,
        "sources": selected_sources,
        "promptChars": len(text),
    }
