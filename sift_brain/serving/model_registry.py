"""Model adapter registry for Sift Brain serving.

Tracks all trained adapters with their metadata:
  - base model
  - LoRA rank / training run
  - domain coverage
  - eval scores
  - status (ready / training / failed)

Usage:
    from sift_brain.serving.model_registry import ModelRegistry
    registry = ModelRegistry.load()
    registry.register_adapter("data/model_adapters/sift-brain-v1", name="v1")
    best = registry.best_adapter()
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"
ADAPTERS_DIR = DATA_DIR / "model_adapters"
REGISTRY_PATH = DATA_DIR / "adapter_registry.json"


class ModelRegistry:
    """Registry of all Sift Brain adapter versions."""

    def __init__(self) -> None:
        self.adapters: dict[str, dict[str, Any]] = {}

    def register_adapter(
        self,
        adapter_path: str | Path,
        *,
        name: str | None = None,
        eval_scores: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Register or update an adapter entry."""
        path = Path(adapter_path)
        if not path.exists():
            raise FileNotFoundError(f"Adapter directory not found: {path}")

        # Load training metadata if available
        meta_path = path / "run_metadata.json"
        meta: dict[str, Any] = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())

        adapter_name = name or meta.get("adapter_name") or path.name
        entry = {
            "name": adapter_name,
            "path": str(path.resolve()),
            "base_model": meta.get("base_model", "unknown"),
            "lora_rank": meta.get("lora_rank"),
            "epochs": meta.get("epochs"),
            "train_loss": meta.get("train_loss"),
            "eval_scores": eval_scores or {},
            "status": "ready",
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
        self.adapters[adapter_name] = entry
        self.save()
        print(f"[registry] Registered adapter '{adapter_name}' from {path}")
        return entry

    def best_adapter(self, metric: str = "avg_overall_score") -> dict[str, Any] | None:
        """Return the adapter with the highest eval score, or the latest if no scores."""
        scored = [
            (a["eval_scores"].get(metric, 0.0), a)
            for a in self.adapters.values()
            if a.get("status") == "ready"
        ]
        if not scored:
            return None
        scored.sort(key=lambda x: x[0], reverse=True)
        # If nothing has eval scores, return the most recently registered
        if scored[0][0] == 0.0:
            by_date = sorted(
                self.adapters.values(),
                key=lambda a: a.get("registered_at", ""),
                reverse=True,
            )
            return by_date[0] if by_date else None
        return scored[0][1]

    def latest_adapter(self) -> dict[str, Any] | None:
        if not self.adapters:
            return None
        return sorted(
            self.adapters.values(),
            key=lambda a: a.get("registered_at", ""),
            reverse=True,
        )[0]

    def list_adapters(self) -> list[dict[str, Any]]:
        return sorted(
            self.adapters.values(),
            key=lambda a: a.get("registered_at", ""),
            reverse=True,
        )

    # ---- Auto-discover ----------------------------------------------------

    def discover(self) -> int:
        """Scan ADAPTERS_DIR and register any unregistered adapters."""
        if not ADAPTERS_DIR.exists():
            return 0
        new = 0
        for meta_file in ADAPTERS_DIR.glob("*/run_metadata.json"):
            adapter_path = meta_file.parent
            adapter_name = adapter_path.name
            if adapter_name not in self.adapters:
                try:
                    self.register_adapter(adapter_path)
                    new += 1
                except Exception as exc:
                    print(f"[registry] Could not register {adapter_path.name}: {exc}")
        return new

    # ---- Persistence -------------------------------------------------------

    def save(self, path: Path | None = None) -> None:
        target = path or REGISTRY_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"adapters": self.adapters}, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | None = None) -> "ModelRegistry":
        target = path or REGISTRY_PATH
        registry = cls()
        if not target.exists():
            # Auto-discover on first load
            registry.discover()
            return registry
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            registry.adapters = data.get("adapters", {})
        except Exception as exc:
            print(f"[registry] Could not load registry: {exc}")
        return registry

    def stats(self) -> dict[str, Any]:
        return {
            "total_adapters": len(self.adapters),
            "ready": sum(1 for a in self.adapters.values() if a.get("status") == "ready"),
            "adapters": [
                {"name": a["name"], "base_model": a["base_model"], "status": a["status"]}
                for a in self.list_adapters()
            ],
        }
