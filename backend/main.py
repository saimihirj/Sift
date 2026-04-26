"""FastAPI entrypoint for Sift."""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
try:
    from starlette.middleware.sessions import SessionMiddleware
except ModuleNotFoundError:  # pragma: no cover - optional dependency path
    SessionMiddleware = None

from backend.core import memory

from backend.api.admin import router as admin_router
from backend.api.analytics import router as analytics_router
from backend.api.auth import router as auth_router
from backend.api.chat import router as chat_router
from backend.api.client import router as client_router
from backend.api.evaluator import router as evaluator_router
from backend.api.outline import router as outline_router
from backend.api.session import router as session_router
from backend.services.expert_knowledge import expert_card_count, expert_data_dir
from backend.services.model_router import active_provider, provider_catalog
from backend.services.runtime_state import auto_stop_monitor


ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"
DEFAULT_CORS_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:5174",
    "http://localhost:5174",
)
RATE_LIMIT_WINDOW_SECONDS = 60.0
RATE_LIMIT_MAX_REQUESTS = int(os.environ.get("SIFT_RATE_LIMIT_PER_MINUTE", "120"))
RATE_LIMIT_BUCKETS: dict[str, list[float]] = {}


def cors_origins() -> list[str]:
    configured = os.environ.get("SIFT_CORS_ORIGINS", "")
    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    return origins or list(DEFAULT_CORS_ORIGINS)


def cookie_same_site() -> str:
    configured = os.environ.get("SIFT_COOKIE_SAMESITE", "lax").strip().lower()
    if configured in {"lax", "strict", "none"}:
        return configured
    return "lax"

app = FastAPI(title="Sift API", version="0.2.0")


@app.middleware("http")
async def beta_rate_limit(request, call_next):
    path = request.url.path
    if RATE_LIMIT_MAX_REQUESTS > 0 and path.startswith("/api/") and path not in {"/api/health", "/api/client/heartbeat"}:
        client_host = request.client.host if request.client else "local"
        key = f"{client_host}:{path}"
        now = time.monotonic()
        recent = [stamp for stamp in RATE_LIMIT_BUCKETS.get(key, []) if now - stamp < RATE_LIMIT_WINDOW_SECONDS]
        if len(recent) >= RATE_LIMIT_MAX_REQUESTS:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests in a short period. Wait a minute and try again."},
            )
        recent.append(now)
        RATE_LIMIT_BUCKETS[key] = recent
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if SessionMiddleware is not None:
    app.add_middleware(
        SessionMiddleware,
        secret_key=os.environ.get("SIFT_SESSION_SECRET", "sift-local-dev-secret"),
        same_site=cookie_same_site(),
        https_only=os.environ.get("SIFT_COOKIE_SECURE", "false").strip().lower() == "true",
        max_age=60 * 60 * 24 * 30,
    )


@app.on_event("startup")
async def on_startup() -> None:
    memory.init_db()
    asyncio.create_task(auto_stop_monitor())


@app.get("/api/health")
async def health() -> dict:
    providers = provider_catalog()
    return {
        "status": "ok",
        "app": "Sift",
        "modelProvider": active_provider(),
        "configuredProviders": [
            provider["key"]
            for provider in providers
            if not provider.get("requiresApiKey") or provider.get("serverConfigured")
        ],
        "dataDir": str(memory.DATA_DIR),
        "expertDataDir": str(expert_data_dir()),
        "expertCardCount": expert_card_count(),
    }


app.include_router(session_router)
app.include_router(chat_router)
app.include_router(evaluator_router)
app.include_router(client_router)
app.include_router(outline_router)
app.include_router(analytics_router)
app.include_router(auth_router)
app.include_router(admin_router)

if FRONTEND_ASSETS.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_ASSETS)), name="assets")


@app.get("/{full_path:path}")
async def frontend_app(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    if full_path == "admin" and os.environ.get("SIFT_ADMIN_MODE", "false").strip().lower() != "true":
        return RedirectResponse("/", status_code=302)
    if FRONTEND_DIST.exists():
        return FileResponse(FRONTEND_DIST / "index.html")
    return JSONResponse(
        status_code=200,
        content={
            "message": "Frontend build not found. Run `npm --prefix frontend run build` or `npm run dev`.",
        },
    )
