"""Dataset builder for Sift Brain fine-tuning.

Exports training data from:
  - Session turns (SQLite) — real founder <> mentor conversations
  - KB cards — Q&A pairs generated from knowledge cards
  - Evaluator reports — structured (question, rationale, score) triplets

Output format: OpenAI messages (ShareGPT-compatible) JSONL.

Usage:
    python3 -m sift_brain.training.dataset_builder --output data/training/sift_dataset.jsonl
    # or:
    from sift_brain.training.dataset_builder import build_dataset
    build_dataset(output_path="data/training/sift_dataset.jsonl")
"""

from __future__ import annotations

import json
import os
import random
import sqlite3
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"
KB_DIR = ROOT_DIR / "knowledge_base" / "expert"
DB_PATH = DATA_DIR / os.environ.get("SIFT_DATABASE_NAME", "sessions.db")
TRAINING_DIR = DATA_DIR / "training"

# Minimum turn quality thresholds
MIN_USER_CHARS = 20
MIN_ASSISTANT_CHARS = 80
MIN_TURNS_PER_SESSION = 3


# ---------------------------------------------------------------------------
# System prompt template for training
# ---------------------------------------------------------------------------

SIFT_SYSTEM_PROMPT = """You are Sift, an AI workbench for startup ideation, pitch deck review, and investor-style evaluation.

You help founders, operators, students, and analysts think clearly about startups:
- In Ideate mode: ask targeted questions, track pitch coverage, shape early ideas into clearer narratives.
- In Evaluate mode: score startup ideas and pitch decks with evidence-driven assessment, structured verdicts, and next steps.
- In Expert mode: answer startup, market, and venture-style questions using domain knowledge and retrieved context.

Rules:
- Never fabricate metrics, funding data, or investor names.
- Ground your answers in customer evidence, market data, and financial fundamentals.
- Adapt tone to the user's role (founder, student, investor, operator).
- Be concise and actionable. Avoid generic advice.
"""


# ---------------------------------------------------------------------------
# Session turn export
# ---------------------------------------------------------------------------

def _load_sessions_from_sqlite() -> list[dict[str, Any]]:
    if not DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, sector, founder_type, session_type FROM sessions")
        sessions = [dict(r) for r in cur.fetchall()]

        for session in sessions:
            cur.execute(
                "SELECT role, content FROM turns WHERE session_id=? ORDER BY id ASC",
                (session["id"],),
            )
            session["turns"] = [dict(r) for r in cur.fetchall()]
        conn.close()
        return sessions
    except Exception as exc:
        print(f"[dataset_builder] SQLite error: {exc}")
        return []


def _session_to_training_examples(session: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a session into multi-turn training examples (sliding window)."""
    turns = session.get("turns", [])
    if len(turns) < MIN_TURNS_PER_SESSION * 2:
        return []

    examples: list[dict[str, Any]] = []
    messages: list[dict[str, str]] = [{"role": "system", "content": SIFT_SYSTEM_PROMPT}]

    i = 0
    while i < len(turns) - 1:
        user_turn = turns[i]
        assistant_turn = turns[i + 1]

        if user_turn.get("role") != "user" or assistant_turn.get("role") != "assistant":
            i += 1
            continue

        u_content = (user_turn.get("content") or "").strip()
        a_content = (assistant_turn.get("content") or "").strip()

        if len(u_content) < MIN_USER_CHARS or len(a_content) < MIN_ASSISTANT_CHARS:
            i += 2
            continue

        messages = messages + [
            {"role": "user", "content": u_content},
            {"role": "assistant", "content": a_content},
        ]
        # Create a training example ending at this assistant turn
        examples.append({"messages": list(messages)})
        i += 2

    return examples


# ---------------------------------------------------------------------------
# KB card Q&A generation
# ---------------------------------------------------------------------------

def _card_to_qa(card: dict[str, Any]) -> dict[str, Any] | None:
    title = card.get("title", "") or card.get("concept", "") or card.get("term", "")
    body = card.get("body", "") or card.get("description", "") or card.get("text", "")
    if not title or not body or len(body) < 60:
        return None

    question = f"Explain {title} in the context of startup evaluation and venture capital."
    answer = body.strip()

    return {
        "messages": [
            {"role": "system", "content": SIFT_SYSTEM_PROMPT},
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]
    }


def _load_kb_qa_examples() -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    if not KB_DIR.exists():
        return examples
    for path in KB_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            entries = data if isinstance(data, list) else data.get("entries", [])
            for entry in entries:
                if isinstance(entry, dict):
                    ex = _card_to_qa(entry)
                    if ex:
                        examples.append(ex)
        except Exception:
            pass
    return examples


# ---------------------------------------------------------------------------
# Dataset assembly
# ---------------------------------------------------------------------------

def build_dataset(
    output_path: str | Path | None = None,
    *,
    include_sessions: bool = True,
    include_kb: bool = True,
    shuffle: bool = True,
    max_examples: int = 0,
    split: float = 0.9,
) -> dict[str, Any]:
    """Build and write the training dataset.

    Returns:
        {
          "total": int,
          "train": int,
          "eval": int,
          "train_path": str,
          "eval_path": str,
        }
    """
    TRAINING_DIR.mkdir(parents=True, exist_ok=True)
    output_path = Path(output_path) if output_path else TRAINING_DIR / "sift_dataset.jsonl"
    train_path = output_path.with_suffix(".train.jsonl")
    eval_path = output_path.with_suffix(".eval.jsonl")

    examples: list[dict[str, Any]] = []

    if include_sessions:
        sessions = _load_sessions_from_sqlite()
        print(f"[dataset_builder] Loaded {len(sessions)} sessions from SQLite")
        for session in sessions:
            examples.extend(_session_to_training_examples(session))

    if include_kb:
        kb_examples = _load_kb_qa_examples()
        print(f"[dataset_builder] Generated {len(kb_examples)} KB Q&A examples")
        examples.extend(kb_examples)

    if shuffle:
        random.shuffle(examples)

    if max_examples and max_examples < len(examples):
        examples = examples[:max_examples]

    # Train/eval split
    split_idx = int(len(examples) * split)
    train_examples = examples[:split_idx]
    eval_examples = examples[split_idx:]

    def _write_jsonl(path: Path, data: list[dict]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for ex in data:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    _write_jsonl(train_path, train_examples)
    _write_jsonl(eval_path, eval_examples)

    result = {
        "total": len(examples),
        "train": len(train_examples),
        "eval": len(eval_examples),
        "train_path": str(train_path),
        "eval_path": str(eval_path),
    }
    print(f"[dataset_builder] Dataset: {result['total']} examples → {train_path.name} + {eval_path.name}")
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build Sift Brain training dataset")
    parser.add_argument("--output", default=str(TRAINING_DIR / "sift_dataset.jsonl"))
    parser.add_argument("--no-sessions", action="store_true")
    parser.add_argument("--no-kb", action="store_true")
    parser.add_argument("--max-examples", type=int, default=0)
    parser.add_argument("--split", type=float, default=0.9)
    args = parser.parse_args()

    build_dataset(
        output_path=args.output,
        include_sessions=not args.no_sessions,
        include_kb=not args.no_kb,
        max_examples=args.max_examples,
        split=args.split,
    )
