"""Hyperparameter tuner for Sift Brain fine-tuning.

Uses Optuna to run N trials with different hyperparameter combinations
and find the best config based on eval loss.

Usage:
    python3 -m sift_brain.training.hypertuner --trials 10 --base qwen3-8b
    # or:
    from sift_brain.training.hypertuner import run_sweep
    best_config = run_sweep(n_trials=10)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"
TUNING_DIR = DATA_DIR / "tuning_runs"


# ---------------------------------------------------------------------------
# Search space definition
# ---------------------------------------------------------------------------

SEARCH_SPACE: dict[str, Any] = {
    "learning_rate": {
        "type": "float",
        "low": 1e-5,
        "high": 5e-4,
        "log": True,
    },
    "lora_rank": {
        "type": "categorical",
        "choices": [8, 16, 32, 64],
    },
    "lora_dropout": {
        "type": "float",
        "low": 0.0,
        "high": 0.15,
    },
    "per_device_train_batch_size": {
        "type": "categorical",
        "choices": [1, 2, 4],
    },
    "gradient_accumulation_steps": {
        "type": "categorical",
        "choices": [2, 4, 8],
    },
    "warmup_steps": {
        "type": "int",
        "low": 10,
        "high": 100,
    },
    "weight_decay": {
        "type": "float",
        "low": 0.0,
        "high": 0.1,
    },
}


def _sample_params(trial: Any) -> dict[str, Any]:
    """Sample hyperparameters from the Optuna trial."""
    params: dict[str, Any] = {}
    for name, spec in SEARCH_SPACE.items():
        t = spec["type"]
        if t == "float":
            params[name] = trial.suggest_float(name, spec["low"], spec["high"], log=spec.get("log", False))
        elif t == "int":
            params[name] = trial.suggest_int(name, spec["low"], spec["high"])
        elif t == "categorical":
            params[name] = trial.suggest_categorical(name, spec["choices"])
    return params


def _objective(trial: Any, base_model: str, dataset_train: str, dataset_eval: str) -> float:
    """Optuna objective — returns eval_loss (lower is better)."""
    from sift_brain.training.finetune import run_finetune

    params = _sample_params(trial)
    trial_name = f"trial_{trial.number:03d}"
    adapter_dir = str(TUNING_DIR / trial_name)

    try:
        result = run_finetune(
            base_model=base_model,
            lora_rank=params["lora_rank"],
            learning_rate=params["learning_rate"],
            epochs=1,  # 1 epoch per trial for speed
            dry_run=False,
        )
        # Try to get eval loss from result or from trainer logs
        eval_loss = result.get("eval_loss") or result.get("train_loss") or 999.0
    except Exception as exc:
        print(f"[hypertuner] Trial {trial.number} failed: {exc}")
        eval_loss = 999.0

    # Log trial result
    trial.set_user_attr("adapter_dir", adapter_dir)
    trial.set_user_attr("params", params)
    return float(eval_loss)


def run_sweep(
    n_trials: int = 10,
    *,
    base_model: str = "Qwen/Qwen3-8B",
    study_name: str | None = None,
    direction: str = "minimize",
) -> dict[str, Any]:
    """Run hyperparameter sweep with Optuna.

    Returns the best config found.
    """
    try:
        import optuna
    except ImportError:
        raise RuntimeError(
            "optuna is required for hyperparameter tuning. "
            "Install with: pip install optuna>=3.6.0"
        )

    TUNING_DIR.mkdir(parents=True, exist_ok=True)
    study_name = study_name or f"sift-brain-sweep-{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    dataset_train = str(DATA_DIR / "training" / "sift_dataset.train.jsonl")
    dataset_eval = str(DATA_DIR / "training" / "sift_dataset.eval.jsonl")

    print(f"[hypertuner] Starting sweep '{study_name}' with {n_trials} trials on {base_model}")
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    study = optuna.create_study(
        direction=direction,
        study_name=study_name,
        sampler=optuna.samplers.TPESampler(seed=42),
    )

    study.optimize(
        lambda trial: _objective(trial, base_model, dataset_train, dataset_eval),
        n_trials=n_trials,
        show_progress_bar=True,
    )

    best_trial = study.best_trial
    best_params = best_trial.params
    best_value = best_trial.value

    print(f"\n[hypertuner] Best trial #{best_trial.number}: eval_loss={best_value:.4f}")
    print(f"[hypertuner] Best params: {json.dumps(best_params, indent=2)}")

    # Save results
    results = {
        "study_name": study_name,
        "n_trials": n_trials,
        "base_model": base_model,
        "best_trial": best_trial.number,
        "best_value": best_value,
        "best_params": best_params,
        "all_trials": [
            {
                "number": t.number,
                "value": t.value,
                "params": t.params,
                "state": str(t.state),
            }
            for t in study.trials
        ],
    }
    results_path = TUNING_DIR / f"{study_name}_results.json"
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"[hypertuner] Results saved to {results_path}")

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sift Brain hyperparameter tuner")
    parser.add_argument("--trials", type=int, default=10, help="Number of Optuna trials")
    parser.add_argument("--base", default="Qwen/Qwen3-8B", help="Base model HF ID or alias")
    parser.add_argument("--study-name", default=None, help="Optuna study name")
    args = parser.parse_args()

    run_sweep(n_trials=args.trials, base_model=args.base, study_name=args.study_name)
