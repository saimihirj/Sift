#!/usr/bin/env python3
"""Update the Sift Brain knowledge graph.

Fetches new knowledge cards from curated domain sources,
deduplicates, and writes timestamped JSON shards to knowledge_base/expert/.

Optionally re-indexes the ChromaDB vector store.

Usage:
    python3 scripts/update_knowledge_graph.py
    python3 scripts/update_knowledge_graph.py --domain saas
    python3 scripts/update_knowledge_graph.py --domain all --dry-run
    python3 scripts/update_knowledge_graph.py --reindex
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update the Sift Brain knowledge graph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/update_knowledge_graph.py                  # update all domains
  python3 scripts/update_knowledge_graph.py --domain saas    # update one domain
  python3 scripts/update_knowledge_graph.py --dry-run        # simulate only
  python3 scripts/update_knowledge_graph.py --reindex        # rebuild ChromaDB index
  python3 scripts/update_knowledge_graph.py --graph          # rebuild entity graph

Available domains: all, saas, d2c, fintech, india_vc, pe_growth, macro,
  regulation_india, market_sizing, pmf_gtm, vc_terms, climatetech, healthtech
""",
    )
    parser.add_argument(
        "--domain", default="all",
        help="Domain to update (default: all enabled domains)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch and parse but do not write new files",
    )
    parser.add_argument(
        "--reindex", action="store_true",
        help="Rebuild the ChromaDB embedding index after updating",
    )
    parser.add_argument(
        "--graph", action="store_true",
        help="Rebuild the entity-relationship knowledge graph after updating",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress per-card output",
    )
    args = parser.parse_args()

    from sift_brain.knowledge_graph.updater import run_update_sync

    print(f"\n{'='*60}")
    print(f"  Sift Brain — Knowledge Graph Updater")
    print(f"  Domain: {args.domain}")
    print(f"  Dry run: {args.dry_run}")
    print(f"{'='*60}\n")

    results = run_update_sync(args.domain, dry_run=args.dry_run)
    total_new = sum(results.values())

    print(f"\n{'='*60}")
    print(f"  Update complete: {total_new} new cards across {len(results)} domain(s)")
    for domain_key, count in results.items():
        print(f"  {domain_key:25s}: {count:4d} new cards")
    print(f"{'='*60}\n")

    if args.reindex and not args.dry_run:
        print("Re-indexing ChromaDB ...")
        from sift_brain.knowledge_graph.embedder import rebuild_index
        count = rebuild_index()
        print(f"Indexed {count} cards into ChromaDB.\n")

    if args.graph and not args.dry_run:
        print("Rebuilding entity-relationship graph ...")
        from sift_brain.knowledge_graph.embedder import _load_all_cards
        from sift_brain.knowledge_graph.graph import KnowledgeGraph
        cards = _load_all_cards()
        kg = KnowledgeGraph()
        added = kg.ingest_cards(cards)
        kg.save()
        stats = kg.stats()
        print(f"Graph: {stats['entities']} entities, {stats['relations']} relations ({added} ingested).\n")


if __name__ == "__main__":
    main()
