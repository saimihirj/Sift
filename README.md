# SignalX

SignalX is a local-first startup and finance workbench with three workflows:
- `Ideate` for shaping rough ideas and reasoning
- `Evaluate` for structured pressure-testing and reports
- `Expert` for domain discussion, concept learning, pre-screening, and deck analysis

It is built to feel more like a sharp operator than a generic chatbot:
- it stays two-way instead of dumping generic advice
- it shows evidence and grounded reasoning in `Expert`
- it supports both open-source local runtime and API-key runtime
- it stores sessions locally so users can resume work
- it can turn an `Ideate` session into a refined pitch artifact

## Quick Start

### Clone-and-run with API keys

Best path if you want the easiest local setup and prefer providers like `Groq`, `Cerebras`, `OpenAI`, `OpenRouter`, `Anthropic`, or `Gemini`.

```bash
git clone <your-repo-url>
cd signalx
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
npm --prefix frontend install
cp .env.example .env
npm run mvp:api
```

Open `http://127.0.0.1:7860`, choose `Use API key`, then pick your provider.

### Run fully local with open-source models

If you want the app to stay local and avoid paid APIs, use the same setup steps above, then:

```bash
ollama pull llama3.2:latest
ollama pull qwen3:8b
npm run mvp
```

SignalX will auto-start Ollama if it is installed and not already running.

## What You Get

### Ideate
- open-ended discussion
- sharper framing of problem, customer, wedge, and pitch
- uploads and session resume
- refined pitch generation from the conversation

### Evaluate
- `Idea review` for adaptive pressure-testing of a startup idea
- `Deck review` for direct `.pdf` and `.pptx` pitch-deck assessment inside Evaluate
- structured reports with verdict, evidence gaps, weak claims, and next steps
- slide/page-aware feedback instead of a generic one-shot chatbot answer

### Expert
- concept explanations and comparisons
- evidence-backed answers using the bundled knowledge corpus
- pre-screening and deck analysis
- source, confidence, and analysis panels in the workbench

## Runtime Modes

### `npm run mvp`

Single-port local app with open-source models.

- serves frontend and backend together on `http://127.0.0.1:7860`
- auto-starts Ollama if needed
- good default for solo local use

### `npm run mvp:api`

Single-port local app without Ollama startup.

- serves frontend and backend together on `http://127.0.0.1:7860`
- optimized for API-key-based usage
- supports `groq`, `cerebras`, `openai`, `openrouter`, `anthropic`, and `gemini`

### `npm run mvp:lan`

LAN sharing for people on the same network.

### `npm run dev`

Frontend and backend split for active development.

- frontend: `http://127.0.0.1:5173`
- backend: `http://127.0.0.1:8000`

## Providers

### Open-source local
- `ollama`

### API-key providers
- `groq`
- `cerebras`
- `openai`
- `openrouter`
- `anthropic`
- `gemini`

API keys can be entered in the UI for a session or exported in the shell before launch.

Example:

```bash
export GROQ_API_KEY=...
npm run mvp:api
```

## Deck Review

`Evaluate` now has two modes:
- `Idea review`
- `Deck review`

`Deck review` is meant for serious pitch-deck feedback, not a prompt hack inside chat.

What it does:
- reads uploaded `.pdf` and `.pptx` decks into an ordered slide/page artifact
- evaluates the deck against the built-in rubric inside `Evaluate`
- reports what is working, what is weak, what is unproven, and what is still missing
- cites slide/page references where possible
- marks missing material as `not shown`, `unclear`, or `unverified` instead of guessing

Important runtime behavior:
- if the active model supports vision and the deck has renderable slide/page images, the review can assess slides more directly
- if the active model is text-only, SignalX runs a bounded transcript review from extracted deck text and explicitly avoids fake visual claims
- `Qwen2.5-VL` is the recommended local Ollama path for stronger deck review
- `Gemma 3` is a lighter local fallback when you want multimodal support on a smaller setup

If you update the deck or improve the review pipeline, re-run `Deck review` to generate a fresh report. Existing saved reports do not automatically rewrite themselves.

## Bundled Knowledge

The Expert workbench ships with a bundled JSON corpus under `knowledge_base/expert/`.

That means:
- clone-and-run does not depend on a private `/Users/.../Desktop/data` path
- `/api/health` reports whether the Expert corpus loaded
- local users and hosted deployments read from the same bundled source by default

## Project Layout

- `frontend/` - React + Vite UI
- `backend/` - FastAPI API and services
- `knowledge_base/expert/` - bundled Expert corpus
- `data/` - local runtime state, sessions, uploads, exports
- `memory.py` - SQLite persistence
- `signalx_app.py` - single-port launcher
- `docs/` - runbook, architecture, and deployment notes

## Deployment

For the current codebase, the cleanest first public deployment is `Render`.

Why:
- the app is a single long-running `React + FastAPI` service
- it uses SQLite and uploaded files on disk
- it expects same-origin frontend and API behavior
- the repo already includes `render.yaml` plus a deployment checklist

Use:
- [Execution Guide](docs/EXECUTION.md) for local and dev commands
- [Deployment Checklist](docs/DEPLOYMENT_CHECKLIST.md) for hosting

## Main Commands

```bash
npm run mvp
npm run mvp:api
npm run mvp:lan
npm run admin
npm run dev
npm run build
npm run knowledge:vc
```

## Current State

- `SignalX` is now a three-workflow MVP: `Ideate`, `Evaluate`, `Expert`
- both open-source and API-key runtime paths are supported
- the Expert corpus is bundled in the repo
- local API-key mode works without Ollama
- `Evaluate` supports both `Idea review` and structured `Deck review`
- long analytical answers auto-continue once when providers stop on length
- session history, uploads, and reports persist locally

## Docs

- [Execution Guide](docs/EXECUTION.md)
- [Deployment Checklist](docs/DEPLOYMENT_CHECKLIST.md)
- [Platform Overview](docs/PLATFORM_OVERVIEW.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Changelog](CHANGELOG.md)
