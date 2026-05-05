# Sift

Sift is an AI workbench for startup ideation, pitch deck review, and investor-style evaluation.

It gives founders, operators, students, and analysts one focused workspace to turn rough startup material into clearer thinking: a sharper pitch, a structured evaluation, and a practical next-actions report.

Public app:

```text
https://sift-vc.web.app
```

## What Sift Does

Sift is organized around three workflows.

`Ideate` helps shape an early idea into a clearer company narrative. It asks targeted questions, tracks pitch coverage, and helps produce a refined founder-ready articulation.

`Evaluate` reviews a startup idea or pitch deck. It returns a structured verdict, score, confidence level, strengths, risks, missing evidence, and suggested next steps.

`Expert` answers startup, market, and venture-style questions with a bundled expert corpus and retrieved context. It is useful for concept breakdowns, risk mapping, deck pre-screening, and investor memo-style thinking.

## Current Production Stack

The current shareable deployment runs on Google Cloud:

- Firebase Hosting provides the clean public `web.app` link.
- Cloud Run serves the FastAPI backend and built React frontend.
- Firestore stores sessions and turns.
- Cloud Storage stores uploads and deck artifacts.
- BigQuery stores analytics events.
- Vertex AI Gemini is the default server-side model path.
- Firebase Hosting rewrites `/api/**` to Cloud Run so users only need one public URL.

The production URL is:

```text
https://sift-vc.web.app
```

Useful live checks:

```bash
curl -fsS https://sift-vc.web.app/api/health
curl -fsS https://sift-vc.web.app/api/session/providers
curl -fsS https://sift-vc.web.app/api/auth/providers
```

## Model Options

Sift supports both hosted and local/open-source model paths.

Hosted providers:

- Vertex AI Gemini
- Gemini API
- Groq
- Cerebras
- OpenAI
- OpenRouter
- Anthropic

Local or private open-source providers:

- Ollama
- OpenAI-compatible local servers such as vLLM, Hugging Face TGI, LM Studio, and llama.cpp server
- Private OpenAI-compatible GPU endpoints

For public Google Cloud deployment, Vertex AI is the default because it uses Google Cloud IAM and project billing. Users can still bring their own API key for supported providers when enabled in the UI.

## Deck Review

Deck review is part of `Evaluate`.

It can:

- ingest `.pdf` and `.pptx` pitch decks
- extract ordered slide or page content
- score the deck against startup pitch criteria
- produce slide-by-slide notes
- identify strengths, risks, missing proof, and unclear claims
- produce an investor-style report without pretending missing evidence exists

PDF review can use page images when the selected model supports vision. PPTX review relies mostly on extracted slide text unless a richer visual extraction path is configured.

## OAuth

The app has OAuth routes for:

- Google
- Apple
- LinkedIn
- X

OAuth providers only appear as active when their client ID and secret are attached to Cloud Run through Secret Manager.

Production callback URLs:

```text
https://sift-vc.web.app/api/auth/callback/google
https://sift-vc.web.app/api/auth/callback/apple
https://sift-vc.web.app/api/auth/callback/linkedin
https://sift-vc.web.app/api/auth/callback/x
```

After creating provider apps, export the issued values locally and run:

```bash
export GOOGLE_OAUTH_CLIENT_ID='...'
export GOOGLE_OAUTH_CLIENT_SECRET='...'
export APPLE_OAUTH_CLIENT_ID='...'
export APPLE_OAUTH_CLIENT_SECRET='...'
export LINKEDIN_OAUTH_CLIENT_ID='...'
export LINKEDIN_OAUTH_CLIENT_SECRET='...'
export X_OAUTH_CLIENT_ID='...'
export X_OAUTH_CLIENT_SECRET='...'

bash tools/configure_oauth_cloud_run.sh
```

Do not commit OAuth secrets. Apple uses a generated client-secret JWT, not a normal static password. X currently uses the OAuth 1.0a API key and API secret flow.

## Local Setup

Install Python and Node dependencies:

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

Run with hosted/API-key providers:

```bash
npm run mvp:api
```

Run with local Ollama:

```bash
ollama pull llama3.2
npm run mvp
```

Open:

```text
http://127.0.0.1:7860
```

Development split stack:

```bash
npm run dev
```

Frontend:

```text
http://127.0.0.1:5173
```

Backend:

```text
http://127.0.0.1:8000
```

## Common Commands

```bash
npm run mvp        # single-port local app with Ollama support
npm run mvp:api    # single-port local app for API-key providers
npm run mvp:lan    # share on the local network
npm run admin      # launch with admin mode
npm run dev        # run backend and frontend separately
npm run build      # build the frontend
python3 -m pytest  # run backend tests
```

## Fresh Data Reset

Reset local runtime data:

```bash
python3 tools/reset_runtime_data.py --local --yes
```

Reset production Google Cloud runtime data:

```bash
python3 tools/reset_runtime_data.py --gcp --project=sift-495116 --yes
```

The reset keeps source code, deployment config, Firestore database, Cloud Storage bucket, and BigQuery schema intact. It deletes generated sessions, turns, analytics events, uploads, and generated local runtime indexes.

## Deploy To Google Cloud

The project includes a Cloud Build and Firebase Hosting deployment path for project `sift-495116`.

Deploy Cloud Run:

```bash
gcloud builds submit --project=sift-495116 --region=us-central1 --config=cloudbuild.yaml .
```

Deploy the clean public Firebase Hosting link:

```bash
bash tools/deploy_clean_webapp_link.sh sift-vc
```

Verify:

```bash
curl -fsS https://sift-vc.web.app/api/health
curl -fsS https://sift-vc.web.app/api/session/providers
```

Full deployment details are in [docs/GCP_SERVERLESS_DEPLOYMENT.md](docs/GCP_SERVERLESS_DEPLOYMENT.md).

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
  expert/       bundled Expert knowledge corpus
  inbox/        source files for offline knowledge builds

tools/          launch, reset, deployment, and operator scripts
docs/           architecture, execution, and deployment notes
tests/          backend tests
data/           local runtime state, ignored by git
```

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
- Keep OAuth and model provider secrets in Secret Manager or local environment variables.
- For public usage, prefer the clean Firebase Hosting URL over the raw Cloud Run URL.
- For lowest public latency on Google Cloud, keep `min-instances` above zero and use Vertex/Gemini or another hosted low-latency provider.
- For open-source model experiments, point `OPEN_SOURCE_BASE_URL` or `LOCAL_OPENAI_BASE_URL` at a vLLM/TGI/OpenAI-compatible endpoint.

## Documentation

- [Google Cloud Serverless Deployment](docs/GCP_SERVERLESS_DEPLOYMENT.md)
- [Deployment Checklist](docs/DEPLOYMENT_CHECKLIST.md)
- [Execution Guide](docs/EXECUTION.md)
- [Platform Overview](docs/PLATFORM_OVERVIEW.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Beta Readiness Checklist](docs/BETA_READINESS.md)
- [Changelog](CHANGELOG.md)
