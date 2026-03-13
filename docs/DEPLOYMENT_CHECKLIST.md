# Deployment Checklist

This is the shortest safe checklist for sharing SignalX with external users.

## Recommended Host

- Use `Render` for the first proper deployment.
- Do not deploy the full app on `Vercel` in its current shape.

Why:
- the app is a single `React + FastAPI` service
- it uses SQLite plus uploaded files on disk
- it uses cookie-backed auth/session routes
- it serves the built frontend and API from one long-running process

## What Is Bundled

The Expert workbench corpus is bundled in:

```text
knowledge_base/expert/
```

Health check response now exposes:
- `expertDataDir`
- `expertCardCount`

Use `/api/health` after deploy to verify the corpus actually loaded.

## Required Env Vars

Set these in production:

```text
VK_MODEL_PROVIDER=groq
VK_DATA_DIR=/var/data/signalx
SIGNALX_EXPERT_DATA_DIR=/app/knowledge_base/expert
VK_SESSION_SECRET=<strong-random-secret>
VK_COOKIE_SECURE=true
GROQ_API_KEY=<your-key>
VK_ADMIN_TOKEN=<optional-admin-token>
```

Optional OAuth:

```text
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
APPLE_OAUTH_CLIENT_ID=
APPLE_OAUTH_CLIENT_SECRET=
```

## Render Steps

1. Push the branch.
2. Create a Render web service from the repo.
3. Use the included `render.yaml`.
4. Set the secret env vars that are marked `sync: false`.
5. Deploy.

## Post-Deploy Verification

Check these first:

1. `GET /api/health`
2. Start an `Ideate` session
3. Start an `Expert` session
4. Upload a file and ask for analysis
5. Ask an Expert question that should hit the bundled corpus
6. Confirm `expertCardCount` is non-zero

## Clone-And-Run Without Ollama

For users who just want to clone and run locally with an API provider:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
npm --prefix frontend install
cp .env.example .env
npm run mvp:api
```

Then:
- choose `Use API key` in setup
- pick a provider such as `Groq` or `OpenAI`
- paste a session key or export it in the shell before launch

Example:

```bash
export GROQ_API_KEY=...
npm run mvp:api
```
