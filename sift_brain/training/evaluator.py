"""Evaluation harness for Sift Brain fine-tuned models.

Runs the trained adapter on held-out session turns and KB Q&A pairs.
Scores responses on: coherence, domain accuracy, actionability.
Generates a comparison report vs. the base model.

Usage:
    python3 -m sift_brain.training.evaluator --adapter latest
    # or:
    from sift_brain.training.evaluator import run_eval
    results = run_eval(adapter_path="data/model_adapters/sift-brain-latest")
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"
ADAPTERS_DIR = DATA_DIR / "model_adapters"
EVAL_DIR = DATA_DIR / "eval_reports"
TRAINING_DIR = DATA_DIR / "training"


# ---------------------------------------------------------------------------
# Scoring rubrics
# ---------------------------------------------------------------------------

def _score_coherence(response: str) -> float:
    """0–1: is the response well-structured and readable?"""
    if not response or len(response) < 30:
        return 0.0
    # Penalise repetition, reward structure markers
    words = response.lower().split()
    unique_ratio = len(set(words)) / max(len(words), 1)
    has_structure = bool(re.search(r"(\n[-•]\s|\d+\.\s|[A-Z][^.!?]+:)", response))
    base = min(unique_ratio * 1.2, 1.0)
    return min(base + (0.1 if has_structure else 0.0), 1.0)


def _score_domain_accuracy(response: str, expected_terms: list[str]) -> float:
    """0–1: does the response use the expected domain terminology?"""
    if not expected_terms:
        return 0.5
    response_lower = response.lower()
    hits = sum(1 for term in expected_terms if term.lower() in response_lower)
    return hits / len(expected_terms)


def _score_actionability(response: str) -> float:
    """0–1: does the response contain actionable advice or next steps?"""
    action_patterns = re.compile(
        r"\b(should|recommend|consider|next step|action|improve|focus on|"
        r"increase|decrease|measure|track|test|validate|prioritise|target)\b",
        re.I,
    )
    matches = len(action_patterns.findall(response))
    return min(matches / 3.0, 1.0)


def _score_response(response: str, expected_terms: list[str] | None = None) -> dict[str, float]:
    coherence = _score_coherence(response)
    domain_acc = _score_domain_accuracy(response, expected_terms or [])
    actionability = _score_actionability(response)
    overall = (coherence * 0.35 + domain_acc * 0.40 + actionability * 0.25)
    return {
        "coherence": round(coherence, 3),
        "domain_accuracy": round(domain_acc, 3),
        "actionability": round(actionability, 3),
        "overall": round(overall, 3),
    }


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def _load_adapter(adapter_path: Path) -> tuple[Any, Any]:
    """Load fine-tuned adapter + tokenizer."""
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    meta_path = adapter_path / "run_metadata.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        base_model_id = meta.get("base_model", "Qwen/Qwen3-8B")
    else:
        base_model_id = "Qwen/Qwen3-8B"

    print(f"[evaluator] Loading base: {base_model_id}")
    tokenizer = AutoTokenizer.from_pretrained(str(adapter_path), trust_remote_code=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        device_map="auto",
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(base_model, str(adapter_path))
    model.eval()
    return model, tokenizer


def _generate(model: Any, tokenizer: Any, messages: list[dict], max_new_tokens: int = 256) -> str:
    import torch
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=1.0,
            pad_token_id=tokenizer.eos_token_id,
        )
    generated = outputs[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(generated, skip_special_tokens=True)


# ---------------------------------------------------------------------------
# Eval dataset
# ---------------------------------------------------------------------------

def _load_eval_examples(n: int = 50) -> list[dict[str, Any]]:
    eval_file = TRAINING_DIR / "sift_dataset.eval.jsonl"
    if not eval_file.exists():
        return []
    examples: list[dict] = []
    with eval_file.open(encoding="utf-8") as f:
        for line in f:
            try:
                examples.append(json.loads(line))
            except Exception:
                pass
    return examples[:n]


# ---------------------------------------------------------------------------
# Main eval
# ---------------------------------------------------------------------------

def run_eval(
    adapter_path: str | Path | None = None,
    *,
    n_examples: int = 30,
    max_new_tokens: int = 256,
) -> dict[str, Any]:
    """Run evaluation on held-out examples.

    Returns a summary report dict.
    """
    if adapter_path is None:
        # Find latest adapter
        candidates = sorted(ADAPTERS_DIR.glob("*/run_metadata.json"))
        if not candidates:
            print("[evaluator] No adapters found in", ADAPTERS_DIR)
            return {"error": "no_adapter_found"}
        adapter_path = candidates[-1].parent
    adapter_path = Path(adapter_path)

    print(f"[evaluator] Evaluating adapter: {adapter_path}")
    model, tokenizer = _load_adapter(adapter_path)

    examples = _load_eval_examples(n=n_examples)
    if not examples:
        print("[evaluator] No eval examples found. Run dataset_builder first.")
        return {"error": "no_eval_data"}

    results: list[dict[str, Any]] = []
    total_score = 0.0

    for i, example in enumerate(examples):
        messages = example.get("messages", [])
        # Find the last user turn and expected assistant response
        user_msgs = [m for m in messages if m["role"] in ("system", "user")]
        expected = next((m["content"] for m in reversed(messages) if m["role"] == "assistant"), "")

        if not user_msgs or not expected:
            continue

        try:
            generated = _generate(model, tokenizer, user_msgs, max_new_tokens=max_new_tokens)
            scores = _score_response(generated, expected_terms=expected.split()[:10])
        except Exception as exc:
            generated = ""
            scores = {"coherence": 0.0, "domain_accuracy": 0.0, "actionability": 0.0, "overall": 0.0}
            print(f"[evaluator] Example {i} error: {exc}")

        results.append({
            "example_id": i,
            "generated": generated[:400],
            "expected": expected[:200],
            "scores": scores,
        })
        total_score += scores["overall"]
        print(f"[evaluator] [{i+1}/{len(examples)}] overall={scores['overall']:.3f}")

    avg_score = total_score / max(len(results), 1)
    report = {
        "adapter": str(adapter_path),
        "n_evaluated": len(results),
        "avg_overall_score": round(avg_score, 3),
        "avg_coherence": round(sum(r["scores"]["coherence"] for r in results) / max(len(results), 1), 3),
        "avg_domain_accuracy": round(sum(r["scores"]["domain_accuracy"] for r in results) / max(len(results), 1), 3),
        "avg_actionability": round(sum(r["scores"]["actionability"] for r in results) / max(len(results), 1), 3),
        "results": results,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = EVAL_DIR / f"eval_report_{ts}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[evaluator] Avg score: {avg_score:.3f} → {report_path}")

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate a Sift Brain fine-tuned adapter")
    parser.add_argument("--adapter", default=None, help="Path to adapter directory (default: latest)")
    parser.add_argument("--n", type=int, default=30, help="Number of eval examples")
    parser.add_argument("--max-tokens", type=int, default=256, help="Max tokens to generate")
    args = parser.parse_args()

    run_eval(adapter_path=args.adapter, n_examples=args.n, max_new_tokens=args.max_tokens)
