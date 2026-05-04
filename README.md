# Sift

Sift is a startup evaluation workbench for shaping ideas, reviewing pitch decks, and pressure-testing early companies with structured AI feedback.

It is designed for founders, students, operators, and analysts who want more than a generic chatbot. Sift keeps the work organized across three focused workflows:

- `Ideate`: shape a rough idea into a clearer pitch story.
- `Evaluate`: score an idea or review a pitch deck with evidence-based feedback.
- `Expert`: ask domain questions, compare startup concepts, and pre-screen opportunities with retrieved context.

For controlled beta testing, Sift uses a lightweight workspace key instead of full authentication. A tester enters their name, email or handle, and Sift key; the same email/handle and key pair resumes only that tester's sessions.

## What Sift Can Do

### Ideate

- Holds a focused two-way conversation about the startup.
- Tracks pitch coverage across problem, solution, market, business model, traction, team, and ask.
- Supports uploads, session history, and a refined pitch artifact.

### Evaluate

- Runs adaptive idea reviews with a score, verdict, confidence, weak spots, and suggested fixes.
- Accepts a startup website URL as evaluation context.
- Supports direct pitch deck review for `.pdf` and `.pptx` uploads.
- Produces structured reports instead of one-off chat responses.

### Deck Review

Deck review is a first-class mode inside `Evaluate`.

It can:

- Parse uploaded pitch decks into ordered slide or page artifacts.
- Score the deck against built-in startup pitch criteria.
- Flag what is working, what is weak, what is unproven, and what is missing.
- Give slide-by-slide notes and top fixes.
- Cite slide or page references when available.
- Mark missing claims as `not shown`, `unclear`, or `unverified` instead of guessing.

PDF reviews can use slide images when the selected model supports vision and page rendering is available. PPTX reviews currently rely mostly on extracted slide text, so visual design feedback is treated as unverified.

### Expert

- Answers startup and finance questions using the bundled knowledge base.
- Shows source and confidence context where available.
- Helps with concept explanations, framework comparisons, deck pre-screening, and investor-style analysis.

## Quick Start

### 1. Install dependencies

```bash
git clone <your-repo-url>
cd sift
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
npm --prefix frontend install
cp .env.example .env
```

### 2. Run with API providers

Use this path if you want to use Groq, Cerebras, OpenAI, OpenRouter, Anthropic, or Gemini.

```bash
npm run mvp:api
```

Open:

```text
http://127.0.0.1:7860
```

You can enter an API key in the UI for a session, or set one in your shell before launch:

```bash
export GROQ_API_KEY=...
npm run mvp:api
```

### 3. Run fully local with Ollama

Install Ollama, pull a model, then launch Sift:

```bash
ollama pull llama3.2
npm run mvp
```

Optional stronger local model:

```bash
ollama pull qwen3:8b
```

Sift will try to start Ollama automatically when running in local model mode.
For Hugging Face/open-source models served through vLLM, TGI, LM Studio, or llama.cpp, set `SIFT_MODEL_PROVIDER=local_openai` and point `LOCAL_OPENAI_BASE_URL` at that server.

Generated workspace keys are compact `SF...` keys. New keys store a short hashed workspace id instead of repeating the user's email/handle and raw key in session and analytics records; older `SIFT-...` keys still open their existing sessions.

## Main Commands

```bash
npm run mvp        # single-port local app with Ollama support
npm run mvp:api    # single-port local app for API-key providers
npm run mvp:lan    # share on the local network
npm run admin      # open the admin view
npm run dev        # run backend and frontend separately
npm run build      # build the frontend
npm run knowledge:vc
```

Development mode uses:

- Frontend: `http://127.0.0.1:5173`
- Backend: `http://127.0.0.1:8000`

## Providers

Local:

- `ollama`
- `local_openai`

Hosted:

- `groq`
- `cerebras`
- `openai`
- `openrouter`
- `anthropic`
- `gemini`
- `vertex`

Server-side provider keys can be configured for hosted demos so visitors do not need to bring their own key.

## Project Structure

```text
backend/
  api/          FastAPI route handlers
  core/         shared state, prompts, knowledge, RAG, and SQLite persistence
  services/     evaluator, deck review, uploads, model routing, retrieval

frontend/
  src/          React application source
  index.html    Vite entrypoint

knowledge_base/
  expert/       bundled Expert knowledge corpus
  inbox/        source files for offline knowledge builds

tools/          local launch and operator scripts
legacy/         archived Gradio prototype
docs/           architecture, execution, and deployment notes
tests/          backend tests
data/           local runtime state, uploads, and generated indexes
```

The root directory is kept intentionally small: configuration, documentation, deployment files, and top-level package metadata.

## Persistence

Sift is local-first by default.

- Sessions and analytics are stored in SQLite under `data/`.
- Session access is scoped by the beta Sift key supplied at entry.
- Uploads are stored on local disk under `data/session_uploads/`.
- Generated retrieval indexes are stored under `data/`.

Do not commit the `data/` directory from a local development machine.

## Deployment

The full app is best deployed as a long-running Python service because the backend serves both the API and the built frontend.

Recommended full-stack path:

- Render or another long-running Python host.
- Persistent disk for SQLite and uploads.
- Server-side provider keys for public demos.

Google Cloud serverless deployment is now supported with Cloud Run, Firestore,
Cloud Storage, and BigQuery. See
[Google Cloud Serverless Deployment](docs/GCP_SERVERLESS_DEPLOYMENT.md).

Frontend-only Vercel deployment is also supported when paired with a hosted backend:

- `vercel.json` builds `frontend/`.
- Set `VITE_API_BASE_URL` to the hosted backend URL.
- Set `SIFT_CORS_ORIGINS` on the backend to the Vercel app URL.

See [Deployment Checklist](docs/DEPLOYMENT_CHECKLIST.md) for details.

## Documentation

- [Execution Guide](docs/EXECUTION.md)
- [Deployment Checklist](docs/DEPLOYMENT_CHECKLIST.md)
- [Beta Readiness Checklist](docs/BETA_READINESS.md)
- [Platform Overview](docs/PLATFORM_OVERVIEW.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Changelog](CHANGELOG.md)

## Current Status

Sift is an MVP with the main product flows wired end to end:

- Ideation workspace
- Adaptive idea evaluator
- Structured deck reviewer
- Expert workbench
- Local session history
- Upload parsing and retrieval
- Local and hosted model providers
- Admin analytics view

The project is still evolving. The most important current limitation is that website evaluation uses single-page context, not a full crawler or diligence engine.
