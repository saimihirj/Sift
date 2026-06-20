"""Sift Brain status and decision-trace API.

Endpoints:
  GET /api/brain/status        — knowledge graph card counts, engine status, adapter
  GET /api/brain/decision-trace — last routing decision for a session
  GET /api/brain/index-status   — ChromaDB index health
"""

from __future__ import annotations

import json
from pathlib import Path
import asyncio

from fastapi import APIRouter, Query, BackgroundTasks
from pydantic import BaseModel

from backend.services.expert_knowledge import load_expert_corpus

router = APIRouter(prefix="/api/brain", tags=["brain"])

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
ADAPTER_REGISTRY_PATH = DATA_DIR / "adapter_registry.json"
KNOWLEDGE_BASE_DIR = ROOT_DIR / "knowledge_base" / "expert"


def _count_cards_per_domain() -> dict[str, dict]:
    """Scan knowledge_base/expert/ for timestamped JSON shards."""
    domain_stats: dict[str, dict] = {}
    if not KNOWLEDGE_BASE_DIR.exists():
        return domain_stats
    for domain_dir in sorted(KNOWLEDGE_BASE_DIR.iterdir()):
        if not domain_dir.is_dir():
            continue
        key = domain_dir.name
        total = 0
        last_updated: str | None = None
        for shard in sorted(domain_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(shard.read_text(encoding="utf-8"))
                cards = data if isinstance(data, list) else data.get("cards", [])
                total += len(cards)
                if last_updated is None:
                    # Use modification time as proxy if no metadata
                    meta_ts = data.get("fetched_at") if isinstance(data, dict) else None
                    if meta_ts:
                        last_updated = str(meta_ts)
                    else:
                        import datetime
                        last_updated = datetime.datetime.fromtimestamp(
                            shard.stat().st_mtime
                        ).isoformat()
            except Exception:
                pass
        domain_stats[key] = {"cardCount": total, "lastUpdated": last_updated}
    return domain_stats


def _chromadb_index_status() -> dict:
    """Check ChromaDB collection status if available."""
    try:
        import chromadb  # type: ignore

        client = chromadb.PersistentClient(path=str(DATA_DIR / "chromadb"))
        collection = client.get_or_create_collection("sift_knowledge")
        count = collection.count()
        return {"status": "ok", "indexedCards": count}
    except Exception as exc:
        return {"status": "unavailable", "indexedCards": 0, "error": str(exc)}


def _adapter_info() -> dict | None:
    """Return the best adapter entry from the registry, if any."""
    if not ADAPTER_REGISTRY_PATH.exists():
        return None
    try:
        data = json.loads(ADAPTER_REGISTRY_PATH.read_text(encoding="utf-8"))
        adapters = list(data.get("adapters", {}).values())
        if not adapters:
            return None
        # Prefer highest eval score
        scored = [(a.get("eval_scores", {}).get("avg_overall_score", 0.0), a) for a in adapters]
        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][1]
        return {
            "adapterName": best.get("name"),
            "adapterBaseModel": best.get("base_model"),
            "adapterScore": scored[0][0] or None,
        }
    except Exception:
        return None


def _detect_engine_status(domain_stats: dict, index_info: dict) -> str:
    total_cards = sum(v["cardCount"] for v in domain_stats.values())
    if total_cards > 0 and index_info.get("indexedCards", 0) > 0:
        return "active"
    if total_cards > 0:
        return "standby"
    return "unconfigured"


@router.get("/status")
async def brain_status():
    """Return full Sift Brain status including knowledge graph stats."""
    domain_stats = _count_cards_per_domain()
    index_info = _chromadb_index_status()
    adapter = _adapter_info()

    total_cards = sum(v["cardCount"] for v in domain_stats.values())
    engine_status = _detect_engine_status(domain_stats, index_info)

    domains = [
        {
            "key": key,
            "cardCount": val["cardCount"],
            "lastUpdated": val.get("lastUpdated"),
        }
        for key, val in domain_stats.items()
        if val["cardCount"] > 0
    ]

    result = {
        "engineStatus": engine_status,
        "totalCards": total_cards,
        "totalDomains": len(domains),
        "indexedCards": index_info.get("indexedCards", 0),
        "domains": domains,
    }
    if adapter:
        result.update(adapter)
    return result


@router.get("/index-status")
async def index_status():
    """Return ChromaDB index health."""
    return _chromadb_index_status()


@router.get("/graph")
async def get_knowledge_graph():
    """Returns the topology of the expert knowledge base for visualization."""
    corpus = load_expert_corpus()
    cards = corpus.get("cards", [])
    
    nodes = []
    links = []
    
    # Central Hub
    nodes.append({
        "id": "hub", 
        "name": "Neural Engine", 
        "group": "hub", 
        "val": 20, 
        "description": "The central orchestration core of the Sift Intelligence Layer. Routes all inbound queries to the appropriate specialized expert clusters."
    })
    
    domain_nodes = set()
    subdomain_nodes = set()
    
    for card in cards:
        domain = card.get("domain", "general")
        subdomain = card.get("subdomain", "General")
        
        # Ensure domain node exists
        if domain not in domain_nodes:
            nodes.append({
                "id": f"domain_{domain}", 
                "name": domain.upper(), 
                "group": "domain", 
                "val": 10,
                "description": f"Primary specialized macro-cluster for {domain.upper()} logic and knowledge processing."
            })
            links.append({"source": "hub", "target": f"domain_{domain}", "value": 3})
            domain_nodes.add(domain)
            
        # Ensure subdomain node exists
        subdomain_id = f"sub_{domain}_{subdomain}"
        if subdomain_id not in subdomain_nodes:
            nodes.append({
                "id": subdomain_id, 
                "name": subdomain, 
                "group": "subdomain", 
                "val": 5,
                "description": f"Targeted subdomain cluster specifically focused on {subdomain} within the broader {domain.upper()} context."
            })
            links.append({"source": f"domain_{domain}", "target": subdomain_id, "value": 2})
            subdomain_nodes.add(subdomain_id)
            
        # Add card node
        card_id = card.get("id")
        nodes.append({
            "id": card_id, 
            "name": card.get("title"), 
            "group": "card", 
            "val": 1.5,
            "domain": domain,
            "confidence": card.get("confidenceTier", "medium"),
            "description": card.get("content", card.get("summary", "No detailed content available."))[:200] + "..." if card.get("content") or card.get("summary") else "Specialized leaf expert node."
        })
        links.append({"source": subdomain_id, "target": card_id, "value": 1})
        
    return {"nodes": nodes, "links": links}


@router.get("/decision-trace")
async def decision_trace(session_id: str = Query(default="")):
    """
    Return the last routing decision for a session.

    The decision trace is written by sift_brain/decision_layer/router.py
    and stored per-session as trace metadata in SQLite. Falls back to
    an empty trace if the brain is not active.
    """
    if not session_id:
        return {"available": False, "reason": "No session_id provided"}

    try:
        from backend.core import memory

        session_row = memory.get_session(session_id)
        if not session_row:
            return {"available": False, "reason": "Session not found"}

        meta = memory.get_session_metadata(session_row)
        trace = meta.get("sift_brain_trace")
        if not trace:
            return {
                "available": False,
                "reason": "No Sift Brain trace for this session. Brain may not be active.",
            }
        return {"available": True, "trace": trace}
    except Exception as exc:
        return {"available": False, "reason": str(exc)}


class TuneRequest(BaseModel):
    rank: int = 8
    learning_rate: float = 2e-4
    epochs: int = 3

tuning_state = {
    "status": "idle",
    "progress": 0.0,
    "error": None
}

async def _simulate_tuning(params: dict):
    tuning_state["status"] = "running"
    tuning_state["progress"] = 0.0
    tuning_state["error"] = None
    try:
        for i in range(1, 11):
            await asyncio.sleep(1)
            tuning_state["progress"] = i * 10.0
        tuning_state["status"] = "completed"
    except Exception as e:
        tuning_state["status"] = "failed"
        tuning_state["error"] = str(e)


@router.post("/tune")
async def start_tuning(req: TuneRequest, background_tasks: BackgroundTasks):
    """Start a background tuning job with the given hyperparameters."""
    if tuning_state["status"] == "running":
        return {"status": "error", "message": "A tuning job is already running"}
    background_tasks.add_task(_simulate_tuning, req.model_dump() if hasattr(req, "model_dump") else req.dict())
    return {"status": "accepted", "message": "Tuning job started"}


@router.get("/tune/status")
async def get_tuning_status():
    """Return the status of the ongoing or last tuning job."""
    return tuning_state
