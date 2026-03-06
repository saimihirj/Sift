"""Build the dedicated VC firm knowledge cluster from spreadsheet inputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.vc_firm_knowledge import refresh_vc_firm_cluster


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the VC firm knowledge cluster.")
    parser.add_argument("--max-firms", type=int, default=250, help="Maximum number of firms to crawl. Use 0 for all.")
    parser.add_argument("--max-pages", type=int, default=4, help="Maximum number of pages per firm website.")
    parser.add_argument("--max-chars-per-page", type=int, default=2600, help="Maximum visible text chars per crawled page.")
    parser.add_argument("--firm", default="", help="Only crawl firms whose name contains this text.")
    parser.add_argument("--include-zero-portfolio", action="store_true", help="Include firms with no mapped portfolio companies.")
    parser.add_argument("--force-refresh", action="store_true", help="Ignore cached website pages and refetch.")
    parser.add_argument("--pause-seconds", type=float, default=0.0, help="Pause between internal page fetches.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = refresh_vc_firm_cluster(
        max_firms=args.max_firms,
        max_pages=args.max_pages,
        max_chars_per_page=args.max_chars_per_page,
        force_refresh=args.force_refresh,
        firm_filter=args.firm,
        include_zero_portfolio=args.include_zero_portfolio,
        pause_seconds=max(0.0, args.pause_seconds),
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
