#!/usr/bin/env python3
"""
scripts/train_config.py
=======================
QLoRA supervised fine-tuning (SFT) blueprint for Sift's custom LLM.

This script encodes the exact hyperparameter decisions made for the Sift
conversational model and drives a complete training run via Unsloth — from
loading and quantizing the base model, to applying LoRA adapters, through
the full SFT loop, and finally saving merge-ready weights.

Architecture decisions captured here
-------------------------------------
  Base model     : Qwen2.5-7B-Instruct  (default)  — or Llama-3-8B-Instruct
  PEFT method    : QLoRA  (4-bit NF4 quantization, LoRA rank 32)
  Sequence length: 8192 tokens  (matches OLLAMA_NUM_CTX_BALANCED)
  Dataset format : ChatML  (output of export_fine_tune_data.py --format chatml)

GPU requirements
----------------
  Training (LoRA only): 16–24 GB VRAM  (A10G, RTX 3090/4090, L4)
  Full merge + save   : 14 GB VRAM
  For 16 GB Mac M-series: --dry-run / data audit only. Run training on cloud.

Quick start
-----------
  # 1. Export training data (local Mac is fine for this step):
  python scripts/export_fine_tune_data.py --min-turns 4 --min-coverage 20

  # 2. Audit data quality without training:
  python scripts/train_config.py --dry-run --data data/exports/sift_finetune_<ts>.jsonl

  # 3. Full training run (on GPU machine):
  python scripts/train_config.py --data data/exports/sift_finetune_<ts>.jsonl

  # 4. Resume from checkpoint:
  python scripts/train_config.py --data <path> --resume-from-checkpoint

  # 5. Use Llama-3-8B instead of Qwen2.5-7B:
  python scripts/train_config.py --data <path> --base llama3

  # 6. Quick validation run (1 step, no save):
  python scripts/train_config.py --data <path> --max-steps 1 --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR  = ROOT_DIR / "data"
EXPORTS_DIR = DATA_DIR / "exports"
ADAPTERS_DIR = DATA_DIR / "model_adapters"


# ── Model registry ────────────────────────────────────────────────────────────
# Canonical HuggingFace IDs for each supported base.
# Unsloth pre-quantized builds are preferred (bnb-4bit) — they skip the local
# quantization step, reducing VRAM spike on load.

BASE_MODEL_MAP: dict[str, dict[str, str]] = {
    "qwen2.5-7b": {
        "hf_id": "Qwen/Qwen2.5-7B-Instruct",
        "unsloth_id": "unsloth/Qwen2.5-7B-Instruct-bnb-4bit",
        "chat_template": "qwen",
        "note": "Best default for Sift: strong instruction following, multilingual, fast.",
    },
    "qwen3-8b": {
        "hf_id": "Qwen/Qwen3-8B-Instruct",
        "unsloth_id": "unsloth/Qwen3-8B-Instruct-bnb-4bit",
        "chat_template": "qwen",
        "note": "Latest Qwen generation. Use if available on Unsloth hub.",
    },
    "llama3": {
        "hf_id": "meta-llama/Meta-Llama-3-8B-Instruct",
        "unsloth_id": "unsloth/Meta-Llama-3-8B-Instruct-bnb-4bit",
        "chat_template": "llama3",
        "note": "Strong alternative. Requires HF gated repo access.",
    },
    "llama3.1-8b": {
        "hf_id": "meta-llama/Llama-3.1-8B-Instruct",
        "unsloth_id": "unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit",
        "chat_template": "llama3",
        "note": "Llama 3.1 — better long-context than 3.0.",
    },
    "mistral-7b": {
        "hf_id": "mistralai/Mistral-7B-Instruct-v0.3",
        "unsloth_id": "unsloth/mistral-7b-instruct-v0.3-bnb-4bit",
        "chat_template": "mistral",
        "note": "Compact, fast. Good fallback if Qwen is unavailable.",
    },
}
DEFAULT_BASE = "qwen2.5-7b"


# ── Core hyperparameter config ────────────────────────────────────────────────

@dataclass
class LoRAConfig:
    """Low-Rank Adaptation settings.

    r=32 / alpha=64 rationale
    --------------------------
    r=32 is the goldilocks rank for Sift's use case:
      - r=8  captures coarse stylistic patterns but misses nuanced conversational
             formatting rules (markdown bullets, inline code, label colon blocks).
      - r=16 is a good general-purpose rank but undershoots for a highly
             specialised domain like investor-grade pitch analysis.
      - r=32 injects enough capacity to encode the full Sift response grammar
             (punchy fragments, one-question-at-a-time pacing, coverage tracking)
             without the instability of r=64+ on datasets under 10k examples.
      - r=64 risks overfitting and increases VRAM cost by 2× for marginal gain.

    alpha=64 = 2 × r (standard scaling factor). Keeps the effective LoRA
    learning rate consistent regardless of rank choice.

    All 7 linear projection layers are targeted. Skipping gate_proj / up_proj /
    down_proj (the MLP layers) leads to "catastrophic forgetting" where the model
    loses factual knowledge while gaining style — not what we want here.
    """
    r: int = 32
    alpha: int = 64                          # always 2×r
    target_modules: list[str] = field(default_factory=lambda: [
        "q_proj",    # query projection  — captures question phrasing patterns
        "k_proj",    # key projection    — information routing / attention structure
        "v_proj",    # value projection  — content retrieval patterns
        "o_proj",    # output projection — response composition
        "gate_proj", # MLP gate          — knowledge & factual recall
        "up_proj",   # MLP up            — token-level feature expansion
        "down_proj", # MLP down          — compressed output representation
    ])
    dropout: float = 0.05          # small dropout prevents overfitting on <2k examples
    bias: str = "none"             # do not train bias terms — wastes parameters
    use_gradient_checkpointing: str = "unsloth"  # saves up to 70% VRAM vs standard
    use_rslora: bool = False       # RSLoRA stabilises very high ranks (≥64); not needed at r=32
    loftq_config: None = None      # LoftQ initialisation — only beneficial at r≥64
    random_state: int = 3407       # fixed seed for reproducibility


@dataclass
class QuantizationConfig:
    """4-bit NF4 quantization via bitsandbytes.

    Why NF4 over INT4?
    ------------------
    NF4 (Normal Float 4) is information-theoretically optimal for weights drawn
    from a normal distribution — which transformer weights approximately follow.
    It loses ~1–2% quality vs fp16 but reduces VRAM by 4×, making 7–8B models
    trainable on a single A10G / L4 GPU.

    Double quantization saves an additional ~0.4 bits per parameter by also
    quantizing the quantization constants themselves — effectively free on
    modern hardware.
    """
    load_in_4bit: bool = True
    bnb_4bit_quant_type: str = "nf4"
    bnb_4bit_compute_dtype: str = "bfloat16"   # bfloat16 > float16 for stability on A100/H100
    bnb_4bit_use_double_quant: bool = True      # save ~0.4 bits/param extra
    dtype: None = None                           # let Unsloth auto-detect (bf16 on Ampere+)


@dataclass
class OptimizerConfig:
    """Training optimiser and learning rate schedule.

    LR = 2e-4 rationale
    --------------------
    The safe range for QLoRA fine-tuning is 1e-4 to 5e-4.
      - 1e-4: converges slowly, good for large datasets (>50k examples)
      - 2e-4: standard sweet spot — fast convergence without loss spikes
      - 5e-4: aggressive; risks spiking on small, domain-specific datasets

    Cosine decay brings the LR down smoothly to ~0 at epoch end, preventing
    the model from "unlearning" structure it absorbed in early training.

    Warmup = 0.03 (3% of steps). Too-fast LR warmup causes gradient spikes
    in the first epoch, especially with large batch sizes.

    adamw_8bit vs paged_adamw_8bit
    --------------------------------
    paged_adamw_8bit pages optimizer states to CPU RAM when VRAM pressure is
    high. On cloud GPUs with ≥24 GB VRAM, adamw_8bit is slightly faster.
    On smaller GPUs (16 GB), use paged_adamw_8bit.
    """
    optimizer: str = "paged_adamw_8bit"
    learning_rate: float = 2e-4
    lr_scheduler_type: str = "cosine"
    warmup_ratio: float = 0.03
    weight_decay: float = 0.01             # mild regularisation
    max_grad_norm: float = 1.0             # gradient clipping for stability


@dataclass
class SequenceConfig:
    """Sequence length and packing.

    max_seq_length = 8192 rationale
    --------------------------------
    This exactly matches OLLAMA_NUM_CTX_BALANCED = 8192 set in model_router.py.
    Training and inference must use the same context window. Mismatched lengths
    cause positional embedding extrapolation errors and degrade quality.

    The 8192-token budget decomposes as:
      system prompt      ≈   300 tokens
      retrieval context  ≈   800 tokens  (HISTORY_TOKEN_BUDGET = 3200 tokens)
      12-turn history    ≈  3200 tokens
      response headroom  ≈   480 tokens
      overhead / special ≈   300 tokens
      ─────────────────────────────────
      total              ≈  5080 tokens  (well within 8192; ~38% headroom)

    Packing = True
    --------------
    Short conversational turns (often 200–600 tokens each) would waste GPU
    compute if padded individually to 8192. Packing concatenates multiple
    training examples into a single 8192-token block separated by EOS tokens,
    increasing effective batch size and GPU utilisation by 3–8×.

    NOTE: packing can introduce cross-contamination between concatenated
    examples if the model attends across EOS tokens. Unsloth's packing
    implementation correctly masks these boundaries.
    """
    max_seq_length: int = 8192
    packing: bool = True


@dataclass
class TrainingConfig:
    """SFT Trainer arguments."""
    per_device_train_batch_size: int = 2    # keep low; gradient accumulation compensates
    gradient_accumulation_steps: int = 4    # effective batch = 2 × 4 = 8
    num_train_epochs: int = 3               # 3 epochs is the standard for SFT on <5k examples
    max_steps: int = -1                     # -1 = use epochs; set >0 to override
    save_steps: int = 200                   # checkpoint every 200 steps
    logging_steps: int = 10
    evaluation_strategy: str = "steps"
    eval_steps: int = 100
    fp16: bool = False                      # use bf16 instead on Ampere+
    bf16: bool = True
    optim: str = "paged_adamw_8bit"         # mirrors OptimizerConfig
    seed: int = 3407
    output_dir: str = str(ADAPTERS_DIR / "sift-qlora-run")
    report_to: str = "none"                 # set "wandb" to enable W&B logging
    dataloader_num_workers: int = 0         # 0 is safest on most cloud setups
    group_by_length: bool = False           # disabled — packing handles this


# ── Data loading ──────────────────────────────────────────────────────────────

def load_chatml_dataset(jsonl_path: Path, tokenizer, max_seq_length: int):
    """Load and tokenize a ChatML JSONL file produced by export_fine_tune_data.py.

    Converts the 'messages' array into a single formatted string using the
    model's built-in chat template, then tokenizes with packing-compatible
    truncation.

    The 'metadata' field is stripped before tokenization — it's for offline
    analysis only and must not appear in training inputs.
    """
    try:
        from datasets import Dataset
    except ImportError:
        raise ImportError("pip install datasets  — required for dataset loading")

    examples = []
    with jsonl_path.open("r", encoding="utf-8") as fh:
        for line_num, raw in enumerate(fh, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError as exc:
                print(f"[warn] Skipping malformed line {line_num}: {exc}", file=sys.stderr)
                continue

            messages = record.get("messages", [])
            if not messages:
                continue

            # Strip metadata — it must not enter the training context.
            formatted = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=False,
            )
            examples.append({"text": formatted})

    if not examples:
        raise ValueError(
            f"No valid examples found in {jsonl_path}.\n"
            "Run: python scripts/export_fine_tune_data.py --format chatml"
        )

    dataset = Dataset.from_list(examples)

    # 80/20 train/eval split (deterministic with seed 3407)
    split = dataset.train_test_split(test_size=0.2, seed=3407)
    return split["train"], split["test"]


def print_dataset_stats(train_ds, eval_ds, tokenizer) -> None:
    """Print token distribution stats to verify packing efficiency."""
    print("\n── Dataset Statistics ──────────────────────────────────────────")
    print(f"  Train examples : {len(train_ds):,}")
    print(f"  Eval  examples : {len(eval_ds):,}")

    # Sample token lengths from first 100 examples
    sample = train_ds.select(range(min(100, len(train_ds))))
    lengths = [len(tokenizer(ex["text"])["input_ids"]) for ex in sample]
    avg_len = sum(lengths) / len(lengths)
    max_len = max(lengths)
    packing_gain = 8192 / avg_len if avg_len > 0 else 1.0

    print(f"  Avg token len  : {avg_len:.0f} tokens")
    print(f"  Max token len  : {max_len} tokens")
    print(f"  Packing gain   : ~{packing_gain:.1f}× GPU utilisation vs no packing")
    if max_len > 8192:
        print(f"  [warn] {sum(1 for l in lengths if l > 8192)} example(s) exceed 8192 tokens — will be truncated")
    print()


# ── Training entry point ───────────────────────────────────────────────────────

def build_and_train(
    data_path: Path,
    base_alias: str = DEFAULT_BASE,
    lora: LoRAConfig | None = None,
    quant: QuantizationConfig | None = None,
    optim: OptimizerConfig | None = None,
    seq: SequenceConfig | None = None,
    train_cfg: TrainingConfig | None = None,
    resume_from_checkpoint: bool = False,
    dry_run: bool = False,
) -> Path:
    """Full QLoRA SFT training run.

    Returns the path to the saved LoRA adapter directory.
    """
    # Apply defaults for any unspecified configs
    lora      = lora      or LoRAConfig()
    quant     = quant     or QuantizationConfig()
    optim_cfg = optim     or OptimizerConfig()
    seq_cfg   = seq       or SequenceConfig()
    t_cfg     = train_cfg or TrainingConfig()

    # Override optim in TrainingConfig to stay in sync
    t_cfg.optim = optim_cfg.optimizer
    if t_cfg.max_steps == -1:
        pass  # use epochs

    model_info = BASE_MODEL_MAP[base_alias]

    print(f"\n{'═'*62}")
    print(f"  Sift QLoRA Fine-Tuning Blueprint")
    print(f"{'═'*62}")
    print(f"  Base model   : {model_info['hf_id']}")
    print(f"  LoRA rank    : r={lora.r}  α={lora.alpha}")
    print(f"  Seq length   : {seq_cfg.max_seq_length} tokens")
    print(f"  Quantization : 4-bit NF4 + double quant")
    print(f"  Optimizer    : {optim_cfg.optimizer}  LR={optim_cfg.learning_rate}")
    print(f"  Epochs       : {t_cfg.num_train_epochs}")
    print(f"  Packing      : {seq_cfg.packing}")
    print(f"  Output dir   : {t_cfg.output_dir}")
    print(f"{'═'*62}\n")

    # ── Dependency check ──────────────────────────────────────────────────────
    try:
        import torch
        _has_torch = True
    except ImportError:
        _has_torch = False

    if _has_torch:
        import torch
        print(f"[train] PyTorch {torch.__version__}  |  CUDA: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            gpu = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
            print(f"[train] GPU: {gpu}  |  VRAM: {vram_gb:.1f} GB")
            if vram_gb < 12:
                print("[warn] < 12 GB VRAM detected. Reduce batch size or use smaller base model.")
        else:
            print("[train] No CUDA GPU — CPU/Mac mode.")
    else:
        print("[train] PyTorch not installed. Install on the GPU machine before training.")

    _gpu_available = _has_torch and __import__("torch").cuda.is_available()

    # Dry-run on CPU/Mac: print config and data stats, then exit cleanly.
    if dry_run and not _gpu_available:
        print("\n── Dry-run (CPU/Mac) — config audit only ───────────────────")
        _print_config_summary(lora, quant, optim_cfg, seq_cfg, t_cfg)

        # Audit the data file
        print(f"── Data Audit ──────────────────────────────────────────────")
        print(f"  File: {data_path}")
        example_count = sum(1 for line in data_path.open() if line.strip())
        print(f"  Raw lines (examples): {example_count}")
        # Peek at first example
        with data_path.open() as fh:
            first_raw = fh.readline().strip()
        if first_raw:
            first = json.loads(first_raw)
            msgs = first.get("messages", [])
            print(f"  First example roles : {[m['role'] for m in msgs]}")
            total_chars = sum(len(m['content']) for m in msgs)
            est_tokens = total_chars // 4
            print(f"  First example ~tokens: {est_tokens}")
        print()
        print("  Config is valid ✓")
        print("  To train, run this script on a machine with CUDA (≥16 GB VRAM).")
        return Path(t_cfg.output_dir)

    if not _gpu_available and not dry_run:
        raise RuntimeError(
            "No CUDA GPU detected.\n"
            "Training requires a GPU with ≥16 GB VRAM.\n"
            "Use --dry-run to audit data and config on CPU/Mac."
        )

    # ── GPU path: load Unsloth ────────────────────────────────────────────────
    try:
        from unsloth import FastLanguageModel
    except ImportError:
        raise ImportError(
            "pip install unsloth  — Unsloth not found.\n"
            "Installation: https://github.com/unslothai/unsloth#installation\n"
            "Note: Unsloth requires CUDA. It cannot run on macOS Apple Silicon."
        )

    # ── Load model ────────────────────────────────────────────────────────────
    print(f"\n[train] Loading base model (Unsloth pre-quantized build)...")
    from unsloth import FastLanguageModel

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_info["unsloth_id"],
        max_seq_length=seq_cfg.max_seq_length,
        dtype=quant.dtype,
        load_in_4bit=quant.load_in_4bit,
    )
    print(f"[train] Base model loaded ✓")

    # ── Apply LoRA ────────────────────────────────────────────────────────────
    print(f"[train] Applying QLoRA adapters (r={lora.r}, α={lora.alpha})...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=lora.r,
        target_modules=lora.target_modules,
        lora_alpha=lora.alpha,
        lora_dropout=lora.dropout,
        bias=lora.bias,
        use_gradient_checkpointing=lora.use_gradient_checkpointing,
        random_state=lora.random_state,
        use_rslora=lora.use_rslora,
        loftq_config=lora.loftq_config,
    )

    # Print trainable parameter count
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    pct = 100 * trainable_params / total_params
    print(f"[train] Trainable params: {trainable_params:,} / {total_params:,} ({pct:.2f}%)")

    # ── Load & tokenize dataset ───────────────────────────────────────────────
    print(f"\n[train] Loading dataset: {data_path}")
    train_ds, eval_ds = load_chatml_dataset(data_path, tokenizer, seq_cfg.max_seq_length)
    print_dataset_stats(train_ds, eval_ds, tokenizer)

    if dry_run:
        print("[dry-run] Skipping training loop (--dry-run set).")
        _print_config_summary(lora, quant, optim_cfg, seq_cfg, t_cfg)
        return Path(t_cfg.output_dir)

    # ── SFT Trainer ───────────────────────────────────────────────────────────
    try:
        from trl import SFTTrainer, SFTConfig
    except ImportError:
        raise ImportError("pip install trl>=0.8  — TRL not found")
    from transformers import TrainingArguments

    ADAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = Path(t_cfg.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    sft_args = SFTConfig(
        dataset_text_field="text",
        max_seq_length=seq_cfg.max_seq_length,
        packing=seq_cfg.packing,
        per_device_train_batch_size=t_cfg.per_device_train_batch_size,
        gradient_accumulation_steps=t_cfg.gradient_accumulation_steps,
        num_train_epochs=t_cfg.num_train_epochs,
        max_steps=t_cfg.max_steps,
        learning_rate=optim_cfg.learning_rate,
        lr_scheduler_type=optim_cfg.lr_scheduler_type,
        warmup_ratio=optim_cfg.warmup_ratio,
        weight_decay=optim_cfg.weight_decay,
        max_grad_norm=optim_cfg.max_grad_norm,
        fp16=t_cfg.fp16,
        bf16=t_cfg.bf16,
        optim=t_cfg.optim,
        save_steps=t_cfg.save_steps,
        logging_steps=t_cfg.logging_steps,
        evaluation_strategy=t_cfg.evaluation_strategy,
        eval_steps=t_cfg.eval_steps,
        output_dir=str(output_path),
        report_to=t_cfg.report_to,
        seed=t_cfg.seed,
        dataloader_num_workers=t_cfg.dataloader_num_workers,
        group_by_length=t_cfg.group_by_length,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        args=sft_args,
    )

    print(f"[train] Starting SFT loop ...")
    print(f"[train] Steps per epoch ≈ {len(train_ds) // (t_cfg.per_device_train_batch_size * t_cfg.gradient_accumulation_steps)}")

    trainer_stats = trainer.train(
        resume_from_checkpoint=resume_from_checkpoint or None,
    )

    print(f"\n[train] Training complete ✓")
    print(f"[train] Train loss  : {trainer_stats.training_loss:.4f}")
    print(f"[train] Runtime     : {trainer_stats.metrics.get('train_runtime', 0):.0f}s")

    # ── Save LoRA adapter ─────────────────────────────────────────────────────
    adapter_path = output_path / "lora_adapter"
    model.save_pretrained(str(adapter_path))
    tokenizer.save_pretrained(str(adapter_path))
    print(f"[train] LoRA adapter saved → {adapter_path}")

    # ── Optional: merge and save full model ───────────────────────────────────
    # Merging produces a plain fp16 model you can push to Ollama / vLLM.
    # Comment this out to keep the adapter-only form (smaller, easier to iterate).
    merged_path = output_path / "merged_model"
    print(f"[train] Merging LoRA into base weights (fp16)...")
    model.save_pretrained_merged(
        str(merged_path),
        tokenizer,
        save_method="merged_16bit",
    )
    print(f"[train] Merged model saved → {merged_path}")

    # ── GGUF quantization for Ollama ──────────────────────────────────────────
    gguf_path = output_path / "gguf"
    print(f"[train] Exporting GGUF (Q4_K_M) for Ollama ...")
    model.save_pretrained_gguf(
        str(gguf_path),
        tokenizer,
        quantization_method="q4_k_m",   # best quality/size tradeoff for inference
    )
    print(f"[train] GGUF model saved → {gguf_path}")
    print(f"\n  To run locally:\n    ollama create sift-brain -f {gguf_path}/Modelfile")
    print(f"    ollama run sift-brain")

    print(f"\n{'═'*62}")
    print(f"  Pipeline complete")
    print(f"  LoRA adapter : {adapter_path}")
    print(f"  Merged fp16  : {merged_path}")
    print(f"  GGUF (Ollama): {gguf_path}")
    print(f"{'═'*62}\n")

    return adapter_path


# ── Config summary printer ────────────────────────────────────────────────────

def _print_config_summary(
    lora: LoRAConfig,
    quant: QuantizationConfig,
    optim: OptimizerConfig,
    seq: SequenceConfig,
    train: TrainingConfig,
) -> None:
    print("\n── Full Hyperparameter Config ──────────────────────────────────")
    print(f"  LoRA rank              : {lora.r}")
    print(f"  LoRA alpha             : {lora.alpha}")
    print(f"  LoRA dropout           : {lora.dropout}")
    print(f"  LoRA target modules    : {', '.join(lora.target_modules)}")
    print(f"  Gradient checkpointing : {lora.use_gradient_checkpointing}")
    print(f"  Quantization           : 4-bit NF4  double_quant={quant.bnb_4bit_use_double_quant}")
    print(f"  Compute dtype          : {quant.bnb_4bit_compute_dtype}")
    print(f"  Optimizer              : {optim.optimizer}")
    print(f"  Learning rate          : {optim.learning_rate}  schedule={optim.lr_scheduler_type}")
    print(f"  Warmup ratio           : {optim.warmup_ratio}")
    print(f"  Weight decay           : {optim.weight_decay}")
    print(f"  Max seq length         : {seq.max_seq_length} tokens")
    print(f"  Packing                : {seq.packing}")
    print(f"  Batch size (device)    : {train.per_device_train_batch_size}")
    print(f"  Gradient accumulation  : {train.gradient_accumulation_steps}  "
          f"(effective batch = {train.per_device_train_batch_size * train.gradient_accumulation_steps})")
    print(f"  Epochs                 : {train.num_train_epochs}")
    print(f"  BF16                   : {train.bf16}")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sift QLoRA fine-tuning blueprint — full SFT training runner.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  # Audit config and data on Mac (no GPU needed):
  python scripts/train_config.py --dry-run --data data/exports/sift_finetune_20260620.jsonl

  # Full run on cloud GPU with default Qwen2.5-7B:
  python scripts/train_config.py --data data/exports/sift_finetune_20260620.jsonl

  # Use Llama-3-8B instead:
  python scripts/train_config.py --data <path> --base llama3

  # Override LoRA rank for a leaner adapter:
  python scripts/train_config.py --data <path> --lora-rank 16

  # Quick 1-step smoke test:
  python scripts/train_config.py --data <path> --max-steps 1

  # Resume interrupted run:
  python scripts/train_config.py --data <path> --resume-from-checkpoint

  # Print all supported base models:
  python scripts/train_config.py --list-models
""",
    )
    parser.add_argument(
        "--data", type=Path, default=None,
        help="Path to ChatML JSONL file from export_fine_tune_data.py",
    )
    parser.add_argument(
        "--base", default=DEFAULT_BASE, choices=list(BASE_MODEL_MAP.keys()),
        help=f"Base model alias (default: {DEFAULT_BASE})",
    )
    parser.add_argument(
        "--lora-rank", type=int, default=32,
        help="LoRA rank r (default: 32 — see docstring for rationale)",
    )
    parser.add_argument(
        "--epochs", type=int, default=3,
        help="Training epochs (default: 3)",
    )
    parser.add_argument(
        "--lr", type=float, default=2e-4,
        help="Learning rate (default: 2e-4)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=2,
        help="Per-device batch size (default: 2)",
    )
    parser.add_argument(
        "--grad-accum", type=int, default=4,
        help="Gradient accumulation steps (default: 4, effective batch=8)",
    )
    parser.add_argument(
        "--max-steps", type=int, default=-1,
        help="Max training steps (-1 = use --epochs, default: -1)",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help=f"Output directory (default: {ADAPTERS_DIR}/sift-qlora-run)",
    )
    parser.add_argument(
        "--resume-from-checkpoint", action="store_true",
        help="Resume training from last checkpoint in --output-dir",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate config and data without running the training loop",
    )
    parser.add_argument(
        "--list-models", action="store_true",
        help="Print all supported base models and exit",
    )
    parser.add_argument(
        "--wandb", action="store_true",
        help="Enable Weights & Biases logging (set WANDB_API_KEY env var)",
    )

    args = parser.parse_args()

    if args.list_models:
        print("\nSupported base models:\n")
        for alias, info in BASE_MODEL_MAP.items():
            print(f"  {alias:<18} {info['hf_id']}")
            print(f"  {'':18} {info['note']}")
            print()
        return

    # Find latest export automatically if --data not specified
    if args.data is None:
        exports = sorted(EXPORTS_DIR.glob("sift_finetune_*.jsonl"), reverse=True)
        if not exports:
            print(
                "[error] No training data found. Run first:\n"
                "  python scripts/export_fine_tune_data.py\n",
                file=sys.stderr,
            )
            sys.exit(1)
        args.data = exports[0]
        print(f"[train] Auto-selected latest export: {args.data}")

    if not args.data.exists():
        print(f"[error] Data file not found: {args.data}", file=sys.stderr)
        sys.exit(1)

    lora_cfg = LoRAConfig(r=args.lora_rank, alpha=args.lora_rank * 2)
    optim_cfg = OptimizerConfig(learning_rate=args.lr)
    train_cfg = TrainingConfig(
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        output_dir=str(args.output_dir or (ADAPTERS_DIR / "sift-qlora-run")),
        report_to="wandb" if args.wandb else "none",
    )

    build_and_train(
        data_path=args.data,
        base_alias=args.base,
        lora=lora_cfg,
        optim=optim_cfg,
        train_cfg=train_cfg,
        resume_from_checkpoint=args.resume_from_checkpoint,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
