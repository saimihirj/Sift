# Sift

Bring your startup. We'll tell you the truth.

Sift is a universal startup validator. It ingests pitch decks, website URLs, or raw ideas and generates a structured readiness score, an investor-grade teardown, and an interactive Co-Pilot to fix the identified issues.

Built on an ultra-minimalist, brutalist black-and-white design system, Sift strips away the noise to focus entirely on actionable feedback and refinement.

## Features

- **Universal Ingestion**: Drag and drop a `.pdf` or `.pptx` deck, paste a website or GitHub URL, or just type out your idea.
- **The Scorecard**: Get a 0-100 Readiness Score alongside a prioritized list of critical risks and warnings.
- **Sift Co-Pilot**: Drop into a streaming chat interface to work through the findings. Sift automatically generates a polished slide outline as you chat.
- **BYO-Key Support**: Use Sift's default local inference, or supply your own API key.

## Architecture

Sift is a lightweight React frontend backed by a Python FastAPI intelligence layer.

| Layer | Stack |
|---|---|
| **Frontend** | React, TypeScript, Vite, Vanilla CSS |
| **Backend** | FastAPI, Uvicorn, SQLite |
| **Model Router**| Groq, Anthropic, OpenAI, Cerebras, OpenRouter, Gemini, Ollama |
| **Local RAG** | ChromaDB, SentenceTransformers |

## Quick Start (Local Development)

```bash
git clone git@github.com:saimihirj/Sift.git
cd Sift

# 1. Start the Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# 2. Start the Frontend
npm install
npm --prefix frontend install
npm run dev
```

The frontend will be available at `http://localhost:5173`.

## Deployment

**Frontend (Vercel)**
1. Connect the repository to Vercel.
2. Set Framework Preset to **Vite**.
3. Add `VITE_API_BASE_URL` environment variable pointing to your deployed backend.

**Backend (Render/Railway)**
1. Connect the repository to your host.
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

## License

Proprietary. All rights reserved.
