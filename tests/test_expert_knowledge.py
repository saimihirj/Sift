from __future__ import annotations

import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.expert_agent import build_analysis_snapshot, classify_expert_turn
from backend.services.expert_knowledge import expert_card_count, expert_data_dir, retrieve_expert_cards, suggest_knowledge_lane


class ExpertKnowledgeTests(unittest.TestCase):
    def test_repo_bundled_corpus_is_available(self) -> None:
        data_dir = expert_data_dir()
        self.assertTrue(data_dir.exists())
        self.assertTrue((Path(data_dir) / "kb_part_rounds.json").exists())

    def test_corpus_loads_cards(self) -> None:
        self.assertGreater(expert_card_count(), 50)

    def test_exact_term_retrieval_prefers_safe(self) -> None:
        cards = retrieve_expert_cards("SAFE vs convertible note", lane="vc", geography="global", top_k=4)
        titles = {card["title"].lower() for card in cards}
        self.assertTrue(any("safe" in title for title in titles))

    def test_lane_suggestion_handles_fintech_infra(self) -> None:
        self.assertEqual(suggest_knowledge_lane("How does UPI compare with OCEN for Indian fintech flows?"), "fintech_infra")

    def test_expert_router_detects_compare(self) -> None:
        route = classify_expert_turn("Compare SAFE vs convertible note for a pre-seed founder", help_mode="coach_me")
        self.assertEqual(route["action"], "compare")
        self.assertEqual(route["knowledgeLane"], "vc")

    def test_analysis_snapshot_surfaces_missing_evidence(self) -> None:
        snapshot = build_analysis_snapshot(
            query="Pre-screen this startup idea",
            route={"action": "pre_screen", "knowledgeLane": "startup"},
            retrieval={
                "concepts": ["Product Market Fit", "Market Sizing"],
                "uploadSnippets": [],
                "sources": [],
                "usedLiveWeb": False,
                "retrievalGap": "The local expert corpus does not have a strong direct hit for this question yet.",
            },
        )
        self.assertTrue(snapshot["missingEvidence"])

    def test_health_reports_expert_corpus_status(self) -> None:
        client = TestClient(app)
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreater(payload.get("expertCardCount", 0), 50)
        self.assertTrue(payload.get("expertDataDir"))


if __name__ == "__main__":
    unittest.main()
