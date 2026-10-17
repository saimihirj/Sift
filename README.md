# Sift

[![Sift CI](https://github.com/saimihirj/Sift/actions/workflows/ci.yml/badge.svg)](https://github.com/saimihirj/Sift/actions/workflows/ci.yml)

Sift is an AI venture-evaluation workbench. A founder brings a pitch deck, a website or a plain description of the idea, and Sift reviews it the way an early-stage investor would, scores it across five pillars, and then works through the weakest parts with the founder in a guided conversation.

Live demo: [sift-blue.vercel.app](https://sift-blue.vercel.app)

## What it does

- **Reads whatever the founder has.** Decks in PDF, PPTX or DOCX, plain text, a website or a GitHub URL.
- **Evaluates like an investor.** The evaluator scores the startup on Market, Execution, Moat, Team-Product and Economics, updating its view with each answer through a Bayesian belief state rather than a one-shot score, and shows the result as a radar chart.
- **Turns the review into next steps.** A co-pilot picks the most important gap, explains why it matters and proposes a concrete rewrite for the slide or section concerned.
- **Grounds its answers in venture knowledge.** Responses draw on a curated knowledge base of investor frameworks, funding rounds and firm profiles through retrieval, and can bring in live web sources when needed.

## How it works

| Layer | What it does | Technology |
|---|---|---|
| Frontend | Input, scorecard and co-pilot screens | React 18, TypeScript, Vite, Recharts |
| API | Sessions, uploads, evaluation, chat, analytics | FastAPI, Uvicorn, SQLite |
| Model router | Sends each request to a suitable model, local or hosted | Ollama, Groq, Cerebras, Anthropic, OpenAI, OpenRouter, Gemini |
| Retrieval | Indexes the knowledge base and past conversations | ChromaDB, sentence-transformers (all-MiniLM-L6-v2) |
| Sift Brain | Venture knowledge graph, query routing, and a fine-tuned decision model | LoRA/QLoRA fine-tuning with peft and trl, Optuna tuning, OpenAI-compatible serving |

Sift Brain is the intelligence layer. Its knowledge graph links companies, investors, markets, metrics and frameworks; its router classifies each query (ideation, evaluation, expert question, deck review) and sends it to the right model; and its training pipeline fine-tunes an open-weight model (Qwen3-8B by default) on session transcripts and knowledge-base question-answer pairs, then serves the adapter locally.

## Repository layout

```
frontend/         React app
backend/          FastAPI app: api/ routes, services/ (evaluator, deck review, retrieval, model router), core/
sift_brain/       knowledge_graph/, decision_layer/, training/, serving/
scripts/          knowledge-graph updates, training and serving launchers, end-to-end test
tests/            backend tests (also backend/tests/)
knowledge_base/   curated venture knowledge used for retrieval
infra/, legacy/   analytics schema; archived Google Cloud deployment files
```

## Running it locally

Requires Python 3.11 and Node 20.

```bash
git clone https://github.com/saimihirj/Sift.git
cd Sift
cp .env.example .env            # choose a model provider and add any API keys

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# in a second terminal
npm --prefix frontend install
npm --prefix frontend run dev
```

The app opens at `http://localhost:5173`. By default Sift uses a local Ollama model; set `SIFT_MODEL_PROVIDER` and the matching key in `.env` to use a hosted one. The Sift Brain training and serving tools need the extra packages in `requirements-brain.txt` and a GPU.

## Tests

```bash
python3 -m pytest -q
```

Continuous integration runs the backend tests and a frontend build on every push to `main`.

## Deployment

The frontend deploys to Vercel (framework preset Vite, with `VITE_API_BASE_URL` pointing at the backend). The backend deploys to Render using `render.yaml`, or to any host that runs `pip install -r requirements.txt` and `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.

## License

Proprietary. All rights reserved.
