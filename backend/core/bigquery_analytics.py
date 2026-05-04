"""Optional BigQuery event export for production analytics."""

from __future__ import annotations

import json
import os
import uuid
from functools import lru_cache
from typing import Any


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _project_id() -> str:
    return (
        os.environ.get("SIFT_GCP_PROJECT_ID")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GCP_PROJECT")
        or ""
    ).strip()


def _table_id() -> str:
    explicit = os.environ.get("SIFT_BIGQUERY_TABLE", "").strip()
    if explicit:
        return explicit

    dataset = os.environ.get("SIFT_BIGQUERY_DATASET", "").strip()
    table = os.environ.get("SIFT_BIGQUERY_EVENTS_TABLE", "events").strip() or "events"
    project = _project_id()
    if not dataset or not project:
        return ""
    return f"{project}.{dataset}.{table}"


def enabled() -> bool:
    return _truthy(os.environ.get("SIFT_BIGQUERY_ENABLED")) or bool(_table_id())


@lru_cache(maxsize=1)
def _client():
    from google.cloud import bigquery  # type: ignore

    project = _project_id() or None
    return bigquery.Client(project=project)


def append_event(
    *,
    event_type: str,
    client_id: str,
    session_id: str,
    display_name: str,
    pathname: str,
    metadata: dict[str, Any],
    created_at: str,
) -> None:
    """Best-effort BigQuery streaming insert.

    Analytics export must not block a user's product flow, so failures are
    logged by Cloud Run but not raised to the request handler.
    """
    table_id = _table_id()
    if not enabled() or not table_id:
        return

    row = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "client_id": (client_id or "").strip().lower(),
        "session_id": session_id or "",
        "display_name": (display_name or "").strip(),
        "pathname": pathname or "",
        "metadata_json": json.dumps(metadata or {}, ensure_ascii=True),
        "app_build": str((metadata or {}).get("appBuild", "")),
        "created_at": created_at,
    }
    try:
        errors = _client().insert_rows_json(table_id, [row])
        if errors:
            print(f"BigQuery analytics insert failed: {errors}")
    except Exception as exc:
        print(f"BigQuery analytics export skipped: {exc}")


def status() -> dict[str, str | bool]:
    return {
        "enabled": enabled(),
        "table": _table_id(),
    }
