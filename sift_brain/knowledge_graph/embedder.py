"""ChromaDB embedder for Sift Brain knowledge graph.

Indexes all knowledge base cards (static + dynamic shards) into a persistent
ChromaDB vector store at data/chroma/.

Supports incremental updates — only new card IDs are embedded.

Usage:
    from sift_brain.knowledge_graph.embedder import rebuild_index, add_cards
    rebuild_index()          # full index rebuild
    add_cards(new_cards)     # incremental update
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[3]
KB_DIR = ROOT_DIR / "knowledge_base" / "expert"
CHROMA_DIR = ROOT_DIR / "data" / "chroma"
COLLECTION_NAME = "sift_knowledge"
EMBEDDING_MODEL = os.environ.get("SIFT_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
BATCH_SIZE = 64


# ---------------------------------------------------------------------------
# Lazy imports — fail gracefully if packages not installed
# ---------------------------------------------------------------------------

def _get_chroma_client():
    try:
        import chromadb
        return chromadb.PersistentClient(path=str(CHROMA_DIR))
    except ImportError:
        raise RuntimeError(
            "chromadb is required for knowledge graph embedding. "
            "Install it with: pip install chromadb>=0.5.0"
        )


def _get_embedding_fn():
    try:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        return SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    except ImportError:
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(EMBEDDING_MODEL)

            class _Fn:
                def __call__(self, texts):
                    return model.encode(texts, show_progress_bar=False).tolist()

            return _Fn()
        except ImportError:
            raise RuntimeError(
                "sentence-transformers is required for embedding. "
                "Install it with: pip install sentence-transformers>=3.0.0"
            )


# ---------------------------------------------------------------------------
# Load all KB cards from disk
# ---------------------------------------------------------------------------

def _load_all_cards() -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    if not KB_DIR.exists():
        return cards
    for path in KB_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            entries = data if isinstance(data, list) else data.get("entries", [])
            for entry in entries:
                if isinstance(entry, dict):
                    # Normalise: ensure id, title, body
                    entry.setdefault("id", path.stem + "_" + str(hash(str(entry)))[:8])
                    entry.setdefault("title", entry.get("concept", entry.get("term", "")))
                    entry.setdefault("body", entry.get("description", entry.get("text", "")))
                    if entry.get("title") or entry.get("body"):
                        cards.append(entry)
        except Exception as exc:
            print(f"[embedder] skipped {path.name}: {exc}")
    return cards


def _card_text(card: dict[str, Any]) -> str:
    parts = [card.get("title", ""), card.get("body", "")]
    tags = card.get("tags", [])
    if tags:
        parts.append("Tags: " + ", ".join(str(t) for t in tags))
    return " | ".join(p for p in parts if p).strip()


def _card_metadata(card: dict[str, Any]) -> dict[str, Any]:
    """Chroma metadata must be str/int/float/bool only."""
    return {
        "domain": str(card.get("domain", "")),
        "geography": str(card.get("geography", "")),
        "source": str(card.get("source", "")),
        "url": str(card.get("url", "")),
        "updated_at": str(card.get("updated_at", "")),
        "title": str(card.get("title", ""))[:256],
    }


# ---------------------------------------------------------------------------
# Index management
# ---------------------------------------------------------------------------

def _get_collection():
    client = _get_chroma_client()
    embedding_fn = _get_embedding_fn()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )


def add_cards(cards: list[dict[str, Any]], *, verbose: bool = True) -> int:
    """Add new cards to the ChromaDB index.  Skips cards already indexed."""
    if not cards:
        return 0

    collection = _get_collection()
    existing = set(collection.get(include=[])["ids"])

    new_cards = [c for c in cards if str(c.get("id", "")) not in existing]
    if not new_cards:
        if verbose:
            print("[embedder] All cards already indexed.")
        return 0

    added = 0
    for i in range(0, len(new_cards), BATCH_SIZE):
        batch = new_cards[i : i + BATCH_SIZE]
        ids = [str(c["id"]) for c in batch]
        documents = [_card_text(c) for c in batch]
        metadatas = [_card_metadata(c) for c in batch]
        collection.add(ids=ids, documents=documents, metadatas=metadatas)
        added += len(batch)

    if verbose:
        print(f"[embedder] Indexed {added} new cards into '{COLLECTION_NAME}'.")
    return added


def rebuild_index(*, verbose: bool = True) -> int:
    """Full rebuild: delete existing collection and re-index all KB cards."""
    client = _get_chroma_client()
    try:
        client.delete_collection(COLLECTION_NAME)
        if verbose:
            print(f"[embedder] Deleted existing collection '{COLLECTION_NAME}'.")
    except Exception:
        pass

    cards = _load_all_cards()
    if verbose:
        print(f"[embedder] Loaded {len(cards)} cards from {KB_DIR}")

    if not cards:
        return 0
    return add_cards(cards, verbose=verbose)


def index_status() -> dict[str, Any]:
    """Return current index statistics."""
    try:
        collection = _get_collection()
        count = collection.count()
        return {
            "collection": COLLECTION_NAME,
            "card_count": count,
            "chroma_dir": str(CHROMA_DIR),
            "embedding_model": EMBEDDING_MODEL,
            "status": "ready",
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
