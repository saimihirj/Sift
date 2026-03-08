# Signal

Signal is a local-first pitch mentor and adaptive idea evaluator for founders, student innovators, and early teams.

It is built to behave more like a sharp human mentor than a generic chatbot:
- it pushes on problem clarity, customer understanding, validation, and reasoning
- it keeps the conversation simple when the founder is early or non-technical
- it can switch between open mentoring and structured evaluation
- it stores sessions locally so founders can come back and continue

The current product is a `React + FastAPI` web app with local-first runtime support.

## What The Tool Does

### Mentor mode
- conversational founder coaching
- short, VC-style questioning without turning into a lecture
- session resume, file context, and outline generation

### Evaluator mode
- adaptive questioning based on prior responses
- handles both short and long answers more naturally
- keeps scoring hidden during the conversation
- generates a final report with score, why, and fixes only at the end

### Runtime options
- local open-source mode through Ollama
- external provider mode with session-scoped API keys
- live provider/model switching inside a session
- optional offline VC-firm knowledge cluster built from `knowledge_inbox/Investor.xlsx` and `knowledge_inbox/Investor Firm.xlsx`

## Local Use

### 1. One-time setup

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
npm --prefix frontend install
cp .env.example .env
```

### 2. Choose your runtime

In normal local MVP mode, the launcher now starts local Ollama automatically if it is needed and not already running.

If you want to use an external provider, you can still skip Ollama entirely and choose `Use API key` in the UI instead.

### 3. Run the app

```bash
npm run mvp
```

Open:

```text
http://127.0.0.1:7860
```

## Main Commands

Run the normal local app:

```bash
npm run mvp
```

Run the app for LAN sharing:

```bash
npm run mvp:lan
```

Run the app with admin enabled:

```bash
npm run admin
```

Run backend + frontend separately in development:

```bash
npm run dev
```

Build the VC firm knowledge cluster from the spreadsheet inputs:

```bash
npm run knowledge:vc
```

Useful variants:

```bash
./.venv/bin/python scripts/build_vc_firm_cluster.py --max-firms 100
./.venv/bin/python scripts/build_vc_firm_cluster.py --firm sequoia --force-refresh
```

Direct launcher:

```bash
python3 signal_app.py --build
```

The old launcher name still works for compatibility:

```bash
python3 vk.py --build
```

## How It Works

### Frontend
- Vite + React + TypeScript
- fixed-height, single-screen UI
- hideable session sidebar
- runtime switcher for provider/model changes

### Backend
- FastAPI
- SQLite session persistence
- session-scoped uploads and retrieval
- deterministic evaluator scoring during live conversation
- final evaluator report generation

### Data and storage
- sessions: `data/sessions.db`
- uploads: `data/session_uploads/`
- exports: `data/exports/`
- VC firm crawl cache: `data/vc_firms/cache/`
- VC firm ingest manifest: `data/vc_firms/manifest.json`

## Models

Default local open-source path:
- provider: `ollama`
- speed model: `llama3.2:latest`
- balanced model: `qwen3:8b`

Supported external providers in the current runtime layer:
- `cerebras`
- `groq`
- `openai`
- `openrouter`
- `anthropic`
- `gemini`

For external providers, API keys are session-scoped in the browser and are not persisted in the database.

## Project Layout

- `frontend/` — React app
- `backend/` — FastAPI APIs and services
- `memory.py` — SQLite session and analytics persistence
- `signal_app.py` — primary single-process launcher
- `vk.py` — compatibility wrapper for the old launcher name
- `docs/` — architecture, execution, and platform notes

## Current State

- active product name: `Signal`
- local-first MVP is fully runnable without paid services
- admin is exposed only in admin launch mode
- mentor and evaluator both support resumed sessions

## Docs

- [Architecture](docs/ARCHITECTURE.md)
- [Execution Guide](docs/EXECUTION.md)
- [Platform Overview](docs/PLATFORM_OVERVIEW.md)
- [Changelog](CHANGELOG.md)
