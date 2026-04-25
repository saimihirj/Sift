# Deployment Checklist

This is the shortest safe checklist for sharing Sift with external users.

## Recommended Host

- Use `Render` for the first proper deployment.
- Use `Vercel` for the frontend if you want Vercel previews and a public web URL.
- Do not deploy the full backend on `Vercel` in its current shape.

Why:
- the app is a single `React + FastAPI` service
- it uses SQLite plus uploaded files on disk
- it uses cookie-backed auth/session routes
- it serves the built frontend and API from one long-running process

## Vercel Frontend + Render Backend

The repo now includes `vercel.json` for a frontend-only Vercel deploy.

Use this setup:

1. Deploy the FastAPI service on Render first.
2. Copy the Render backend URL, for example `https://sift-api.onrender.com`.
3. In Vercel, set:

```text
VITE_API_BASE_URL=https://your-backend-host
```

4. On the backend host, allow the Vercel origin:

```text
SIFT_CORS_ORIGINS=https://your-vercel-app.vercel.app
```

5. If you enable OAuth across separate frontend/backend domains, also set:

```text
SIFT_FRONTEND_URL=https://your-vercel-app.vercel.app
SIFT_COOKIE_SECURE=true
SIFT_COOKIE_SAMESITE=none
```

6. Deploy from the repo root. Vercel will run:

```bash
npm --prefix frontend ci
npm --prefix frontend run build
```

7. Keep OAuth callback URLs pointed at the backend host:

```text
https://your-backend-host/api/auth/callback/google
https://your-backend-host/api/auth/callback/apple
```

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
SIFT_MODEL_PROVIDER=groq
SIFT_DATA_DIR=/var/data/sift
SIFT_EXPERT_DATA_DIR=/app/knowledge_base/expert
SIFT_SESSION_SECRET=<strong-random-secret>
SIFT_COOKIE_SECURE=true
SIFT_COOKIE_SAMESITE=lax
GROQ_API_KEY=<your-key>
GROQ_MODEL_SPEED=openai/gpt-oss-20b
GROQ_MODEL_BALANCED=openai/gpt-oss-120b
SIFT_ADMIN_TOKEN=<optional-admin-token>
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
- pick a provider such as `Groq`, `Cerebras`, or `OpenAI`
- paste a session key, or export it in the shell before launch so the UI shows the provider as server-ready

Example:

```bash
export GROQ_API_KEY=...
export GROQ_MODEL_SPEED=openai/gpt-oss-20b
export GROQ_MODEL_BALANCED=openai/gpt-oss-120b
npm run mvp:api
```
