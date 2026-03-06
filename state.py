"""Conversation state tracking for the Socratic engine."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


SECTIONS = ["Problem", "Solution", "Market", "Business Model", "Traction", "Team", "Ask"]

URGENCY_SIGNALS = [
    "demo day", "pitch on", "meeting on", "this week", "tomorrow",
    "friday", "monday", "next week", "in 2 days", "in 3 days", "deadline",
]


@dataclass
class NumberClaim:
    """A numeric claim made by the founder."""
    claim: str
    source_provided: bool = False
    challenged: bool = False
    stress_tested: bool = False

    def to_dict(self) -> dict:
        return {
            "claim": self.claim,
            "source_provided": self.source_provided,
            "challenged": self.challenged,
            "stress_tested": self.stress_tested,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NumberClaim":
        return cls(
            claim=data.get("claim", ""),
            source_provided=bool(data.get("source_provided", False)),
            challenged=bool(data.get("challenged", False)),
            stress_tested=bool(data.get("stress_tested", False)),
        )


@dataclass
class ConversationState:
    """Tracks the full state of a founder conversation."""

    # Section coverage (0-100)
    coverage: dict = field(default_factory=lambda: {s: 0 for s in SECTIONS})

    # Detected founder profile (from conversation analysis)
    sector: str = "unknown"      # "saas", "d2c", "fintech", "marketplace", "unknown"
    stage: str = "unknown"       # "idea", "pre-revenue", "early-revenue", "growth"
    company_name: str = ""

    # Onboarding-collected profile
    founder_type: str = "unknown"   # "student", "professional", "founder", "serial"
    mode: str = "think_it_through"  # "think_it_through", "quick_stress_test"
    urgency: bool = False           # True if pitch deadline detected

    # Number claims tracking
    number_claims: list = field(default_factory=list)

    # Conversation phase
    phase: str = "intro"  # "intro", "exploration", "deep_dive", "synthesis"
    turns: int = 0

    # Key facts extracted
    facts: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize state into a plain dictionary."""
        return {
            "coverage": self.coverage,
            "sector": self.sector,
            "stage": self.stage,
            "company_name": self.company_name,
            "founder_type": self.founder_type,
            "mode": self.mode,
            "urgency": self.urgency,
            "number_claims": [n.to_dict() for n in self.number_claims],
            "phase": self.phase,
            "turns": self.turns,
            "facts": self.facts,
        }

    def to_json(self, compact: bool = False) -> str:
        """Serialize state to JSON for injection into prompts or APIs."""
        if compact:
            return json.dumps(self.to_dict(), separators=(",", ":"))
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict | None) -> "ConversationState":
        """Rehydrate state from a dictionary."""
        state = cls()
        if not data:
            return state

        coverage = data.get("coverage", {})
        if isinstance(coverage, dict):
            for section in SECTIONS:
                if section in coverage:
                    state.coverage[section] = int(coverage[section])

        state.sector = data.get("sector", state.sector)
        state.stage = data.get("stage", state.stage)
        state.company_name = data.get("company_name", state.company_name)
        state.founder_type = data.get("founder_type", state.founder_type)
        state.mode = data.get("mode", state.mode)
        state.urgency = bool(data.get("urgency", state.urgency))
        state.phase = data.get("phase", state.phase)
        state.turns = int(data.get("turns", state.turns))
        facts = data.get("facts", {})
        if isinstance(facts, dict):
            state.facts = facts
        state.number_claims = [
            NumberClaim.from_dict(item)
            for item in data.get("number_claims", [])
            if isinstance(item, dict)
        ]
        return state

    @classmethod
    def from_json(cls, state_json: str | None) -> "ConversationState":
        """Rehydrate state from JSON."""
        if not state_json:
            return cls()
        return cls.from_dict(json.loads(state_json))

    def add_number_claim(self, claim: str, source_provided: bool = False) -> None:
        """Append a numeric claim if it has not already been captured."""
        normalized = claim.strip()
        if not normalized:
            return
        if any(n.claim == normalized for n in self.number_claims):
            return
        self.number_claims.append(
            NumberClaim(claim=normalized, source_provided=source_provided)
        )

    def update_from_analysis(self, analysis: dict):
        """Update state from LLM's structured analysis response."""
        if "coverage_updates" in analysis:
            for section, score in analysis["coverage_updates"].items():
                if section in self.coverage:
                    self.coverage[section] = min(100, max(self.coverage[section], score))

        # Only override sector/stage from onboarding if still unknown
        if "sector" in analysis and analysis["sector"] in ("saas", "d2c", "fintech", "marketplace"):
            if self.sector == "unknown":
                self.sector = analysis["sector"]

        if "stage" in analysis and analysis["stage"] in ("idea", "pre-revenue", "early-revenue", "growth"):
            if self.stage == "unknown":
                self.stage = analysis["stage"]

        if "company_name" in analysis and analysis["company_name"]:
            self.company_name = analysis["company_name"]

        if "new_number_claims" in analysis:
            for claim_data in analysis["new_number_claims"]:
                self.number_claims.append(NumberClaim(
                    claim=claim_data.get("claim", ""),
                    source_provided=claim_data.get("source_provided", False),
                ))

        if "facts" in analysis:
            self.facts.update(analysis["facts"])

        if "phase" in analysis and analysis["phase"] in ("intro", "exploration", "deep_dive", "synthesis"):
            self.phase = analysis["phase"]

        # Detect urgency from conversation facts
        facts_str = str(self.facts).lower()
        if any(signal in facts_str for signal in URGENCY_SIGNALS):
            self.urgency = True

        self.turns += 1

    def get_missing_sections(self) -> list[str]:
        """Return sections with coverage below 30%."""
        return [s for s, v in self.coverage.items() if v < 30]

    def get_unchallenged_numbers(self) -> list[NumberClaim]:
        """Return number claims that haven't been challenged yet."""
        return [n for n in self.number_claims if not n.source_provided and not n.challenged]

    def overall_coverage(self) -> float:
        """Average coverage across all sections."""
        return sum(self.coverage.values()) / len(self.coverage)
