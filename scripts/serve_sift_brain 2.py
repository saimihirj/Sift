#!/usr/bin/env python3
"""Serve the Sift Brain fine-tuned model locally.

Starts an OpenAI-compatible inference server on port 8001.
The main Sift app can point to it via:
  LOCAL_OPENAI_BASE_URL=http://127.0.0.1:8001/v1
  SIFT_MODEL_PROVIDER=sift_brain

Usage:
    python3 scripts/serve_sift_brain.py
    python3 scripts/serve_sift_brain.py --adapter latest
    python3 scripts/serve_sift_brain.py --adapter data/model_adapters/sift-brain-v1
    python3 scripts/serve_sift_brain.py --port 8001 --host 127.0.0.1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sift Brain — local inference server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Once running, the server is accessible at:
  http://127.0.0.1:8001/v1/chat/completions  (OpenAI-compatible)
  http://127.0.0.1:8001/health               (health check)
  http://127.0.0.1:8001/v1/models            (model list)

Configure Sift to use it:
  SIFT_MODEL_PROVIDER=sift_brain
  SIFT_BRAIN_BASE_URL=http://127.0.0.1:8001/v1

Or use it as a local_openai provider:
  SIFT_MODEL_PROVIDER=local_openai
  LOCAL_OPENAI_BASE_URL=http://127.0.0.1:8001/v1
""",
    )
    parser.add_argument(
        "--adapter", default=None,
        help="Adapter path or 'latest' (default: best adapter by eval score)",
    )
    parser.add_argument("--port", type=int, default=8001, help="Server port (default: 8001)")
    parser.add_argument("--host", default="127.0.0.1", help="Server host (default: 127.0.0.1)")
    parser.add_argument(
        "--list-adapters", action="store_true",
        help="List registered adapters and exit",
    )
    args = parser.parse_args()

    from sift_brain.serving.model_registry import ModelRegistry

    registry = ModelRegistry.load()

    if args.list_adapters:
        stats = registry.stats()
        print(f"\nRegistered adapters ({stats['total_adapters']}):\n")
        for a in stats["adapters"]:
            print(f"  {a['name']:30s}  base={a['base_model']:30s}  status={a['status']}")
        print()
        return

    adapter_path = None
    if args.adapter and args.adapter != "latest":
        adapter_path = args.adapter

    print(f"\n{'='*60}")
    print(f"  Sift Brain — Local Inference Server")
    print(f"  Host: {args.host}:{args.port}")
    print(f"  Adapter: {adapter_path or 'best/latest'}")
    print(f"{'='*60}\n")

    from sift_brain.serving.server import start_server
    start_server(adapter_path=adapter_path, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
