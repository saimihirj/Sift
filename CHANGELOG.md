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

## v0.4.0 — 2026-06-19

### Design System

- Premium loading screen: `SIFT.` wordmark with accent dot + animated sweep bar.
- New CSS token set: `--brain-accent`, `--brain-glow`, `--surface-glass` across all four themes (light / dark / dusk / neon).
- New keyframes: `sift-fade-up`, `sift-brain-pulse`, `sift-stream-cursor`, `sift-deck-border`.
- Full style blocks for `DeckUploadZone`, `DeckVisionBadge`, `SiftBrainPanel`, abort button, and streaming stats.

### Frontend

- **DeckUploadZone** [new component]: drag-and-drop zone with animated border, file preview, page count estimate, `DeckVisionBadge` (Vision ON / Text mode), upload progress, and validation.
- **EvaluatorScreen**: `DeckUploadZone` replaces the old inline attachment row for `deck_review` mode.
- **SiftBrainPanel** [new component]: live neural engine status badge, knowledge-graph domain cards with freshness, decision trace, TTFT/TPS metrics, and adapter registry.
- **RuntimeSidebar**: abort/stop button during streaming, TTFT + tokens/sec stats row, collapsible Sift Brain section.
- **LandingScreen**: conviction headline copy and neural pulse ticker that cycles through Sift Brain capabilities.
- **App.tsx** provider model presets updated to current open-source models:
  - Ollama: `qwen3:8b` (speed) / `qwen3:30b` (balanced)
  - Groq: `llama-4-scout-17b-16e-instruct` / `llama-4-maverick-17b-128e-instruct`
  - Cerebras: `qwen-3-8b` / `qwen-3-32b`
  - OpenAI: `gpt-4.1-mini` / `gpt-4.1`
  - Anthropic: `claude-haiku-4-5` / `claude-sonnet-4-5`
- `sift_brain` added as a first-class provider option pointing to port 8001.
- `sift_brain` added to `Provider` union type.
- Groq and Cerebras `supportsVisionModels` corrected to `false`.

### Backend

- **`backend/api/brain.py`** [new]: three endpoints — `/api/brain/status` (KB card counts, engine status, adapter info), `/api/brain/index-status` (ChromaDB), `/api/brain/decision-trace` (per-session trace).
- **`backend/main.py`**: registered `brain_router`; bumped API version to `0.4.0`.
- **`backend/api/chat.py`**: `ttft_ms` tracked on first delta; `ttftMs` and `tps` emitted in `done` SSE event.

### Repo

- Git remote corrected from `SignalX.git` → `Sift.git`.
- `render.yaml`: Groq model names updated to `llama-4-scout-17b-16e-instruct` / `llama-4-maverick-17b-128e-instruct`.
- `package.json` root + frontend bumped to `0.4.0`.
- `PLATFORM_OVERVIEW.md`: model defaults, local paths, and Open-Source config updated.

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
