"""OAuth routes for Vishwakarma."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

import memory

from backend.services.auth import auth_provider_catalog, build_auth_user, extract_user_info, get_oauth_client, sanitize_next_path


router = APIRouter(prefix="/api/auth", tags=["auth"])


def _session_store(request: Request) -> dict | None:
    try:
        return request.session
    except Exception:
        return None


@router.get("/providers")
async def auth_providers() -> dict:
    return {"providers": auth_provider_catalog()}


@router.get("/session")
async def auth_session(request: Request) -> dict:
    session = _session_store(request)
    user = session.get("auth_user") if session else None
    error = session.pop("auth_error", "") if session else ""
    return {
        "user": user,
        "providers": auth_provider_catalog(),
        "error": error,
        "adminMode": os.environ.get("VK_ADMIN_MODE", "false").strip().lower() == "true",
    }


@router.get("/login/{provider}")
async def auth_login(request: Request, provider: str, next: str = Query(default="/")):
    client = get_oauth_client(provider)
    session = _session_store(request)
    if session is None:
        raise HTTPException(status_code=503, detail="Session support is not available")
    if client is None:
        raise HTTPException(status_code=404, detail="OAuth provider is not configured")

    session["auth_next"] = sanitize_next_path(next)
    redirect_uri = str(request.url_for("auth_callback", provider=provider))
    authorize_kwargs = {}
    if provider == "google":
        authorize_kwargs["prompt"] = "select_account"
    if provider == "apple":
        authorize_kwargs["response_mode"] = "form_post"
    return await client.authorize_redirect(request, redirect_uri, **authorize_kwargs)


@router.api_route("/callback/{provider}", methods=["GET", "POST"])
async def auth_callback(request: Request, provider: str):
    client = get_oauth_client(provider)
    session = _session_store(request)
    if session is None:
        raise HTTPException(status_code=503, detail="Session support is not available")
    if client is None:
        raise HTTPException(status_code=404, detail="OAuth provider is not configured")

    next_path = sanitize_next_path(session.pop("auth_next", "/"))
    try:
        token = await client.authorize_access_token(request)
        claims = await extract_user_info(request, client, token)
        user = build_auth_user(provider, claims)
    except Exception:
        session["auth_error"] = f"{provider.title()} sign-in failed. Check OAuth credentials and redirect setup."
        return RedirectResponse(next_path, status_code=302)

    session["auth_user"] = user
    session["auth_token"] = {
        "provider": provider,
        "hasRefreshToken": bool(token.get("refresh_token")),
    }
    memory.track_event(
        event_type="auth_login",
        client_id=user["clientId"],
        display_name=user["displayName"],
        pathname=next_path,
        metadata={
            "provider": provider,
            "email": user["email"],
        },
    )
    return RedirectResponse(next_path, status_code=302)


@router.post("/logout")
async def auth_logout(request: Request) -> JSONResponse:
    session = _session_store(request)
    user = session.pop("auth_user", None) if session else None
    if session:
        session.pop("auth_token", None)
        session.pop("auth_next", None)
        session.pop("auth_error", None)
    if isinstance(user, dict):
        memory.track_event(
            event_type="auth_logout",
            client_id=user.get("clientId", ""),
            display_name=user.get("displayName", ""),
            pathname="/",
            metadata={"provider": user.get("provider", "")},
        )
    return JSONResponse({"ok": True})
