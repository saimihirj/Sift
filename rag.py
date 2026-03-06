"""RAG (Retrieval-Augmented Generation) layer for Pitch Deck Mentor.

Two ChromaDB collections:
  knowledge      — admin-managed: indexed docs, URLs, articles
  conversations  — auto-accumulated: every Q&A turn from every user session

Embeddings use all-MiniLM-L6-v2 (sentence-transformers, ~80MB, downloads once).
All imports are deferred so missing dependencies produce clear errors, not import crashes.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
CHROMA_DIR = DATA_DIR / "chroma"
INBOX_DIR = Path("knowledge_inbox")
INDEXED_LOG = DATA_DIR / ".indexed_files"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

# ── Lazy initialisation ───────────────────────────────────────────────────────

_client = None
_ef = None
_knowledge_col = None
_conversations_col = None
_vc_firms_col = None


def _embedding_fn():
    global _ef
    if _ef is None:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        _ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    return _ef


def _chroma_client():
    global _client
    if _client is None:
        import chromadb
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client


def get_collections():
    """Return (knowledge_col, conversations_col). Idempotent."""
    global _knowledge_col, _conversations_col
    if _knowledge_col is None or _conversations_col is None:
        client = _chroma_client()
        ef = _embedding_fn()
        _knowledge_col = client.get_or_create_collection(
            name="knowledge",
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
        _conversations_col = client.get_or_create_collection(
            name="conversations",
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
    return _knowledge_col, _conversations_col


def get_vc_firms_collection():
    """Return the dedicated VC firm collection."""
    global _vc_firms_col
    if _vc_firms_col is None:
        client = _chroma_client()
        ef = _embedding_fn()
        _vc_firms_col = client.get_or_create_collection(
            name="vc_firms",
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
    return _vc_firms_col


def _rag_available() -> bool:
    try:
        import chromadb  # noqa: F401
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


# ── Text chunking ─────────────────────────────────────────────────────────────

def chunk_text(
    text: str,
    source: str,
    doc_type: str,
    sector: str = "general",
) -> list[dict]:
    """Split text into overlapping chunks with metadata."""
    chunks = []
    start = 0
    idx = 0
    text = text.strip()
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append({
                "text": chunk,
                "metadata": {
                    "source": source,
                    "doc_type": doc_type,
                    "sector": sector,
                    "date_added": datetime.now(timezone.utc).isoformat(),
                    "chunk_index": idx,
                },
            })
            idx += 1
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


# ── Ingestion ─────────────────────────────────────────────────────────────────

def ingest_text(
    text: str,
    source: str,
    doc_type: str,
    sector: str = "general",
) -> int:
    """Chunk and upsert text into the knowledge collection. Returns chunk count."""
    if not _rag_available():
        logger.warning("RAG unavailable — chromadb or sentence-transformers not installed.")
        return 0
    knowledge_col, _ = get_collections()
    chunks = chunk_text(text, source, doc_type, sector)
    if not chunks:
        return 0
    ids = [f"{hashlib.md5(source.encode()).hexdigest()}::{c['metadata']['chunk_index']}" for c in chunks]
    knowledge_col.upsert(
        ids=ids,
        documents=[c["text"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks],
    )
    return len(chunks)


def ingest_file(file_path: str, sector: str = "general") -> int:
    """Parse a file using existing parsers and ingest into knowledge collection."""
    from app import _parse_pdf, _parse_docx, _parse_txt, _parse_pptx
    path = Path(file_path)
    ext = path.suffix.lower()
    parsers = {
        ".pdf": (_parse_pdf, "pdf"),
        ".docx": (_parse_docx, "document"),
        ".txt": (_parse_txt, "text"),
        ".pptx": (_parse_pptx, "presentation"),
    }
    if ext not in parsers:
        logger.warning(f"Unsupported file type: {ext}")
        return 0
    parser_fn, doc_type = parsers[ext]
    try:
        text = parser_fn(str(path))
    except Exception as e:
        logger.error(f"Failed to parse {path.name}: {e}")
        return 0
    if not text.strip():
        return 0
    return ingest_text(text, source=path.name, doc_type=doc_type, sector=sector)


def ingest_url(url: str, sector: str = "general") -> int:
    """Fetch a URL and ingest its text content into the knowledge collection."""
    try:
        import requests
        from bs4 import BeautifulSoup
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # Remove script/style noise
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        if not text.strip():
            return 0
        return ingest_text(text, source=url, doc_type="webpage", sector=sector)
    except Exception as e:
        logger.error(f"Failed to ingest URL {url}: {e}")
        return 0


def ingest_vc_firm_documents(documents: list[dict]) -> int:
    """Upsert aggregated VC firm profiles into the dedicated collection."""
    if not _rag_available() or not documents:
        return 0
    try:
        vc_firms_col = get_vc_firms_collection()
        ids = []
        texts = []
        metadatas = []
        for index, document in enumerate(documents):
            source = document.get("source", f"vc-firm-{index}")
            stable = document.get("id") or hashlib.md5(source.encode()).hexdigest()
            ids.append(stable)
            texts.append(document.get("text", ""))
            metadatas.append(
                {
                    "source": source,
                    "doc_type": document.get("doc_type", "vc_firm_profile"),
                    "website": document.get("website", ""),
                    "portfolio_count": int(document.get("portfolio_count", 0) or 0),
                    "date_added": document.get("date_added", datetime.now(timezone.utc).isoformat()),
                }
            )
        vc_firms_col.upsert(ids=ids, documents=texts, metadatas=metadatas)
        return len(ids)
    except Exception as e:
        logger.error(f"ingest_vc_firm_documents failed: {e}")
        return 0


def ingest_inbox() -> int:
    """Index any unindexed files in knowledge_inbox/. Returns new chunk count."""
    INBOX_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)
    indexed = set()
    if INDEXED_LOG.exists():
        indexed = set(INDEXED_LOG.read_text().splitlines())

    total = 0
    supported = {".pdf", ".docx", ".txt", ".pptx"}
    new_indexed = []

    for f in sorted(INBOX_DIR.iterdir()):
        if f.suffix.lower() not in supported:
            continue
        if f.name in indexed:
            continue
        n = ingest_file(str(f))
        if n > 0:
            total += n
            new_indexed.append(f.name)
            logger.info(f"Indexed {f.name}: {n} chunks")

    if new_indexed:
        with INDEXED_LOG.open("a") as fh:
            fh.write("\n".join(new_indexed) + "\n")

    return total


# ── Retrieval ─────────────────────────────────────────────────────────────────

def retrieve_knowledge(
    query: str,
    top_k: int = 3,
    sector_filter: str | None = None,
) -> list[dict]:
    """Retrieve top-k relevant chunks from the knowledge collection."""
    if not _rag_available():
        return []
    try:
        knowledge_col, _ = get_collections()
        if knowledge_col.count() == 0:
            return []
        where = None
        if sector_filter and sector_filter not in ("unknown", "general", ""):
            where = {"sector": {"$in": [sector_filter, "general"]}}
        results = knowledge_col.query(
            query_texts=[query],
            n_results=min(top_k, knowledge_col.count()),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        chunks = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append({"text": doc, "source": meta.get("source", ""), "distance": dist})
        return chunks
    except Exception as e:
        logger.error(f"retrieve_knowledge failed: {e}")
        return []


def retrieve_vc_firm_documents(query: str, top_k: int = 3) -> list[dict]:
    """Retrieve top VC firm profiles from the dedicated collection."""
    if not _rag_available():
        return []
    try:
        vc_firms_col = get_vc_firms_collection()
        if vc_firms_col.count() == 0:
            return []
        results = vc_firms_col.query(
            query_texts=[query],
            n_results=min(top_k, vc_firms_col.count()),
            include=["documents", "metadatas", "distances"],
        )
        chunks = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append(
                {
                    "text": doc,
                    "source": meta.get("source", ""),
                    "website": meta.get("website", ""),
                    "portfolio_count": int(meta.get("portfolio_count", 0) or 0),
                    "distance": dist,
                }
            )
        return chunks
    except Exception as e:
        logger.error(f"retrieve_vc_firm_documents failed: {e}")
        return []


def store_conversation_turn(
    session_id: str,
    role: str,
    content: str,
    metadata: dict,
) -> None:
    """Store a Q&A turn in the conversations collection for cross-user learning."""
    if not _rag_available() or not session_id:
        return
    try:
        _, conversations_col = get_collections()
        turn_index = conversations_col.count()
        doc_id = f"{session_id}::{turn_index}"
        meta = {
            "session_id": session_id,
            "role": role,
            "founder_type": metadata.get("founder_type", "unknown"),
            "sector": metadata.get("sector", "unknown"),
            "stage": metadata.get("stage", "unknown"),
            "phase": metadata.get("phase", "intro"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        conversations_col.upsert(ids=[doc_id], documents=[content], metadatas=[meta])
    except Exception as e:
        logger.error(f"store_conversation_turn failed: {e}")


def retrieve_conversations(
    query: str,
    top_k: int = 2,
    sector: str | None = None,
    founder_type: str | None = None,
) -> list[dict]:
    """Retrieve similar past Q&A turns from other sessions."""
    if not _rag_available():
        return []
    try:
        _, conversations_col = get_collections()
        if conversations_col.count() < 3:  # not enough data yet
            return []
        where_conditions = []
        if sector and sector not in ("unknown", ""):
            where_conditions.append({"sector": sector})
        if founder_type and founder_type not in ("unknown", ""):
            where_conditions.append({"founder_type": founder_type})
        where = {"$and": where_conditions} if len(where_conditions) > 1 else (where_conditions[0] if where_conditions else None)
        results = conversations_col.query(
            query_texts=[query],
            n_results=min(top_k, conversations_col.count()),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        chunks = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append({
                "text": doc,
                "role": meta.get("role", ""),
                "sector": meta.get("sector", ""),
                "founder_type": meta.get("founder_type", ""),
                "distance": dist,
            })
        return chunks
    except Exception as e:
        logger.error(f"retrieve_conversations failed: {e}")
        return []


# ── Admin helpers ─────────────────────────────────────────────────────────────

def list_knowledge_sources() -> list[dict]:
    """Return all unique sources in the knowledge collection."""
    if not _rag_available():
        return []
    try:
        knowledge_col, _ = get_collections()
        if knowledge_col.count() == 0:
            return []
        results = knowledge_col.get(include=["metadatas"])
        seen = {}
        for meta in results["metadatas"]:
            src = meta.get("source", "unknown")
            if src not in seen:
                seen[src] = {
                    "source": src,
                    "doc_type": meta.get("doc_type", ""),
                    "sector": meta.get("sector", "general"),
                    "date_added": meta.get("date_added", ""),
                    "chunk_count": 0,
                }
            seen[src]["chunk_count"] += 1
        return sorted(seen.values(), key=lambda x: x["date_added"], reverse=True)
    except Exception as e:
        logger.error(f"list_knowledge_sources failed: {e}")
        return []


def delete_source(source: str) -> int:
    """Delete all chunks from a given source. Returns deleted count."""
    if not _rag_available():
        return 0
    try:
        knowledge_col, _ = get_collections()
        results = knowledge_col.get(where={"source": source}, include=["metadatas"])
        ids = results.get("ids", [])
        if ids:
            knowledge_col.delete(ids=ids)
        return len(ids)
    except Exception as e:
        logger.error(f"delete_source failed: {e}")
        return 0


def format_rag_context(knowledge_chunks: list[dict], conversation_chunks: list[dict]) -> str:
    """Format retrieved chunks for injection into the system prompt."""
    if not knowledge_chunks and not conversation_chunks:
        return ""

    parts = ["## Retrieved Context\n"]

    if knowledge_chunks:
        parts.append("### From Knowledge Base")
        for chunk in knowledge_chunks:
            src = chunk.get("source", "")
            parts.append(f"{chunk['text']}\n*Source: {src}*")

    if conversation_chunks:
        parts.append("\n### From Similar Founder Conversations")
        for chunk in conversation_chunks:
            role = chunk.get("role", "")
            sector = chunk.get("sector", "")
            label = "Founder" if role == "user" else "Mentor"
            context = f"[{sector}]" if sector and sector != "unknown" else ""
            parts.append(f"{label} {context}: {chunk['text']}")

    return "\n".join(parts)


def get_rag_stats() -> dict:
    """Return basic stats about the RAG collections."""
    if not _rag_available():
        return {"available": False}
    try:
        knowledge_col, conversations_col = get_collections()
        vc_firms_col = get_vc_firms_collection()
        sources = list_knowledge_sources()
        return {
            "available": True,
            "knowledge_chunks": knowledge_col.count(),
            "knowledge_sources": len(sources),
            "conversation_turns": conversations_col.count(),
            "vc_firm_profiles": vc_firms_col.count(),
        }
    except Exception as e:
        return {"available": False, "error": str(e)}
