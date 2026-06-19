# Changelog

## v0.3.0 — 2026-06-19

### Cleanup

- Archived Firebase/GCP deployment files to `legacy/gcp/` — app is now localhost-first with Render as recommended shared deployment.
- Split GCP Python dependencies into `requirements-gcp.txt` (no longer installed by default).
- Hardened `SIFT_PERSISTENCE_BACKEND=sqlite` as the true default — Firestore/BigQuery only active when explicitly enabled.
- Removed `gradio` from core requirements (legacy Gradio prototype fully replaced by React).
- Updated `package.json` to v0.3.0 and replaced legacy `run:sift` aliases with `brain:*` scripts.

### Model Defaults

- Ollama: speed → `qwen3:8b` · balanced → `qwen3:30b` (was `llama3.2` / `qwen3:8b`).
- Groq: `llama-4-scout-17b-16e-instruct` / `llama-4-maverick-17b-128e-instruct` (Llama 4 generation).
- Cerebras: `qwen-3-8b` / `qwen-3-32b`.
- Anthropic: `claude-haiku-4-5` / `claude-sonnet-4-5`.
- OpenAI: `gpt-4.1-mini` / `gpt-4.1`.
- OpenRouter: `meta-llama/llama-4-scout` / `meta-llama/llama-4-maverick`.

### Added — Sift Brain Intelligence Layer

- `sift_brain/knowledge_graph/` — async domain updater, ChromaDB embedder, entity-relationship graph, and hybrid retriever.
- `sift_brain/decision_layer/` — intelligent query router and context builder for the platform.
- `sift_brain/training/` — dataset builder, LoRA/QLoRA fine-tuner (peft + trl), hyperparameter tuner (Optuna), and model evaluator.
- `sift_brain/serving/` — OpenAI-compatible local serving server for fine-tuned adapters + model registry.
- `scripts/update_knowledge_graph.py` — CLI to update domain knowledge.
- `scripts/train_sift_brain.py` — end-to-end training launcher.
- `scripts/serve_sift_brain.py` — local model serving launcher.
- `requirements-brain.txt` — optional brain layer dependencies.
- `sift_brain` provider entry in `model_router.py` — routes to local custom model server on port 8001.

### Documentation

- `README.md` — full rewrite: localhost-first, Sift Brain section, updated model defaults, no Firebase URLs.
- `docs/ARCHITECTURE.md` — Sift Brain added to component diagrams, Render as primary production target.
- `docs/PLATFORM_OVERVIEW.md` — updated stack section, Sift Brain in architecture overview.

## Unreleased

### Upgraded

- Runtime catalog now marks server-configured provider keys so public users can run hosted providers without pasting their own API key.
- Fast hosted open-weight defaults now prioritize GPT-OSS on Groq/Cerebras.
- Local Ollama defaults now start on `qwen3:8b`, with `qwen3:30b` as the sharper local option.
- OpenAI defaults now expose `gpt-5.4-mini` for fast mode and `gpt-5.5` for sharper frontier mode.
- Setup and runtime panels now show provider readiness, latency intent, model presets, and end-to-end response timing.

## v0.2.0 - 2026-03-06

Adaptive evaluator release for `Sift`.

### Added

- Evaluator mode alongside the existing mentor chat flow.
- Bounded adaptive assessments with `10`, `15`, or `20` question budgets.
- Hybrid answer scoring across comprehension, logic, evidence, quantification, and clarity.
- Final evaluator report with success score, why the score landed there, and concrete fixes.
- Session-scoped provider, model, and API-key support for local and external inference providers.
- Single-page website ingestion as an evaluator input source.
- Evaluator-specific admin metrics for starts, completions, scores, provider mix, and fetch failures.

### Kept intact

- Existing mentor chat flow and session resume behavior.
- Local-first Ollama runtime as the default open-source path.
- Outline route, admin dashboard, and one-command local launcher.

## v0.1.0 - 2026-03-06

Initial private MVP snapshot of `Sift`.

### Included

- React + FastAPI app shell replacing the Gradio-first prototype as the primary user experience.
- Local-first chat workflow with Ollama-backed model routing and streamed responses.
- Compact onboarding flow, landing screen, session history, resume flow, and exit session controls.
- Separate outline route for transcript-to-outline generation.
- Admin dashboard for usage and latency monitoring.
- Monochrome responsive UI for desktop, tablet, and mobile.
- Local launcher with `tools/sift_app.py`.
- Architecture, execution, and platform overview docs in `docs/`.

### Runtime defaults

- Provider: `ollama`
- Speed profile: `llama3.2:latest`
- Balanced profile: `qwen3:8b`

### Known constraints

- Local MVP mode stores state in SQLite and local disk.
- Google and Apple sign-in are not wired yet.
- GitHub deployment automation is not part of this snapshot.
