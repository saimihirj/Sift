#!/usr/bin/env python3
"""End-to-end Sift Brain training launcher.

Builds the training dataset, runs LoRA/QLoRA fine-tuning,
evaluates the adapter, and registers it in the model registry.

Usage:
    python3 scripts/train_sift_brain.py
    python3 scripts/train_sift_brain.py --base qwen3-8b --epochs 3 --lora-rank 16
    python3 scripts/train_sift_brain.py --dataset-only
    python3 scripts/train_sift_brain.py --eval-only --adapter data/model_adapters/sift-brain-latest
    python3 scripts/train_sift_brain.py --sweep --trials 10
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sift Brain — training pipeline launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline (dataset + train + eval + register)
  python3 scripts/train_sift_brain.py

  # Custom base model and LoRA config
  python3 scripts/train_sift_brain.py --base qwen3-8b --epochs 3 --lora-rank 16 --lr 2e-4

  # Larger model (needs cloud GPU)
  python3 scripts/train_sift_brain.py --base llama3-70b --epochs 1

  # Dataset only
  python3 scripts/train_sift_brain.py --dataset-only

  # Evaluate existing adapter
  python3 scripts/train_sift_brain.py --eval-only --adapter data/model_adapters/sift-brain-latest

  # Hyperparameter sweep (10 trials)
  python3 scripts/train_sift_brain.py --sweep --trials 10
""",
    )
    parser.add_argument("--base", default="qwen3-8b", help="Base model alias or HF id (default: qwen3-8b)")
    parser.add_argument("--epochs", type=int, default=3, help="Training epochs (default: 3)")
    parser.add_argument("--lora-rank", type=int, default=16, help="LoRA rank (default: 16)")
    parser.add_argument("--lr", type=float, default=None, help="Learning rate (default: from config)")
    parser.add_argument("--config", default=None, help="Path to YAML/JSON finetune config")
    parser.add_argument("--dry-run", action="store_true", help="Validate setup without training")
    parser.add_argument("--dataset-only", action="store_true", help="Only build the dataset, skip training")
    parser.add_argument("--eval-only", action="store_true", help="Only evaluate an existing adapter")
    parser.add_argument("--adapter", default=None, help="Adapter path for --eval-only")
    parser.add_argument("--sweep", action="store_true", help="Run hyperparameter sweep instead of single training run")
    parser.add_argument("--trials", type=int, default=10, help="Number of Optuna trials for --sweep")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  Sift Brain — Training Pipeline")
    print(f"{'='*60}\n")

    # ---- Dataset -----------------------------------------------------------
    if not args.eval_only:
        print("[train] Step 1/3: Building training dataset ...")
        from sift_brain.training.dataset_builder import build_dataset
        dataset_info = build_dataset()
        print(f"[train] Dataset: {dataset_info['total']} examples "
              f"(train={dataset_info['train']}, eval={dataset_info['eval']})")

        if args.dataset_only:
            print("\nDataset ready. Skipping training.")
            return

    # ---- Hyperparameter sweep ----------------------------------------------
    if args.sweep:
        print(f"\n[train] Step 2/3: Hyperparameter sweep ({args.trials} trials) ...")
        from sift_brain.training.hypertuner import run_sweep
        sweep_results = run_sweep(n_trials=args.trials, base_model=args.base)
        print(f"\nBest eval_loss: {sweep_results['best_value']:.4f}")
        print(f"Best params: {sweep_results['best_params']}")
        return

    # ---- Fine-tuning -------------------------------------------------------
    if not args.eval_only:
        print("\n[train] Step 2/3: Running LoRA/QLoRA fine-tuning ...")
        from sift_brain.training.finetune import run_finetune
        train_result = run_finetune(
            config_path=args.config,
            base_model=args.base,
            epochs=args.epochs,
            lora_rank=args.lora_rank,
            learning_rate=args.lr,
            dry_run=args.dry_run,
        )
        if args.dry_run:
            print("\nDry run complete.")
            return
        adapter_path = train_result.get("adapter_dir")
    else:
        adapter_path = args.adapter

    # ---- Evaluation --------------------------------------------------------
    print(f"\n[train] Step 3/3: Evaluating adapter ...")
    from sift_brain.training.evaluator import run_eval
    eval_report = run_eval(adapter_path=adapter_path, n_examples=30)

    if "error" not in eval_report:
        print(f"[train] Avg score: {eval_report['avg_overall_score']:.3f}")

    # ---- Register ----------------------------------------------------------
    if adapter_path and not args.eval_only:
        print(f"\n[train] Registering adapter in model registry ...")
        from sift_brain.serving.model_registry import ModelRegistry
        registry = ModelRegistry.load()
        eval_scores = {k: v for k, v in eval_report.items() if k.startswith("avg_")}
        registry.register_adapter(adapter_path, eval_scores=eval_scores)
        print(f"[train] Registry: {registry.stats()['total_adapters']} adapters")

    print(f"\n{'='*60}")
    print(f"  Training pipeline complete!")
    print(f"  Adapter: {adapter_path}")
    if "avg_overall_score" in eval_report:
        print(f"  Score:   {eval_report['avg_overall_score']:.3f}")
    print(f"\n  Start the server: npm run brain:serve")
    print(f"  Or: python3 scripts/serve_sift_brain.py")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
