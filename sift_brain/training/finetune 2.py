"""LoRA/QLoRA fine-tuning for Sift Brain.

Trains a low-rank adapter on a base open-weight model using the Sift
training dataset (session turns + KB Q&A pairs).

Supported base models:
  - Qwen/Qwen3-8B             (default — fast local GPU)
  - Qwen/Qwen3-30B-A3B        (30B MoE — strong reasoning)
  - meta-llama/Llama-3.3-8B-Instruct
  - meta-llama/Llama-3.3-70B-Instruct (cloud GPU)
  - mistralai/Mistral-7B-Instruct-v0.3

Hyperparameter config is loaded from a YAML file. Default config is
written to data/training/finetune_config.yaml on first run.

Usage:
    python3 scripts/train_sift_brain.py --base qwen3-8b --epochs 3
    # or:
    from sift_brain.training.finetune import run_finetune
    run_finetune(config_path="data/training/finetune_config.yaml")
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"
ADAPTERS_DIR = DATA_DIR / "model_adapters"
TRAINING_DIR = DATA_DIR / "training"
CONFIG_PATH = TRAINING_DIR / "finetune_config.yaml"

# Base model aliases
BASE_MODEL_ALIASES: dict[str, str] = {
    "qwen3-8b": "Qwen/Qwen3-8B",
    "qwen3-8b-instruct": "Qwen/Qwen3-8B-Instruct",
    "qwen3-30b": "Qwen/Qwen3-30B-A3B",
    "llama3-8b": "meta-llama/Llama-3.3-8B-Instruct",
    "llama3-70b": "meta-llama/Llama-3.3-70B-Instruct",
    "mistral-7b": "mistralai/Mistral-7B-Instruct-v0.3",
    "gemma3-12b": "google/gemma-3-12b-it",
}

DEFAULT_CONFIG: dict[str, Any] = {
    "base_model": "Qwen/Qwen3-8B",
    "adapter_name": "sift-brain",
    "lora": {
        "r": 16,                  # LoRA rank
        "lora_alpha": 32,         # LoRA alpha (usually 2x rank)
        "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        "lora_dropout": 0.05,
        "bias": "none",
        "task_type": "CAUSAL_LM",
    },
    "training": {
        "num_train_epochs": 3,
        "per_device_train_batch_size": 2,
        "per_device_eval_batch_size": 2,
        "gradient_accumulation_steps": 4,
        "warmup_steps": 50,
        "learning_rate": 2e-4,
        "weight_decay": 0.01,
        "lr_scheduler_type": "cosine",
        "logging_steps": 10,
        "eval_steps": 100,
        "save_steps": 200,
        "max_seq_length": 2048,
        "fp16": False,
        "bf16": True,           # Use bf16 if GPU supports it
        "optim": "adamw_torch",
        "dataloader_num_workers": 0,
        "remove_unused_columns": False,
    },
    "quantization": {
        "load_in_4bit": True,   # QLoRA — 4-bit base model
        "bnb_4bit_quant_type": "nf4",
        "bnb_4bit_compute_dtype": "bfloat16",
        "bnb_4bit_use_double_quant": True,
    },
    "dataset": {
        "train_file": str(TRAINING_DIR / "sift_dataset.train.jsonl"),
        "eval_file": str(TRAINING_DIR / "sift_dataset.eval.jsonl"),
        "format": "openai_messages",  # or "alpaca"
    },
    "output": {
        "adapter_dir": str(ADAPTERS_DIR / "sift-brain-latest"),
        "push_to_hub": False,
    },
}


def _write_default_config() -> Path:
    TRAINING_DIR.mkdir(parents=True, exist_ok=True)
    try:
        import yaml
        CONFIG_PATH.write_text(yaml.dump(DEFAULT_CONFIG, default_flow_style=False), encoding="utf-8")
    except ImportError:
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
    print(f"[finetune] Wrote default config to {CONFIG_PATH}")
    return CONFIG_PATH


def _load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return DEFAULT_CONFIG
    text = config_path.read_text(encoding="utf-8")
    try:
        import yaml
        return yaml.safe_load(text) or DEFAULT_CONFIG
    except ImportError:
        return json.loads(text)


def _resolve_base_model(base: str) -> str:
    return BASE_MODEL_ALIASES.get(base.lower(), base)


def _check_requirements() -> None:
    missing = []
    for pkg in ["peft", "trl", "transformers", "accelerate"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        raise RuntimeError(
            f"Missing fine-tuning dependencies: {', '.join(missing)}\n"
            f"Install with: pip install -r requirements-brain.txt"
        )


def run_finetune(
    config_path: str | Path | None = None,
    *,
    base_model: str | None = None,
    epochs: int | None = None,
    lora_rank: int | None = None,
    learning_rate: float | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run LoRA/QLoRA fine-tuning.

    Args:
        config_path: Path to YAML/JSON config. Uses default if not provided.
        base_model:  Override base model (alias or HF model id).
        epochs:      Override number of training epochs.
        lora_rank:   Override LoRA rank (r).
        learning_rate: Override learning rate.
        dry_run:     Validate setup without actually training.

    Returns:
        Training result dict with adapter_dir, train_loss, eval_loss.
    """
    _check_requirements()

    cfg_path = Path(config_path) if config_path else CONFIG_PATH
    if not cfg_path.exists():
        cfg_path = _write_default_config()

    config = _load_config(cfg_path)

    # Apply overrides
    if base_model:
        config["base_model"] = _resolve_base_model(base_model)
    if epochs:
        config["training"]["num_train_epochs"] = epochs
    if lora_rank:
        config["lora"]["r"] = lora_rank
        config["lora"]["lora_alpha"] = lora_rank * 2
    if learning_rate:
        config["training"]["learning_rate"] = learning_rate

    print(f"[finetune] Base model: {config['base_model']}")
    print(f"[finetune] LoRA rank={config['lora']['r']}, alpha={config['lora']['lora_alpha']}")
    print(f"[finetune] Epochs: {config['training']['num_train_epochs']}")
    print(f"[finetune] Output: {config['output']['adapter_dir']}")

    if dry_run:
        print("[finetune] Dry run — skipping actual training.")
        return {"status": "dry_run", "config": config}

    # ---- Actual fine-tuning -----------------------------------------------
    import torch
    from datasets import load_dataset
    from peft import LoraConfig, get_peft_model, TaskType
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        TrainingArguments,
        BitsAndBytesConfig,
    )
    from trl import SFTTrainer

    ADAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    adapter_dir = Path(config["output"]["adapter_dir"])
    adapter_dir.mkdir(parents=True, exist_ok=True)

    # Quantization
    quant_cfg = config.get("quantization", {})
    bnb_config = None
    if quant_cfg.get("load_in_4bit"):
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=quant_cfg.get("bnb_4bit_quant_type", "nf4"),
            bnb_4bit_compute_dtype=getattr(torch, quant_cfg.get("bnb_4bit_compute_dtype", "bfloat16")),
            bnb_4bit_use_double_quant=quant_cfg.get("bnb_4bit_use_double_quant", True),
        )

    # Load model + tokenizer
    print(f"[finetune] Loading {config['base_model']} ...")
    model = AutoModelForCausalLM.from_pretrained(
        config["base_model"],
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(config["base_model"], trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # LoRA
    lora_cfg = config["lora"]
    peft_config = LoraConfig(
        r=lora_cfg["r"],
        lora_alpha=lora_cfg["lora_alpha"],
        target_modules=lora_cfg.get("target_modules"),
        lora_dropout=lora_cfg.get("lora_dropout", 0.05),
        bias=lora_cfg.get("bias", "none"),
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # Dataset
    ds_cfg = config["dataset"]
    dataset = load_dataset(
        "json",
        data_files={"train": ds_cfg["train_file"], "eval": ds_cfg.get("eval_file", ds_cfg["train_file"])},
    )

    # Training args
    t_cfg = config["training"]
    training_args = TrainingArguments(
        output_dir=str(adapter_dir),
        num_train_epochs=t_cfg["num_train_epochs"],
        per_device_train_batch_size=t_cfg["per_device_train_batch_size"],
        per_device_eval_batch_size=t_cfg.get("per_device_eval_batch_size", 2),
        gradient_accumulation_steps=t_cfg.get("gradient_accumulation_steps", 4),
        warmup_steps=t_cfg.get("warmup_steps", 50),
        learning_rate=float(t_cfg["learning_rate"]),
        weight_decay=t_cfg.get("weight_decay", 0.01),
        lr_scheduler_type=t_cfg.get("lr_scheduler_type", "cosine"),
        logging_steps=t_cfg.get("logging_steps", 10),
        eval_steps=t_cfg.get("eval_steps", 100),
        save_steps=t_cfg.get("save_steps", 200),
        fp16=t_cfg.get("fp16", False),
        bf16=t_cfg.get("bf16", True),
        optim=t_cfg.get("optim", "adamw_torch"),
        dataloader_num_workers=t_cfg.get("dataloader_num_workers", 0),
        remove_unused_columns=t_cfg.get("remove_unused_columns", False),
        load_best_model_at_end=True,
        evaluation_strategy="steps",
        save_strategy="steps",
        report_to="none",
    )

    # SFT Trainer
    def _format_messages(example: dict) -> dict:
        messages = example.get("messages", [])
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        return {"text": text}

    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset["train"].map(_format_messages),
        eval_dataset=dataset["eval"].map(_format_messages),
        tokenizer=tokenizer,
        peft_config=peft_config,
        args=training_args,
        dataset_text_field="text",
        max_seq_length=t_cfg.get("max_seq_length", 2048),
    )

    print("[finetune] Starting training ...")
    train_result = trainer.train()
    trainer.save_model(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))

    metrics = train_result.metrics
    print(f"[finetune] Done. train_loss={metrics.get('train_loss', '?'):.4f}")
    print(f"[finetune] Adapter saved to {adapter_dir}")

    # Write run metadata
    run_meta = {
        "base_model": config["base_model"],
        "adapter_name": config.get("adapter_name", "sift-brain"),
        "adapter_dir": str(adapter_dir),
        "lora_rank": lora_cfg["r"],
        "epochs": t_cfg["num_train_epochs"],
        "train_loss": metrics.get("train_loss"),
        "config": config,
    }
    (adapter_dir / "run_metadata.json").write_text(json.dumps(run_meta, indent=2), encoding="utf-8")

    return run_meta
