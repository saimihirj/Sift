# Sift Architecture

This document explains how Sift works today, how it should run for a shareable MVP, and what to monitor.

It is written for product and technical review.

## Product Goal

Sift is a domain workbench, not a generic chatbot.

The product should:
- help users clarify the real problem
- test assumptions with evidence
- stay grounded in customer discovery, finance, and operating reality
- adapt tone by role, geography, and workflow
- turn conversations into a refined pitch, evaluation report, or expert analysis

## Recommended MVP Stack

For the best current MVP deployment:

- `Frontend + API hosting`: Render web service
- `Database`: SQLite on persistent disk
- `File storage`: persistent disk
- `Auth`: optional OAuth later
- `Model inference`: Groq Llama-4 Scout/Maverick or another server-configured API provider in production, Ollama locally
- `Intelligence layer`: Sift Brain — dynamic knowledge graph + custom fine-tuned LLM (optional, local)
- `Monitoring`: Render metrics + logs, in-app usage tracking

## 1. Current Local Architecture

Use this for local development and private testing.

```mermaid
flowchart LR
    U["User Browser"] --> F["React Frontend (Vite)"]
    F --> A["FastAPI Backend"]
    A --> M["Ollama or API Provider"]
    A --> S["SQLite sessions.db"]
    A --> UPL["Local uploads folder"]
    A --> KB["Expert corpus"]
    A --> SB["Sift Brain (optional)"]
    SB --> KG["Knowledge Graph"]
    SB --> LLM["Fine-tuned Adapter"]
    A --> O["Refined pitch / expert analysis"]

    subgraph Local Ports
      F
      A
      M
      SB
    end
```

### Local runtime modes

#### Single-port local app

```text
Browser -> http://127.0.0.1:7860
```

This is started by:

```bash
python3 tools/sift_app.py --build
```

The backend serves the built frontend and API from one process.

#### Dev mode

```text
Frontend: http://127.0.0.1:5173
Backend:  http://127.0.0.1:8000
Ollama:   http://127.0.0.1:11434
```

This is started by:

```bash
npm run dev
```

## 2. Recommended MVP Production Architecture

This is the architecture recommended for sharing the current app with early testers.

```mermaid
flowchart LR
    B["User Browser"] --> R["Render Web Service\nReact build + FastAPI API"]
    R --> DB["Persistent Disk\nSQLite + uploads"]
    R --> G["Groq / Cerebras\nLlama-4 Scout / Maverick"]

    R --> LG["Render Logs / Metrics"]
```

### Why this shape

- one deployed service is simpler than splitting frontend and backend too early
- Render fits the current Dockerized FastAPI app well
- persistent disk keeps the current SQLite and upload model intact
- a server-configured Groq key removes the need for visitors to paste their own API keys
- Llama-4 Scout/Maverick on Groq gives fast open-weight inference at very low latency

> **GCP / Firebase**: the Cloud Run + Firestore + BigQuery deployment is archived in `legacy/gcp/`. See [legacy/gcp/README.md](legacy/gcp/README.md) to restore it.

## 3. Request Workflow

### Session start workflow

```mermaid
sequenceDiagram
    participant User
    participant UI as React UI
    participant API as FastAPI
    participant DB as Session Store

    User->>UI: complete onboarding
    UI->>API: POST /api/session/start
    API->>DB: create session row
    API-->>UI: opening message + chips + state
    UI-->>User: workbench opens
```

### Chat workflow

```mermaid
sequenceDiagram
    participant User
    participant UI as React UI
    participant API as FastAPI
    participant RET as Retrieval Layer
    participant MODEL as Groq / Ollama
    participant DB as Session Store

    User->>UI: send message or file
    UI->>API: POST /api/chat
    API->>RET: build retrieval context
    RET-->>API: expert cards + upload snippets + routing hints
    API->>MODEL: stream chat completion
    MODEL-->>API: streamed tokens
    API-->>UI: SSE events (meta, delta, done)
    API->>DB: persist user turn + assistant turn + metadata
    UI-->>User: updated chat, coverage, chips
```

### Upload workflow

```mermaid
sequenceDiagram
    participant User
    participant API as FastAPI
    participant ST as File Store
    participant RET as Retrieval Layer

    User->>API: upload PDF / DOCX / PPTX / TXT
    API->>ST: save source file
    API->>API: parse and chunk once
    API->>ST: save chunk manifest
    RET-->>API: top relevant snippets for later turns
```

### Refined pitch workflow

```mermaid
sequenceDiagram
    participant User
    participant UI as React UI
    participant API as FastAPI
    participant DB as Session Store
    participant MODEL as Groq / Ollama

    User->>UI: open refined pitch
    UI->>API: POST /api/outline
    API->>DB: load full transcript
    API->>MODEL: generate refined pitch draft
    API-->>UI: markdown refined pitch
```

## 4. Core App Modules

### Frontend

- `frontend/src/app/App.tsx`
- `frontend/src/features/onboarding/LandingScreen.tsx`
- `frontend/src/features/onboarding/SetupWizard.tsx`
- `frontend/src/features/chat/ChatScreen.tsx`
- `frontend/src/features/evaluator/EvaluatorScreen.tsx`
- `frontend/src/features/evaluator/EvaluatorReportScreen.tsx`
- `frontend/src/features/outline/OutlineScreen.tsx`

Responsibilities:
- onboarding
- session resume
- ideate shell
- evaluate shell
- expert shell
- streaming response rendering
- refined pitch view
- heartbeat for local auto-stop

### Backend API

- `backend/main.py`
- `backend/api/session.py`
- `backend/api/chat.py`
- `backend/api/outline.py`
- `backend/api/client.py`

Responsibilities:
- session start and load
- streaming chat events
- outline generation
- heartbeat handling
- frontend asset serving in single-port mode

### Backend services

- `backend/services/prompting.py`
- `backend/services/retrieval.py`
- `backend/services/expert_knowledge.py`
- `backend/services/expert_agent.py`
- `backend/services/model_router.py`
- `backend/services/state_engine.py`
- `backend/services/uploads.py`

Responsibilities:
- workflow behavior rules
- compact retrieval context
- expert corpus loading and routing
- model routing and fallback
- deterministic state updates
- upload parsing and snippet retrieval

### Persistence

Current local storage:
- `backend/core/memory.py` -> SQLite at `data/sessions.db`
- `backend/services/uploads.py` -> `data/session_uploads/`

Recommended production storage:
- persistent disk for MVP
- optional managed database and object storage later

## 5. Ports And Endpoints To Monitor

### Local ports

| Port | Service | Why it matters |
|---|---|---|
| `7860` | single-port local app | normal local testing |
| `8000` | FastAPI backend | API health and backend debugging |
| `5173` | Vite frontend | frontend dev only |
| `11434` | Ollama | local model runtime |

### Local endpoints

| Endpoint | Purpose |
|---|---|
| `/api/health` | health check |
| `/api/session/start` | session creation |
| `/api/session` | list user sessions |
| `/api/chat` | streamed chat |
| `/api/outline` | outline generation |
| `/api/client/heartbeat` | local app browser heartbeat |

### Production ports

In production, users should access only HTTPS:

```text
https://your-domain.com
```

Internally:
- Render container listens on port `8000`
- Groq and other API providers are external managed services

## 6. What To Monitor

### Render

Monitor:
- request volume
- error rate
- p95 latency
- memory usage
- container restarts
- deploy success/failure

Where:
- Render service logs
- Render service metrics

### Model provider

Monitor:
- response latency
- timeout rate
- quota / credit usage
- model errors

Where:
- Groq console

### In-app product analytics

You should track these yourself in the database:

- who signed in
- who opened the app
- who started a session
- who resumed a session
- who uploaded a file
- how many turns each session had
- first token latency
- total response latency
- which response profile was used
- whether fallback happened
- whether the outline was opened

This matters more than generic pageview analytics because this is a workflow product.

## 7. Web Analytics Recommendation

For MVP, separate analytics into two layers.

### Product analytics

Best for admin understanding:
- user identity
- session usage
- feature usage
- upload behavior
- mentor latency

This should live inside your app database.

### Traffic analytics

Best for traffic patterns:
- unique visitors
- countries / cities
- devices
- page load performance

If you later move the frontend to Vercel, Vercel Web Analytics is useful for this layer.

For the current recommended MVP stack, traffic analytics are optional. Product analytics are the priority.

## 8. Recommended Admin View

For your admin perspective, build a simple internal dashboard that shows:

- signed-in users
- sessions per user
- active sessions this week
- average turns per session
- uploads per session
- outline opens
- model profile usage
- response latency trends
- error counts

Suggested sections:

1. `Users`
2. `Sessions`
3. `Uploads`
4. `Latency`
5. `Errors`

## 9. Suggested Environment Split

### Local open-source

- Ollama
- SQLite
- local uploads
- `python3 tools/sift_app.py --build`

### Local API-key mode

- Groq, Cerebras, OpenAI, OpenRouter, Anthropic, or Gemini
- SQLite
- local uploads
- `python3 tools/sift_app.py --build --no-ollama`

### MVP / staging

- Render
- persistent disk
- Groq
- optional invite-only auth

### Later production

- optional Vercel frontend
- Render or another container host for API
- optional managed database/object storage
- stronger analytics and alerting

## 10. Short Summary

Today:
- local-first app
- React + FastAPI
- Ollama or API providers (Groq Llama-4 as hosted default)
- SQLite
- local upload storage
- dynamic knowledge graph + ChromaDB (`sift_brain/`)
- custom LLM fine-tuning + serving pipeline (`sift_brain/training/`, `sift_brain/serving/`)

Best MVP deployment:
- Render web service
- persistent disk for SQLite and uploads
- Groq Llama-4 inference
- internal product analytics

Main technical reason:
- your current app needs a real backend process and persistent storage, so full-stack Vercel is the wrong fit right now.
