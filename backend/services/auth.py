"""OAuth provider helpers for Sift."""

from __future__ import annotations

import inspect
import os
from typing import Any

try:
    from authlib.integrations.starlette_client import OAuth
except ModuleNotFoundError:  # pragma: no cover - optional dependency path
    OAuth = None


PROVIDER_DEFS: dict[str, dict[str, Any]] = {
    "google": {
        "label": "Google",
        "client_id_env": "GOOGLE_OAUTH_CLIENT_ID",
        "client_secret_env": "GOOGLE_OAUTH_CLIENT_SECRET",
        "register": {
            "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
            "client_kwargs": {"scope": "openid email profile"},
        },
    },
    "apple": {
        "label": "Apple",
        "client_id_env": "APPLE_OAUTH_CLIENT_ID",
        "client_secret_env": "APPLE_OAUTH_CLIENT_SECRET",
        "register": {
            "server_metadata_url": "https://appleid.apple.com/.well-known/openid-configuration",
            "client_kwargs": {"scope": "name email"},
        },
    },
}


oauth = OAuth() if OAuth is not None else None
_REGISTERED = False


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _ensure_registered() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    if oauth is None:
        _REGISTERED = True
        return

    for key, config in PROVIDER_DEFS.items():
        client_id = _env(config["client_id_env"])
        client_secret = _env(config["client_secret_env"])
        if not client_id or not client_secret:
            continue
        oauth.register(
            name=key,
            client_id=client_id,
            client_secret=client_secret,
            **config["register"],
        )

    _REGISTERED = True


def auth_provider_catalog() -> list[dict[str, Any]]:
    _ensure_registered()
    providers: list[dict[str, Any]] = []
    for key, config in PROVIDER_DEFS.items():
        providers.append(
            {
                "key": key,
                "label": config["label"],
                "configured": oauth is not None and oauth.create_client(key) is not None,
            }
        )
    return providers


def get_oauth_client(provider: str):
    _ensure_registered()
    if oauth is None:
        return None
    return oauth.create_client((provider or "").strip().lower())


def sanitize_next_path(value: str | None) -> str:
    if not value:
        return "/"
    candidate = value.strip()
    if not candidate.startswith("/") or candidate.startswith("//"):
        return "/"
    return candidate


async def extract_user_info(request, client, token: dict[str, Any]) -> dict[str, Any]:
    claims = token.get("userinfo")
    if isinstance(claims, dict) and claims:
        return claims

    claims = token.get("id_token_claims")
    if isinstance(claims, dict) and claims:
        return claims

    try:
        profile = client.parse_id_token(request, token)
        if inspect.isawaitable(profile):
            profile = await profile
        if isinstance(profile, dict) and profile:
            return profile
    except Exception:
        pass

    try:
        profile = await client.userinfo(token=token)
        if isinstance(profile, dict) and profile:
            return profile
    except Exception:
        pass

    fallback = {}
    for key in ("sub", "email", "name", "picture"):
        value = token.get(key)
        if value:
            fallback[key] = value
    return fallback


def build_auth_user(provider: str, claims: dict[str, Any]) -> dict[str, str]:
    user_id = str(claims.get("sub") or claims.get("email") or claims.get("id") or "").strip()
    email = str(claims.get("email") or "").strip()
    display_name = str(
        claims.get("name")
        or claims.get("given_name")
        or claims.get("preferred_username")
        or email.split("@")[0]
        or "Founder"
    ).strip()
    avatar_url = str(claims.get("picture") or "").strip()
    return {
        "provider": provider,
        "userId": user_id,
        "email": email,
        "displayName": display_name,
        "avatarUrl": avatar_url,
        "clientId": f"oauth:{provider}:{user_id or email or display_name.lower().replace(' ', '-')}",
    }
