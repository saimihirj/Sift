"""Hybrid retriever for Sift Brain knowledge graph.

Combines:
  - Dense retrieval: ChromaDB cosine similarity (semantic)
  - Sparse retrieval: BM25-style keyword scoring (lexical)
  - Knowledge graph: entity-neighbour context expansion

This is intended as a drop-in upgrade path over backend/services/retrieval.py.
It adds richer semantic search while preserving the existing card format.

Usage:
    from sift_brain.knowledge_graph.retriever import retrieve
    cards = retrieve("What is a good LTV/CAC ratio for SaaS?", domain="saas", top_k=5)
"""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Any

from sift_brain.knowledge_graph.graph import KnowledgeGraph

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[3]
KB_DIR = ROOT_DIR / "knowledge_base" / "expert"
TOP_K_DENSE = int(os.environ.get("SIFT_BRAIN_DENSE_TOP_K", "10"))
TOP_K_SPARSE = int(os.environ.get("SIFT_BRAIN_SPARSE_TOP_K", "6"))
TOP_K_FINAL = int(os.environ.get("SIFT_BRAIN_FINAL_TOP_K", "8"))
DENSE_WEIGHT = 0.65
SPARSE_WEIGHT = 0.35

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "for",
    "how", "in", "is", "it", "of", "on", "or", "the", "to", "was",
    "what", "when", "which", "with", "you",
}


# ---------------------------------------------------------------------------
# BM25-style sparse scorer
# ---------------------------------------------------------------------------

class _BM25:
    """Lightweight BM25 implementation over KB card texts."""

    K1 = 1.5
    B = 0.75

    def __init__(self, cards: list[dict[str, Any]]) -> None:
        self.cards = cards
        self._tokenize()

    def _tokens(self, text: str) -> list[str]:
        return [
            t.lower() for t in re.findall(r"\b[a-z][a-z0-9]{1,}\b", text.lower())
            if t not in STOPWORDS and len(t) > 2
        ]

    def _tokenize(self) -> None:
        self.doc_tokens: list[list[str]] = []
        self.doc_len: list[int] = []
        for card in self.cards:
            text = " ".join([
                card.get("title", ""),
                card.get("body", ""),
                " ".join(card.get("tags", [])),
            ])
            tokens = self._tokens(text)
            self.doc_tokens.append(tokens)
            self.doc_len.append(len(tokens))

        self.avg_len = sum(self.doc_len) / max(len(self.doc_len), 1)
        N = len(self.cards)
        df: dict[str, int] = {}
        for tokens in self.doc_tokens:
            for t in set(tokens):
                df[t] = df.get(t, 0) + 1
        self.idf: dict[str, float] = {
            t: math.log((N - f + 0.5) / (f + 0.5) + 1)
            for t, f in df.items()
        }

    def score(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        query_tokens = self._tokens(query)
        scores: list[float] = []
        for i, tokens in enumerate(self.doc_tokens):
            tf_map: dict[str, int] = {}
            for t in tokens:
                tf_map[t] = tf_map.get(t, 0) + 1
            dl = self.doc_len[i]
            s = 0.0
            for qt in query_tokens:
                tf = tf_map.get(qt, 0)
                idf = self.idf.get(qt, 0.0)
                tf_norm = tf * (self.K1 + 1) / (tf + self.K1 * (1 - self.B + self.B * dl / self.avg_len))
                s += idf * tf_norm
            scores.append(s)
        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [(i, s) for i, s in indexed[:top_k] if s > 0]


# ---------------------------------------------------------------------------
# Dense (ChromaDB) retrieval
# ---------------------------------------------------------------------------

def _dense_retrieve(query: str, top_k: int, domain: str | None = None) -> list[tuple[str, float, dict]]:
    """Returns list of (card_id, score, metadata)."""
    try:
        from sift_brain.knowledge_graph.embedder import _get_collection
        collection = _get_collection()
        where = {"domain": domain} if domain else None
        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": top_k,
            "include": ["distances", "metadatas", "documents"],
        }
        if where:
            kwargs["where"] = where
        results = collection.query(**kwargs)
        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        return [
            (ids[i], 1.0 - float(distances[i]), metadatas[i])
            for i in range(len(ids))
        ]
    except Exception as exc:
        return []


# ---------------------------------------------------------------------------
# Card loader (for sparse fallback)
# ---------------------------------------------------------------------------

_card_cache: list[dict[str, Any]] | None = None
_bm25_cache: "_BM25 | None" = None


def _load_cards() -> list[dict[str, Any]]:
    global _card_cache
    if _card_cache is not None:
        return _card_cache
    cards: list[dict[str, Any]] = []
    if KB_DIR.exists():
        for path in KB_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                entries = data if isinstance(data, list) else data.get("entries", [])
                for entry in entries:
                    if isinstance(entry, dict):
                        entry.setdefault("id", path.stem + "_" + str(id(entry)))
                        entry.setdefault("title", entry.get("concept", entry.get("term", "")))
                        entry.setdefault("body", entry.get("description", entry.get("text", "")))
                        cards.append(entry)
            except Exception:
                pass
    _card_cache = cards
    return cards


def _get_bm25() -> "_BM25":
    global _bm25_cache
    if _bm25_cache is None:
        _bm25_cache = _BM25(_load_cards())
    return _bm25_cache


def _invalidate_caches() -> None:
    global _card_cache, _bm25_cache
    _card_cache = None
    _bm25_cache = None


# ---------------------------------------------------------------------------
# Graph context expansion
# ---------------------------------------------------------------------------

def _graph_expand(query: str, cards: list[dict[str, Any]], kg: KnowledgeGraph | None) -> list[dict[str, Any]]:
    """Add neighbouring graph entities as supplementary context cards."""
    if kg is None:
        return []
    extra: list[dict[str, Any]] = []
    # Extract candidate entity names from top cards
    for card in cards[:3]:
        title = card.get("title", "")
        if not title:
            continue
        neighbours = kg.neighbours(title)
        for nb in neighbours[:2]:
            extra.append({
                "id": f"graph_{nb['id']}",
                "title": nb.get("label", ""),
                "body": nb.get("description", ""),
                "domain": nb.get("domain", ""),
                "geography": nb.get("geography", ""),
                "source": "knowledge_graph",
                "_graph_relation": nb.get("_via", ""),
            })
    return extra


# ---------------------------------------------------------------------------
# Public retrieval API
# ---------------------------------------------------------------------------

def retrieve(
    query: str,
    *,
    domain: str | None = None,
    top_k: int = TOP_K_FINAL,
    use_graph: bool = True,
) -> list[dict[str, Any]]:
    """Retrieve relevant knowledge cards for a query.

    Hybrid: dense (ChromaDB) + sparse (BM25) + optional graph expansion.
    Returns a deduplicated, ranked list of card dicts.
    """
    seen_ids: set[str] = set()
    scored: list[tuple[float, dict[str, Any]]] = []

    # --- Dense retrieval ---
    dense_results = _dense_retrieve(query, top_k=TOP_K_DENSE, domain=domain)
    all_cards = _load_cards()
    id_to_card = {str(c.get("id", "")): c for c in all_cards}

    for card_id, score, metadata in dense_results:
        card = id_to_card.get(card_id) or {
            "id": card_id,
            "title": metadata.get("title", ""),
            "body": "",
            "domain": metadata.get("domain", ""),
            "geography": metadata.get("geography", ""),
            "source": metadata.get("source", ""),
            "url": metadata.get("url", ""),
        }
        if card_id not in seen_ids:
            seen_ids.add(card_id)
            scored.append((score * DENSE_WEIGHT, card))

    # --- Sparse (BM25) retrieval ---
    bm25 = _get_bm25()
    sparse_results = bm25.score(query, top_k=TOP_K_SPARSE)
    max_sparse = max((s for _, s in sparse_results), default=1.0) or 1.0
    for idx, raw_score in sparse_results:
        card = all_cards[idx]
        card_id = str(card.get("id", ""))
        norm_score = (raw_score / max_sparse) * SPARSE_WEIGHT
        if card_id not in seen_ids:
            seen_ids.add(card_id)
            scored.append((norm_score, card))
        else:
            # Boost existing dense hit
            for i, (existing_score, existing_card) in enumerate(scored):
                if str(existing_card.get("id", "")) == card_id:
                    scored[i] = (existing_score + norm_score, existing_card)
                    break

    # Sort by score
    scored.sort(key=lambda x: x[0], reverse=True)
    top_cards = [card for _, card in scored[:top_k]]

    # --- Graph expansion ---
    if use_graph:
        try:
            kg = KnowledgeGraph.load()
            if kg.entities:
                extra = _graph_expand(query, top_cards, kg)
                for card in extra:
                    card_id = str(card.get("id", ""))
                    if card_id not in seen_ids:
                        seen_ids.add(card_id)
                        top_cards.append(card)
        except Exception:
            pass

    return top_cards[:top_k]


def index_status() -> dict:
    """Return status of dense index and card cache."""
    from sift_brain.knowledge_graph.embedder import index_status as chroma_status
    return {
        "dense_index": chroma_status(),
        "sparse_cards": len(_load_cards()),
    }
