"""FastAPI entrypoint for the Vishwakarma rebuild."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import memory

from backend.api.admin import router as admin_router
from backend.api.analytics import router as analytics_router
from backend.api.chat import router as chat_router
from backend.api.client import router as client_router
from backend.api.outline import router as outline_router
from backend.api.session import router as session_router
from backend.services.model_router import active_provider
from backend.services.runtime_state import auto_stop_monitor


ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"

app = FastAPI(title="Vishwakarma API", version="1.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    memory.init_db()
    asyncio.create_task(auto_stop_monitor())


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "app": "Vishwakarma",
        "modelProvider": active_provider(),
        "dataDir": str(memory.DATA_DIR),
    }


app.include_router(session_router)
app.include_router(chat_router)
app.include_router(client_router)
app.include_router(outline_router)
app.include_router(analytics_router)
app.include_router(admin_router)

if FRONTEND_ASSETS.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_ASSETS)), name="assets")


@app.get("/{full_path:path}")
async def frontend_app(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    if FRONTEND_DIST.exists():
        return FileResponse(FRONTEND_DIST / "index.html")
    return JSONResponse(
        status_code=200,
        content={
            "message": "Frontend build not found. Run `npm --prefix frontend run build` or `npm run dev`.",
        },
    )
