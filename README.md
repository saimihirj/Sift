# Sift

Sift is an AI workbench for startup ideation, pitch deck review, and investor-style evaluation.

It gives founders, operators, students, and analysts one focused workspace to turn rough startup material into clearer thinking: a sharper pitch, a structured evaluation, and a practical next-actions report.

## What Sift Does

Sift is organized around three workflows.

`Ideate` helps shape an early idea into a clearer company narrative. It asks targeted questions, tracks pitch coverage, and helps produce a refined founder-ready articulation.

`Evaluate` reviews a startup idea or pitch deck. It returns a structured verdict, score, confidence level, strengths, risks, missing evidence, and suggested next steps.

`Expert` answers startup, market, and venture-style questions with a bundled expert corpus and retrieved context. It is useful for concept breakdowns, risk mapping, deck pre-screening, and investor memo-style thinking.

## Current Stack

Sift runs **localhost-first**. No cloud services required.

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript (Vite) |
| Backend | FastAPI + Uvicorn |
| Persistence | SQLite (`data/sessions.db`) |
| File storage | Local disk (`data/session_uploads/`) |
| Knowledge base | Bundled expert corpus + dynamic knowledge graph |
| Model inference | Ollama (local) or any API-key provider |

For shared access, the recommended production path is **Render** with a persistent disk (SQLite + uploads intact, no cloud DB migration needed).

## Model Options

Sift supports both local and hosted model paths.

**Local open-source (default):**

- Ollama — `qwen3:8b` (speed) · `qwen3:30b` (balanced) · `qwen2.5vl:7b` (deck review)
- Local OpenAI-compatible server — vLLM, Hugging Face TGI, LM Studio, llama.cpp
- Sift Brain — custom fine-tuned decision layer (see below)

**Hosted providers:**

- Groq — `llama-4-scout` (fast) · `llama-4-maverick` (balanced)
- Cerebras — `qwen-3-8b` (fast) · `qwen-3-32b` (balanced)
- OpenAI — `gpt-4.1-mini` / `gpt-4.1`
- Anthropic — `claude-haiku-4-5` / `claude-sonnet-4-5`
- OpenRouter — any open-weight or frontier model
- Gemini API — `gemini-2.0-flash` / `gemini-2.5-flash`

**Archived (optional GCP path):**

- Vertex AI Gemini — available via `requirements-gcp.txt` and `legacy/gcp/`

## Deck Review

Deck review is part of `Evaluate`.

It can:

- ingest `.pdf` and `.pptx` pitch decks
- extract ordered slide or page content
- score the deck against startup pitch criteria
- produce slide-by-slide notes
- identify strengths, risks, missing proof, and unclear claims
- produce an investor-style report without pretending missing evidence exists

PDF review can use page images when the selected model supports vision. PPTX review relies mostly on extracted slide text.

## Sift Brain — Knowledge Graph & Custom LLM

Sift includes a `sift_brain/` intelligence layer with two parts.

### Dynamic Knowledge Graph

The knowledge graph continuously updates the expert corpus across all targeted domains:

- SaaS, D2C, Fintech, India VC, PE/Growth, Macro, Regulation, Market Sizing, Unit Economics, PMF

Run a domain update:

```bash
npm run brain:update
# or: python3 scripts/update_knowledge_graph.py [--domain all|saas|fintech|...]
```

This runs an async scraper → ChromaDB embedder pipeline that adds new knowledge cards incrementally to `knowledge_base/expert/` and `data/chroma/`.

### Custom LLM — Fine-tuning & Serving

Build and serve a Sift-specific decision layer on top of the best open-source base models:

```bash
# Build a fine-tuned adapter (LoRA/QLoRA)
npm run brain:train
# or: python3 scripts/train_sift_brain.py --base qwen3-8b --epochs 3 --lora-rank 16

# Serve it locally (OpenAI-compatible on port 8001)
npm run brain:serve
# or: python3 scripts/serve_sift_brain.py --adapter latest
```

The serving server exposes an OpenAI-compatible `/v1/chat/completions` endpoint. Point `LOCAL_OPENAI_BASE_URL=http://127.0.0.1:8001/v1` in `.env` to use it, or set `SIFT_MODEL_PROVIDER=sift_brain`.

Fine-tuning config is YAML-based and supports hyperparameter sweeps via Optuna.

## OAuth

The app has OAuth routes for:

- Google
- Apple
- LinkedIn
- X

OAuth providers only appear when their client ID and secret are set in the environment.

Local callback URLs:

```text
http://127.0.0.1:7860/api/auth/callback/google
http://127.0.0.1:7860/api/auth/callback/apple
http://127.0.0.1:7860/api/auth/callback/linkedin
http://127.0.0.1:7860/api/auth/callback/x
```

Dev split-stack callback URLs use port `8000` for the backend.

## Local Setup

```bash
git clone git@github.com:saimihirj/Sift.git
cd Sift

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

npm install
npm --prefix frontend install
cp .env.example .env
```

Run with local Ollama (default):

```bash
ollama pull qwen3:8b
npm run mvp
```

Run with API-key providers only:

```bash
npm run mvp:api
```

Open:

```text
http://127.0.0.1:7860
```

Development split stack:

```bash
npm run dev
```

Frontend: `http://127.0.0.1:5173` · Backend: `http://127.0.0.1:8000`

## Common Commands

```bash
npm run mvp            # single-port local app with Ollama
npm run mvp:api        # single-port local app for API-key providers
npm run mvp:lan        # share on the local network
npm run admin          # launch with admin mode
npm run dev            # run backend and frontend separately
npm run build          # build the frontend only
npm run brain:update   # update the knowledge graph
npm run brain:train    # fine-tune the Sift Brain model
npm run brain:serve    # serve the Sift Brain local model
python3 -m pytest      # run backend tests
```

## Fresh Data Reset

Reset local runtime data:

```bash
python3 tools/reset_runtime_data.py --local --yes
```

## Project Structure

```text
backend/
  api/          FastAPI route handlers
  core/         persistence, analytics, knowledge, and shared runtime state
  services/     evaluation, deck review, uploads, retrieval, auth, and model routing

frontend/
  src/          React application source
  index.html    Vite entrypoint

knowledge_base/
  expert/       bundled Expert knowledge corpus (static + dynamic shards)
  inbox/        source files for offline knowledge builds

sift_brain/
  knowledge_graph/   dynamic domain updater, ChromaDB embedder, entity graph, retriever
  decision_layer/    intelligent query router and context builder
  training/          dataset builder, LoRA/QLoRA fine-tuner, hypertuner, evaluator
  serving/           OpenAI-compatible local model server and adapter registry

scripts/        knowledge graph update, training, and serving launchers
tools/          local app launcher and reset scripts
docs/           architecture, execution, and platform notes
tests/          backend tests
data/           local runtime state (SQLite, uploads, chroma, model adapters) — not in git
legacy/gcp/     archived Google Cloud / Firebase deployment files
```

## Optional: Google Cloud Deployment

The Firebase/GCP deployment path is archived in `legacy/gcp/`. To restore it:

1. `pip install -r requirements-gcp.txt`
2. Copy files from `legacy/gcp/` back to project root and `tools/` and `docs/`
3. Set GCP environment variables in `.env`

## Verification Status

Latest local verification:

```text
python3 -m pytest
27 passed

npm --prefix frontend run build
passed
```

## Notes For Operators

- Keep `.env`, local caches, `frontend/dist`, and `data/` out of git.
- Keep OAuth and model provider secrets in environment variables or a secrets manager.
- For the best public demo experience, deploy to **Render** with a persistent disk.
- For open-source inference, point `LOCAL_OPENAI_BASE_URL` at a vLLM/TGI/llama.cpp endpoint, or use Ollama locally.
- For the Sift Brain custom model, start `scripts/serve_sift_brain.py` before the main app.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Platform Overview](docs/PLATFORM_OVERVIEW.md)
- [Execution Guide](docs/EXECUTION.md)
- [Beta Readiness](docs/BETA_READINESS.md)
- [Changelog](CHANGELOG.md)
- [GCP Deployment (archived)](legacy/gcp/README.md)
