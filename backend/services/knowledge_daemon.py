"""Background daemon for continuous knowledge graph updates."""

import asyncio
import json
import logging
from typing import Any

from sift_brain.knowledge_graph.embedder import rebuild_index
from sift_brain.knowledge_graph.graph import KnowledgeGraph
from sift_brain.knowledge_graph.updater import KB_DIR, run_domain_update

logger = logging.getLogger(__name__)

UPDATE_INTERVAL_SECONDS = 60  # 60 seconds for demo purposes


async def knowledge_daemon_task() -> None:
    """Continuously runs the knowledge graph update process."""
    logger.info("Knowledge daemon started, interval=%s seconds", UPDATE_INTERVAL_SECONDS)
    while True:
        try:
            logger.info("Running domain update...")
            results = await run_domain_update("all", verbose=False)
            total_new = sum(results.values())
            logger.info("Domain update complete. New cards found: %s", total_new)

            if total_new > 0:
                logger.info("Triggering ChromaDB index rebuild...")
                await asyncio.to_thread(rebuild_index, verbose=False)
                
                logger.info("Rebuilding entity-relationship graph...")
                await asyncio.to_thread(_rebuild_graph)
                logger.info("Entity-relationship graph rebuilt.")
        except asyncio.CancelledError:
            logger.info("Knowledge daemon task cancelled.")
            break
        except Exception as e:
            logger.error("Error in knowledge daemon: %s", e)

        await asyncio.sleep(UPDATE_INTERVAL_SECONDS)


def _rebuild_graph() -> None:
    """Rebuilds the entire entity-relationship graph from all KB cards."""
    all_cards: list[dict[str, Any]] = []
    if KB_DIR.exists():
        for f in KB_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                entries = data if isinstance(data, list) else data.get("entries", [])
                all_cards.extend([e for e in entries if isinstance(e, dict)])
            except Exception as e:
                logger.warning("Failed to read %s: %s", f.name, e)
    
    kg = KnowledgeGraph()  # Start fresh
    kg.ingest_cards(all_cards)
    kg.save()
