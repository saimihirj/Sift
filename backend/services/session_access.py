"""Lightweight beta session ownership checks."""

from __future__ import annotations

from fastapi import HTTPException


def normalize_client_id(client_id: str | None) -> str:
    return (client_id or "").strip().lower()


def require_session_owner(session_row: dict, client_id: str | None) -> None:
    """Require the caller to present the same beta identity that owns the session."""
    expected = normalize_client_id(session_row.get("user_identifier"))
    supplied = normalize_client_id(client_id)
    if expected and supplied != expected:
        raise HTTPException(status_code=403, detail="Enter the matching Sift key to open this session.")
