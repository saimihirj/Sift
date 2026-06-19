"""Entity-relationship knowledge graph for Sift Brain.

Builds a lightweight graph structure from KB cards — no external graph DB needed.
Entities: companies, investors, markets, metrics, frameworks, sectors.
Relationships: competes_with, funded_by, applies_to_sector, benchmarks_against, part_of.

The graph is persisted as JSON at data/knowledge_graph.json and can be
queried for neighbours, relationship chains, and entity summaries.

Usage:
    from sift_brain.knowledge_graph.graph import KnowledgeGraph
    kg = KnowledgeGraph.load()
    kg.add_entity("Stripe", kind="company", domain="fintech")
    kg.add_relation("Stripe", "competes_with", "Razorpay")
    kg.save()
    neighbours = kg.neighbours("Stripe")
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"
GRAPH_PATH = DATA_DIR / "knowledge_graph.json"

# Entity kinds
ENTITY_KINDS = {
    "company", "investor", "market", "metric", "framework",
    "sector", "geography", "regulation", "concept",
}

# Relation types
RELATION_TYPES = {
    "competes_with",
    "funded_by",
    "applies_to_sector",
    "benchmarks_against",
    "part_of",
    "related_to",
    "located_in",
    "regulated_by",
    "enables",
    "disrupts",
}


class KnowledgeGraph:
    """In-memory entity-relationship graph with JSON persistence."""

    def __init__(self) -> None:
        self.entities: dict[str, dict[str, Any]] = {}   # id -> {label, kind, domain, ...}
        self.relations: list[dict[str, str]] = []        # [{source, relation, target}]

    # ---- Entity management ------------------------------------------------

    def add_entity(
        self,
        label: str,
        *,
        kind: str = "concept",
        domain: str = "",
        geography: str = "",
        description: str = "",
        url: str = "",
        **extra: Any,
    ) -> str:
        """Add or update an entity. Returns the entity id."""
        entity_id = _normalize_id(label)
        self.entities[entity_id] = {
            "id": entity_id,
            "label": label,
            "kind": kind if kind in ENTITY_KINDS else "concept",
            "domain": domain,
            "geography": geography,
            "description": description,
            "url": url,
            **extra,
        }
        return entity_id

    def get_entity(self, label: str) -> dict[str, Any] | None:
        return self.entities.get(_normalize_id(label))

    def has_entity(self, label: str) -> bool:
        return _normalize_id(label) in self.entities

    # ---- Relation management -----------------------------------------------

    def add_relation(self, source: str, relation: str, target: str) -> None:
        """Add a directed relationship between two entities (auto-creates if missing)."""
        if not self.has_entity(source):
            self.add_entity(source)
        if not self.has_entity(target):
            self.add_entity(target)

        rel_type = relation if relation in RELATION_TYPES else "related_to"
        entry = {
            "source": _normalize_id(source),
            "relation": rel_type,
            "target": _normalize_id(target),
        }
        if entry not in self.relations:
            self.relations.append(entry)

    def neighbours(self, label: str, *, relation: str | None = None) -> list[dict[str, Any]]:
        """Return neighbouring entities (both directions)."""
        eid = _normalize_id(label)
        result: list[dict[str, Any]] = []
        for rel in self.relations:
            if rel["source"] == eid or rel["target"] == eid:
                if relation and rel["relation"] != relation:
                    continue
                other_id = rel["target"] if rel["source"] == eid else rel["source"]
                entity = self.entities.get(other_id)
                if entity:
                    result.append({**entity, "_via": rel["relation"]})
        return result

    def find_by_domain(self, domain: str) -> list[dict[str, Any]]:
        return [e for e in self.entities.values() if e.get("domain") == domain]

    def find_by_kind(self, kind: str) -> list[dict[str, Any]]:
        return [e for e in self.entities.values() if e.get("kind") == kind]

    # ---- Auto-extraction from KB cards ------------------------------------

    def ingest_cards(self, cards: list[dict[str, Any]]) -> int:
        """Extract entities and relationships from KB cards heuristically."""
        added = 0
        for card in cards:
            title = card.get("title", "")
            domain = card.get("domain", "")
            geo = card.get("geography", "")

            if not title:
                continue

            # Infer entity kind from domain
            kind_map = {
                "fintech": "company", "saas": "company", "d2c": "company",
                "india_vc": "investor", "vc_terms": "framework",
                "pe_growth": "investor", "macro": "metric",
                "regulation_india": "regulation",
                "market_sizing": "market", "pmf_gtm": "framework",
            }
            kind = kind_map.get(domain, "concept")

            self.add_entity(
                title,
                kind=kind,
                domain=domain,
                geography=geo,
                description=card.get("body", "")[:200],
                url=card.get("url", ""),
            )
            added += 1

            # Link sector entities
            for tag in card.get("tags", []):
                self.add_entity(str(tag), kind="sector", domain=domain)
                self.add_relation(title, "applies_to_sector", str(tag))

        return added

    # ---- Persistence -------------------------------------------------------

    def save(self, path: Path | None = None) -> None:
        target = path or GRAPH_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {"entities": self.entities, "relations": self.relations},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path | None = None) -> "KnowledgeGraph":
        target = path or GRAPH_PATH
        kg = cls()
        if not target.exists():
            return kg
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            kg.entities = data.get("entities", {})
            kg.relations = data.get("relations", [])
        except Exception as exc:
            print(f"[graph] Could not load graph: {exc}")
        return kg

    # ---- Stats -------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        kind_counts: dict[str, int] = {}
        rel_counts: dict[str, int] = {}
        for e in self.entities.values():
            kind_counts[e.get("kind", "unknown")] = kind_counts.get(e.get("kind", "unknown"), 0) + 1
        for r in self.relations:
            rel_counts[r["relation"]] = rel_counts.get(r["relation"], 0) + 1
        return {
            "entities": len(self.entities),
            "relations": len(self.relations),
            "entity_kinds": kind_counts,
            "relation_types": rel_counts,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_id(label: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", label.strip().lower())[:64]
