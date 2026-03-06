# Vishwakarma (VK)

Vishwakarma is a local-first pitch deck mentor for founders and student innovators.

The current product is a `React + FastAPI + Ollama` app with:
- a fixed-height chat workspace
- streamed mentoring responses
- saved sessions and resume flow
- a dedicated outline view
- session-scoped file parsing and retrieval
- an internal admin route at `/admin` for usage and latency monitoring

The old `app.py` Gradio prototype is still in the repo as legacy reference, but it is not the main app surface.

This repo can now run as an open-source-only MVP with no paid services.

Release notes:
- [`v0.1.0` changelog](CHANGELOG.md)

## Quick Start

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
npm --prefix frontend install
cp .env.example .env
python3 vk.py --build
```

If Ollama is not running:

```bash
ollama serve
```

Open:
- `http://127.0.0.1:7860`

## Open-Source-Only MVP Commands

Normal MVP app:

```bash
npm run mvp
```

LAN share with a co-founder on the same network:

```bash
npm run mvp:lan
```

Open directly into admin:

```bash
npm run admin
```

## Run Modes

### Local app

```bash
python3 vk.py --build
```

Single port, opens in browser, and auto-stops shortly after the browser closes.

### LAN test with a co-founder

```bash
python3 vk.py --host 0.0.0.0 --port 7860 --build
```

### Development mode

```bash
npm run dev
```

This runs:
- FastAPI on `http://127.0.0.1:8000`
- Vite on `http://127.0.0.1:5173`

### Docker

```bash
docker build -t vishwakarma .
docker run -p 8000:8000 vishwakarma
```

### Render blueprint

```text
render.yaml
```

The repo now includes a Render service blueprint for a Groq-backed MVP deploy with a persistent disk.

## Docs

- Platform overview: `docs/PLATFORM_OVERVIEW.md`
- Execution guide: `docs/EXECUTION.md`
- Architecture guide: `docs/ARCHITECTURE.md`

## Key Files

- `backend/main.py` - FastAPI entrypoint and frontend serving
- `backend/api/` - session, chat, outline, and heartbeat APIs
- `backend/services/prompting.py` - mentor behavior, chip logic, compact prompt rules
- `backend/services/model_router.py` - Ollama profiles and fallback
- `backend/api/admin.py` - admin metrics and recent activity
- `backend/api/analytics.py` - event capture for monitoring
- `frontend/src/` - React app shell, onboarding, chat, outline, styling
- `memory.py` - SQLite session persistence and JSONL export
- `vk.py` - single-process local launcher

## Current Defaults

- default profile: `speed`
- default local model: `llama3.2:latest`
- optional balanced model: `qwen3:4b`
- persistence: `data/sessions.db`
- uploads: `data/session_uploads/`
- runtime mode: `VK_MODEL_PROVIDER=ollama`

## Product Direction

Vishwakarma is not meant to behave like a generic chatbot.

It should:
- clarify the real problem
- test assumptions with evidence
- stay grounded in customer discovery and early validation
- explain jargon simply when needed
- end wrap-up turns with concrete next steps
