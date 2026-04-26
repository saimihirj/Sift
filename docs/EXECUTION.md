# Execution Guide

This document is the accurate runbook for the current Sift app.

It covers:
- local setup
- local app mode
- local API-key mode
- LAN sharing
- development mode
- Docker deployment
- Render deployment
- runtime behavior
- troubleshooting

Sift supports two normal local paths:
- open-source local runtime through `Ollama`
- API-key runtime through providers like `Groq`, `Cerebras`, `OpenAI`, `OpenRouter`, `Anthropic`, and `Gemini`

If you want open-source-only with no paid services, use the local and LAN modes below and keep:

```env
SIFT_MODEL_PROVIDER=ollama
```

## 1. Prerequisites

Required:
- Python `3.11+`
- Node.js `18+`
- npm

Optional:
- [Ollama](https://ollama.com) for fully local open-source runtime

Recommended local models:

```bash
ollama pull llama3.2
ollama pull qwen3:8b
```

The local launcher auto-starts Ollama if it is needed and not already running.

## 2. One-Time Setup

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
npm --prefix frontend install
cp .env.example .env
```

## 3. Environment

Default runtime values live in `.env.example`.

Current keys:

```env
SIFT_EXPERT_DATA_DIR=knowledge_base/expert
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL_SPEED=llama3.2:latest
OLLAMA_MODEL_BALANCED=qwen3:8b
```

Notes:
- `speed` is the default chat profile
- `balanced` is optional and falls back to `speed` if it errors
- the bundled Expert corpus lives under `knowledge_base/expert`
- the rebuilt app uses Ollama over HTTP
- legacy Gradio config in `.env.example` is for the old prototype only

## 4. Run Modes

### Fastest paths

Use one of these after setup:

```bash
npm run mvp
```

For fully local open-source mode.

```bash
npm run mvp:api
```

For API-key mode without Ollama.

### A. Local App Mode

Best default for normal use.

```bash
python3 tools/sift_app.py --build
```

Shortcut:

```bash
npm run mvp
```

What it does:
- builds the frontend if needed
- serves frontend and backend on one port
- opens a browser window automatically
- stops 90 seconds after the browser heartbeat disappears by default

Default URL:

```text
http://127.0.0.1:7860
```

Useful flags:

```bash
python3 tools/sift_app.py --build --port 7870
python3 tools/sift_app.py --build --no-open
python3 tools/sift_app.py --build --idle-timeout 90
```

### B. LAN Test Mode

Use this to let another person test on the same Wi-Fi network.

```bash
python3 tools/sift_app.py --host 0.0.0.0 --port 7860 --build
```

Shortcut:

```bash
npm run mvp:lan
```

What to share:
- the LAN URL printed in the terminal

Notes:
- this is local-network sharing only
- there is no auth in this pass

### C. Local API-Key Mode

Use this when you want people to clone the repo and run it without installing Ollama.

```bash
npm run mvp:api
```

What it does:
- builds the frontend if needed
- serves frontend and backend on one port
- does not try to start local Ollama

How to use it:
- start the app with `npm run mvp:api`
- choose `Use API key` in the setup flow
- either paste a provider key in the UI or export one in your shell before launch

Example:

```bash
export GROQ_API_KEY=...
npm run mvp:api
```

Supported external providers:
- `groq`
- `cerebras`
- `openai`
- `openrouter`
- `anthropic`
- `gemini`

### D. Development Mode

Use this when you are editing code.

```bash
npm run dev
```

This starts:
- FastAPI at `http://127.0.0.1:8000`
- Vite at `http://127.0.0.1:5173`

You can also run them separately:

```bash
npm run dev:backend
```

```bash
npm run dev:frontend
```

Important:
- `npm run dev` is a normal dev workflow
- it does not auto-stop when you close the browser

### E. Docker

For container-style deployment:

```bash
docker build -t sift .
docker run -p 8000:8000 sift
```

App URL:

```text
http://127.0.0.1:8000
```

### F. Render

The repo includes:

```text
render.yaml
```

Recommended deploy path:

1. Create a new Render service from the repo
2. Use the included `render.yaml`
3. Set `GROQ_API_KEY`
4. Set `SIFT_SESSION_SECRET`
5. Set `SIFT_ADMIN_TOKEN`
6. Deploy

Important:
- the current blueprint uses a persistent disk
- app data is written under `/var/data/sift`
- the bundled Expert corpus is read from `/app/knowledge_base/expert`
- admin monitoring is available at `/admin`

If you want zero paid dependencies, skip this section and stay on local / LAN mode.

## 5. VC Firm Knowledge Cluster

Sift can build a dedicated `vc_firms` retrieval cluster from:

```text
knowledge_base/inbox/Investor.xlsx
knowledge_base/inbox/Investor Firm.xlsx
```

Default build command:

```bash
npm run knowledge:vc
```

Useful variants:

```bash
./.venv/bin/python scripts/build_vc_firm_cluster.py --max-firms 100
./.venv/bin/python scripts/build_vc_firm_cluster.py --firm sequoia --force-refresh
```

What it does:
- reads firm websites from `Investor.xlsx`
- ranks firms by mapped portfolio footprint from `Investor Firm.xlsx`
- crawls a few high-signal pages on each firm website
- stores a crawl cache under `data/vc_firms/cache/`
- indexes aggregated firm profiles into a dedicated `vc_firms` Chroma collection

This is an offline build step. It does not run on app startup.

## 6. Runtime Behavior

### Sessions

Sessions are stored in:

```text
data/sessions.db
```

Each session stores:
- founder profile
- current state snapshot
- full chat history
- response metadata

### Admin monitoring

The app now exposes:

```text
/admin
```

Open it directly with:

```bash
npm run admin
```

And backend routes:

```text
/api/admin/overview
/api/admin/events
```

If `SIFT_ADMIN_TOKEN` is set, the admin API requires the `x-admin-token` header.

### Uploads

Session-scoped uploads are stored in:

```text
data/session_uploads/
```

Files are:
- parsed once
- chunked per session
- retrieved as small relevant snippets

### Frontend Serving

In single-port mode and Docker mode, FastAPI serves the built frontend from:

```text
frontend/dist
```

If that build is missing, the root route returns a message telling you to build the frontend.

## 6. Product Flow

Typical local flow:

1. Start a session from onboarding
2. Chat in the mentor workspace
3. Upload notes, a deck, or a research file if needed
4. Resume older sessions from the left rail
5. Open the outline route when you want a structured pitch summary

## 7. Troubleshooting

### Ollama is not reachable

Sift normally starts Ollama for you. If it still cannot reach Ollama, check:

Check:
- `OLLAMA_BASE_URL`
- whether Ollama is already bound to another interface

### The balanced profile fails

Pull the configured model:

```bash
ollama pull qwen3:8b
```

If it is still unavailable, the app should fall back to `speed`.

### The browser closes but the server keeps running

That auto-stop behavior only applies to:

```bash
python3 tools/sift_app.py
```

It does not apply to:

```bash
npm run dev
uvicorn backend.main:app --reload
```

### Responses are too slow

Check:
- you are using `speed`
- Ollama is running locally
- the model matches `.env`
- you are not on the heavier `balanced` profile by default

Current default model choice is tuned for Apple Silicon local use:
- `speed` -> `llama3.2:latest`
- `balanced` -> `qwen3:8b`

### Frontend does not load in single-port mode

Build it explicitly:

```bash
npm --prefix frontend run build
```

Then restart:

```bash
python3 tools/sift_app.py --build
```

## 8. Key Commands

Setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
npm --prefix frontend install
```

Run local app:

```bash
python3 tools/sift_app.py --build
```

Run LAN share:

```bash
python3 tools/sift_app.py --host 0.0.0.0 --port 7860 --build
```

Run dev:

```bash
npm run dev
```

Build frontend:

```bash
npm --prefix frontend run build
```

Run Docker:

```bash
docker build -t sift .
docker run -p 8000:8000 sift
```
