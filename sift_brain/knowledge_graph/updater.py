"""Async knowledge graph updater for Sift Brain.

Fetches structured knowledge cards from curated seed sources per domain,
deduplicates against existing knowledge base, and writes new shards to
knowledge_base/expert/ as timestamped JSON files.

Usage:
    python3 scripts/update_knowledge_graph.py [--domain all|saas|fintech|...]
    # or via the KB API:
    from sift_brain.knowledge_graph.updater import run_domain_update
    await run_domain_update("saas")
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    _BS4_AVAILABLE = True
except ImportError:
    _BS4_AVAILABLE = False

from sift_brain.knowledge_graph.domains import DomainConfig, DOMAINS, enabled_domains

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[3]
KB_DIR = ROOT_DIR / "knowledge_base" / "expert"
DATA_DIR = ROOT_DIR / "data"
FETCH_TIMEOUT = 15.0  # seconds
MAX_BODY_CHARS = 3000  # max chars extracted per page
MIN_BODY_CHARS = 120   # skip pages that are too thin
MAX_CONCURRENT = 4     # concurrent fetch limit


# ---------------------------------------------------------------------------
# Knowledge card structure
# ---------------------------------------------------------------------------

def _card_id(url: str, title: str) -> str:
    """Deterministic content hash used for deduplication."""
    raw = f"{url}::{title.strip().lower()}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _make_card(
    *,
    domain: str,
    geography: str,
    title: str,
    body: str,
    url: str,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": _card_id(url, title),
        "domain": domain,
        "geography": geography,
        "title": title.strip(),
        "body": body.strip(),
        "url": url,
        "tags": tags or [],
        "source": "web_scrape",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def _extract_text(html: str, url: str) -> tuple[str, str]:
    """Return (title, body) from raw HTML.  Falls back to regex if bs4 absent."""
    if not _BS4_AVAILABLE:
        # Regex fallback: strip tags
        title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        title = title_m.group(1).strip() if title_m else url
        body = re.sub(r"<[^>]+>", " ", html)
        body = re.sub(r"\s+", " ", body).strip()[:MAX_BODY_CHARS]
        return title, body

    soup = BeautifulSoup(html, "html.parser")

    # Title
    title_tag = soup.find("title")
    og_title = soup.find("meta", property="og:title")
    h1_tag = soup.find("h1")
    title = (
        (og_title.get("content") if og_title else None)
        or (h1_tag.get_text(" ", strip=True) if h1_tag else None)
        or (title_tag.get_text(" ", strip=True) if title_tag else None)
        or url
    )

    # Body — prefer article / main content
    for tag in ["article", "main", "section"]:
        elem = soup.find(tag)
        if elem:
            body = elem.get_text(" ", strip=True)
            if len(body) > MIN_BODY_CHARS:
                return title, body[:MAX_BODY_CHARS]

    # Fallback: all paragraphs
    paras = soup.find_all("p")
    body = " ".join(p.get_text(" ", strip=True) for p in paras)
    return title, body[:MAX_BODY_CHARS]


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

async def _fetch_url(client: "httpx.AsyncClient", url: str) -> str | None:
    try:
        resp = await client.get(url, timeout=FETCH_TIMEOUT, follow_redirects=True)
        if resp.status_code == 200:
            return resp.text
    except Exception as exc:
        print(f"  [updater] fetch error {url}: {exc}")
    return None


# ---------------------------------------------------------------------------
# Existing card IDs (deduplication)
# ---------------------------------------------------------------------------

def _load_existing_ids() -> set[str]:
    ids: set[str] = set()
    if not KB_DIR.exists():
        return ids
    for f in KB_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            entries = data if isinstance(data, list) else data.get("entries", [])
            for entry in entries:
                if isinstance(entry, dict) and entry.get("id"):
                    ids.add(entry["id"])
        except Exception:
            pass
    return ids


# ---------------------------------------------------------------------------
# Core update logic
# ---------------------------------------------------------------------------

async def _update_domain(domain: DomainConfig, existing_ids: set[str], dry_run: bool = False) -> list[dict[str, Any]]:
    if not _HTTPX_AVAILABLE:
        print(f"  [updater] httpx not installed — skipping fetch for {domain.key}")
        return []

    new_cards: list[dict[str, Any]] = []
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def fetch_and_parse(client: "httpx.AsyncClient", url: str) -> None:
        async with semaphore:
            html = await _fetch_url(client, url)
            if not html:
                return
            title, body = _extract_text(html, url)
            if len(body) < MIN_BODY_CHARS:
                return
            card = _make_card(
                domain=domain.key,
                geography=domain.geography,
                title=title,
                body=body,
                url=url,
                tags=list(domain.taxonomy_keys),
            )
            if card["id"] not in existing_ids:
                new_cards.append(card)
                existing_ids.add(card["id"])
                print(f"  [updater] +card: {card['title'][:60]}")
            else:
                print(f"  [updater]  skip: {title[:60]} (exists)")

    async with httpx.AsyncClient(headers={"User-Agent": "SiftBot/1.0 (knowledge graph updater)"}) as client:
        await asyncio.gather(*[fetch_and_parse(client, url) for url in domain.seed_urls])

    return new_cards


def _write_shard(domain_key: str, cards: list[dict[str, Any]]) -> Path:
    KB_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    shard_path = KB_DIR / f"kb_brain_{domain_key}_{timestamp}.json"
    shard_path.write_text(json.dumps(cards, indent=2, ensure_ascii=False), encoding="utf-8")
    return shard_path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def run_domain_update(
    domain_key: str = "all",
    *,
    dry_run: bool = False,
    verbose: bool = True,
) -> dict[str, int]:
    """Run the updater for one domain key or all enabled domains.

    Returns a dict mapping domain_key -> number of new cards added.
    """
    existing_ids = _load_existing_ids()

    if domain_key == "all":
        targets = enabled_domains()
    elif domain_key in DOMAINS:
        cfg = DOMAINS[domain_key]
        if not cfg.enabled:
            print(f"[updater] domain '{domain_key}' is disabled — skipping.")
            return {domain_key: 0}
        targets = [cfg]
    else:
        raise ValueError(f"Unknown domain key '{domain_key}'. Valid: {', '.join(DOMAINS)}")

    results: dict[str, int] = {}
    for domain in targets:
        if verbose:
            print(f"\n[updater] Updating domain: {domain.label} ({domain.geography})")
        t0 = time.monotonic()
        new_cards = await _update_domain(domain, existing_ids, dry_run=dry_run)
        elapsed = time.monotonic() - t0

        if new_cards and not dry_run:
            shard_path = _write_shard(domain.key, new_cards)
            if verbose:
                print(f"[updater] Wrote {len(new_cards)} cards → {shard_path.name} ({elapsed:.1f}s)")
        else:
            if verbose:
                print(f"[updater] {len(new_cards)} new cards found (dry-run={dry_run}) ({elapsed:.1f}s)")

        results[domain.key] = len(new_cards)

    return results


def run_update_sync(domain_key: str = "all", *, dry_run: bool = False) -> dict[str, int]:
    """Synchronous wrapper around run_domain_update."""
    return asyncio.run(run_domain_update(domain_key, dry_run=dry_run))
