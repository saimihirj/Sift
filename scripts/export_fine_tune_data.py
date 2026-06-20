#!/usr/bin/env python3
"""
scripts/export_fine_tune_data.py
=================================
Export high-quality Sift conversation turns as JSONL for fine-tuning a
custom LLM. Each line of the output is a valid OpenAI Chat Completions
fine-tuning example (messages array format), also compatible with Axolotl,
LLaMA-Factory, and most other frameworks via the --format flag.

Usage examples
--------------
# Export everything from the default SQLite DB:
  python scripts/export_fine_tune_data.py

# Only include sessions with at least 6 turns and coverage ≥ 40%:
  python scripts/export_fine_tune_data.py --min-turns 6 --min-coverage 40

# Export only SaaS sessions from the last 90 days:
  python scripts/export_fine_tune_data.py --sector saas --days 90

# Dry run — print stats without writing a file:
  python scripts/export_fine_tune_data.py --dry-run

# Output in Alpaca instruction format instead of ChatML:
  python scripts/export_fine_tune_data.py --format alpaca

Output
------
data/exports/sift_finetune_<timestamp>.jsonl

Each ChatML line looks like:
  {
    "messages": [
      {"role": "system",    "content": "<system prompt>"},
      {"role": "user",      "content": "<founder message>"},
      {"role": "assistant", "content": "<sift response>"}
    ],
    "metadata": {           ← stripped before upload; for offline analysis
      "session_id": "...",
      "sector": "saas",
      "stage": "early-revenue",
      "coverage_avg": 52.3,
      "turn_index": 4
    }
  }

Each Alpaca line looks like:
  {
    "instruction": "<system prompt>",
    "input": "<founder message>",
    "output": "<sift response>"
  }

Quality filters (adjustable via CLI flags)
------------------------------------------
- Only assistant turns with ≥ 80 chars are included (not one-word responses).
- Sessions must have a minimum number of turns.
- Sessions must have a minimum average coverage score.
- Optionally filter by sector, stage, or date range.
- Deduplication: exact-match turns are skipped.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator


# ── Paths ────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "sessions.db"
EXPORTS_DIR = DATA_DIR / "exports"

# ── Defaults ─────────────────────────────────────────────────────────────────
DEFAULT_MIN_TURNS = 4
DEFAULT_MIN_COVERAGE = 20          # average coverage across sections, 0–100
DEFAULT_MIN_ASSISTANT_CHARS = 80   # minimum chars for an assistant turn to be included
DEFAULT_SYSTEM_PROMPT = (
    "You are Sift, an AI mentor that helps founders pressure-test and sharpen "
    "their pitch through Socratic dialogue. You ask one clear, specific question "
    "at a time. You are direct, analytical, and never offer hollow encouragement."
)


# ── DB helpers ───────────────────────────────────────────────────────────────
def _conn(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        print(f"[error] Database not found: {db_path}", file=sys.stderr)
        print(
            "        Start Sift at least once to create the database, or pass\n"
            "        --db-path /path/to/sessions.db to point at an existing one.",
            file=sys.stderr,
        )
        sys.exit(1)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con


def _list_sessions(
    con: sqlite3.Connection,
    sector: str | None,
    stage: str | None,
    days: int | None,
    min_turns: int,
) -> list[sqlite3.Row]:
    query = """
        SELECT
            s.id,
            s.sector,
            s.stage,
            s.founder_type,
            s.session_type,
            s.coverage_json,
            s.metadata_json,
            s.created_at,
            COUNT(t.id) AS turn_count
        FROM sessions s
        LEFT JOIN turns t ON t.session_id = s.id AND t.role IN ('user', 'assistant')
        WHERE 1=1
    """
    params: list[object] = []

    if sector:
        query += " AND s.sector = ?"
        params.append(sector)
    if stage:
        query += " AND s.stage = ?"
        params.append(stage)
    if days:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query += " AND s.created_at >= ?"
        params.append(cutoff)

    query += " GROUP BY s.id HAVING turn_count >= ?"
    params.append(min_turns)
    query += " ORDER BY s.created_at DESC"

    return con.execute(query, params).fetchall()


def _get_turns(con: sqlite3.Connection, session_id: str) -> list[sqlite3.Row]:
    return con.execute(
        """SELECT role, content, metadata_json
           FROM turns
           WHERE session_id = ?
           ORDER BY id""",
        (session_id,),
    ).fetchall()


def _coverage_avg(coverage_json: str | None) -> float:
    if not coverage_json:
        return 0.0
    try:
        data = json.loads(coverage_json)
        values = [v for v in data.values() if isinstance(v, (int, float))]
        return sum(values) / len(values) if values else 0.0
    except (json.JSONDecodeError, AttributeError):
        return 0.0


def _get_system_prompt(metadata_json: str | None) -> str:
    """Extract system prompt from session metadata if stored, otherwise return default."""
    if not metadata_json:
        return DEFAULT_SYSTEM_PROMPT
    try:
        meta = json.loads(metadata_json)
        # We store the system prompt in metadata when SIFT_CAPTURE_SYSTEM_PROMPT=true
        sp = meta.get("system_prompt", "").strip()
        return sp if sp else DEFAULT_SYSTEM_PROMPT
    except (json.JSONDecodeError, AttributeError):
        return DEFAULT_SYSTEM_PROMPT


# ── Yield examples ───────────────────────────────────────────────────────────
def _yield_chatml(
    session: sqlite3.Row,
    turns: list[sqlite3.Row],
    system_prompt: str,
    min_assistant_chars: int,
    min_coverage: float,
    seen: set[str],
) -> Iterator[dict]:
    """Yield one ChatML dict per (user, assistant) adjacent pair in the session."""
    coverage_avg = _coverage_avg(session["coverage_json"])
    if coverage_avg < min_coverage:
        return

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    turn_index = 0

    for turn in turns:
        role = turn["role"]
        content = (turn["content"] or "").strip()
        if not content or role not in ("user", "assistant"):
            continue

        if role == "user":
            messages.append({"role": "user", "content": content})
        elif role == "assistant":
            if len(content) < min_assistant_chars:
                # Too short — likely a clarifying rephrase or error message; skip.
                messages = messages[:-1] if messages and messages[-1]["role"] == "user" else messages
                continue

            # Deduplication: skip if the exact (user, assistant) pair was seen before.
            dedup_key = (
                (messages[-1]["content"] if messages and messages[-1]["role"] == "user" else "")
                + "|||"
                + content
            )
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            full_messages = list(messages) + [{"role": "assistant", "content": content}]
            yield {
                "messages": full_messages,
                "metadata": {
                    "session_id": session["id"],
                    "sector": session["sector"],
                    "stage": session["stage"],
                    "founder_type": session["founder_type"],
                    "session_type": session["session_type"],
                    "coverage_avg": round(coverage_avg, 1),
                    "turn_index": turn_index,
                    "created_at": session["created_at"],
                },
            }
            turn_index += 1
            # Build up a rolling context window — keep last 6 messages (3 pairs)
            # plus the system prompt for the next example.
            messages.append({"role": "assistant", "content": content})
            if len(messages) > 7:  # system + 3 pairs = 7
                messages = [messages[0]] + messages[-6:]


def _yield_alpaca(
    session: sqlite3.Row,
    turns: list[sqlite3.Row],
    system_prompt: str,
    min_assistant_chars: int,
    min_coverage: float,
    seen: set[str],
) -> Iterator[dict]:
    """Yield one Alpaca dict per (user, assistant) adjacent pair in the session."""
    coverage_avg = _coverage_avg(session["coverage_json"])
    if coverage_avg < min_coverage:
        return

    pending_user: str | None = None

    for turn in turns:
        role = turn["role"]
        content = (turn["content"] or "").strip()
        if not content or role not in ("user", "assistant"):
            continue

        if role == "user":
            pending_user = content
        elif role == "assistant" and pending_user is not None:
            if len(content) < min_assistant_chars:
                pending_user = None
                continue

            dedup_key = pending_user + "|||" + content
            if dedup_key in seen:
                pending_user = None
                continue
            seen.add(dedup_key)

            yield {
                "instruction": system_prompt,
                "input": pending_user,
                "output": content,
            }
            pending_user = None


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export Sift conversation turns as JSONL for LLM fine-tuning.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DB_PATH,
        help=f"Path to sessions.db (default: {DB_PATH})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSONL file path (default: data/exports/sift_finetune_<timestamp>.jsonl)",
    )
    parser.add_argument(
        "--format",
        choices=["chatml", "alpaca"],
        default="chatml",
        help="Output format: 'chatml' (OpenAI messages array) or 'alpaca' (instruction/input/output)",
    )
    parser.add_argument(
        "--min-turns",
        type=int,
        default=DEFAULT_MIN_TURNS,
        help=f"Minimum number of turns per session (default: {DEFAULT_MIN_TURNS})",
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=DEFAULT_MIN_COVERAGE,
        help=f"Minimum average coverage score per session, 0–100 (default: {DEFAULT_MIN_COVERAGE})",
    )
    parser.add_argument(
        "--min-chars",
        type=int,
        default=DEFAULT_MIN_ASSISTANT_CHARS,
        help=f"Minimum characters in an assistant turn (default: {DEFAULT_MIN_ASSISTANT_CHARS})",
    )
    parser.add_argument(
        "--sector",
        default=None,
        choices=["saas", "d2c", "fintech", "marketplace", "unknown"],
        help="Filter by sector (default: all sectors)",
    )
    parser.add_argument(
        "--stage",
        default=None,
        choices=["idea", "pre-revenue", "early-revenue", "growth", "unknown"],
        help="Filter by startup stage (default: all stages)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Only include sessions created in the last N days (default: all time)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print statistics without writing any output file",
    )
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Strip the 'metadata' field from ChatML output (required for some fine-tuning APIs)",
    )

    args = parser.parse_args()

    con = _conn(args.db_path)
    sessions = _list_sessions(con, args.sector, args.stage, args.days, args.min_turns)

    print(f"[sift-export] Found {len(sessions)} qualifying session(s).")

    seen: set[str] = set()
    examples: list[dict] = []

    for session in sessions:
        turns = _get_turns(con, session["id"])
        system_prompt = _get_system_prompt(session["metadata_json"])

        if args.format == "chatml":
            gen = _yield_chatml(session, turns, system_prompt, args.min_chars, args.min_coverage, seen)
        else:
            gen = _yield_alpaca(session, turns, system_prompt, args.min_chars, args.min_coverage, seen)

        for example in gen:
            if args.no_metadata and "metadata" in example:
                del example["metadata"]
            examples.append(example)

    print(f"[sift-export] Generated {len(examples)} training example(s) after quality filtering.")

    if not examples:
        print("[sift-export] No examples to write. Check your filters and run more sessions first.")
        return

    if args.dry_run:
        print("[sift-export] --dry-run enabled. No file written.")
        # Print a sample of the first example for review.
        print("\nSample (first example):\n")
        print(json.dumps(examples[0], indent=2, ensure_ascii=False))
        return

    # Determine output path
    if args.output:
        out_path = args.output
    else:
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = EXPORTS_DIR / f"sift_finetune_{timestamp}.jsonl"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for example in examples:
            fh.write(json.dumps(example, ensure_ascii=False) + "\n")

    print(f"[sift-export] Wrote {len(examples)} example(s) → {out_path}")
    print(f"[sift-export] File size: {out_path.stat().st_size / 1024:.1f} KB")
    print()
    print("Next steps:")
    print("  Upload to OpenAI:  openai api fine_tuning.jobs.create -t {path} -m gpt-4o-mini")
    print("  Use with Axolotl:  axolotl train configs/sift_lora.yml --dataset {path}")
    print("  Use with Unsloth:  Pass the JSONL path to FastLanguageModel.get_dataset()")


if __name__ == "__main__":
    main()
