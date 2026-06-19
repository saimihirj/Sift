"""Session and analytics persistence for Sift.

Uses SQLite locally by default, and can use Firestore on Google Cloud.
Stores:
  sessions         — founder profile + coverage state per user
  turns            — every conversation message
  analytics_events — page views, session starts, chat completions, uploads, etc.

Also handles JSONL export for fine-tuning.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.core import bigquery_analytics


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("SIFT_DATA_DIR", str(ROOT_DIR / "data")))
DB_PATH = DATA_DIR / "sessions.db"
EXPORTS_DIR = DATA_DIR / "exports"
PERSISTENCE_BACKEND = os.environ.get("SIFT_PERSISTENCE_BACKEND", os.environ.get("SIFT_DB_BACKEND", "sqlite")).strip().lower()
FIRESTORE_COLLECTION_PREFIX = os.environ.get("SIFT_FIRESTORE_COLLECTION_PREFIX", "sift").strip() or "sift"
_DB_READY = False
USEFUL_ADMIN_EVENT_TYPES = {
    "auth_login",
    "auth_logout",
    "session_started",
    "session_runtime_updated",
    "evaluator_started",
    "evaluator_answered",
    "evaluator_completed",
    "evaluator_deeper_started",
    "evaluator_report_viewed",
    "chat_completed",
    "file_uploaded",
    "outline_opened",
    "website_fetch_failed",
}


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    user_identifier TEXT,
    display_name    TEXT DEFAULT '',
    session_type    TEXT DEFAULT 'mentor',
    founder_type    TEXT DEFAULT 'unknown',
    sector          TEXT DEFAULT 'unknown',
    stage           TEXT DEFAULT 'unknown',
    mode            TEXT DEFAULT 'think_it_through',
    geography       TEXT DEFAULT 'unspecified',
    question_budget INTEGER DEFAULT 15,
    provider        TEXT DEFAULT 'ollama',
    model           TEXT DEFAULT '',
    website_url     TEXT DEFAULT '',
    company_name    TEXT DEFAULT '',
    coverage_json   TEXT DEFAULT '{}',
    facts_json      TEXT DEFAULT '{}',
    metadata_json   TEXT DEFAULT '{}',
    created_at      TEXT,
    last_active     TEXT
);

CREATE TABLE IF NOT EXISTS turns (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    role          TEXT NOT NULL,
    content       TEXT NOT NULL,
    metadata_json TEXT DEFAULT '{}',
    timestamp     TEXT
);

CREATE TABLE IF NOT EXISTS analytics_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id     TEXT DEFAULT '',
    session_id    TEXT DEFAULT '',
    display_name  TEXT DEFAULT '',
    event_type    TEXT NOT NULL,
    pathname      TEXT DEFAULT '',
    metadata_json TEXT DEFAULT '{}',
    created_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_turns_session   ON turns(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user   ON sessions(user_identifier);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(last_active);
CREATE INDEX IF NOT EXISTS idx_events_created  ON analytics_events(created_at);
CREATE INDEX IF NOT EXISTS idx_events_client   ON analytics_events(client_id);
CREATE INDEX IF NOT EXISTS idx_events_session  ON analytics_events(session_id);
"""


def _use_firestore() -> bool:
    return PERSISTENCE_BACKEND in {"firestore", "gcp", "google_firestore"}


def _project_id() -> str:
    return (
        os.environ.get("SIFT_GCP_PROJECT_ID")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GCP_PROJECT")
        or ""
    ).strip()


@lru_cache(maxsize=1)
def _firestore_client():
    try:
        from google.cloud import firestore  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "SIFT_PERSISTENCE_BACKEND=firestore requires google-cloud-firestore. "
            "Install production requirements before starting the service."
        ) from exc

    project = _project_id() or None
    database = os.environ.get("SIFT_FIRESTORE_DATABASE", "").strip()
    if database:
        return firestore.Client(project=project, database=database)
    return firestore.Client(project=project)


def _firestore_sessions():
    return _firestore_client().collection(f"{FIRESTORE_COLLECTION_PREFIX}_sessions")


def _firestore_events():
    return _firestore_client().collection(f"{FIRESTORE_COLLECTION_PREFIX}_analytics_events")


def _session_turn_count(session_id: str) -> int:
    if not session_id:
        return 0
    return sum(1 for _ in _firestore_sessions().document(session_id).collection("turns").stream())


def _session_defaults(row: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "user_identifier": "",
        "display_name": "",
        "session_type": "mentor",
        "founder_type": "unknown",
        "sector": "unknown",
        "stage": "unknown",
        "mode": "think_it_through",
        "geography": "unspecified",
        "question_budget": 15,
        "provider": "ollama",
        "model": "",
        "website_url": "",
        "company_name": "",
        "coverage_json": "{}",
        "facts_json": "{}",
        "metadata_json": "{}",
        "created_at": "",
        "last_active": "",
        "turn_count": 0,
    }
    return {**defaults, **row}


def _session_from_firestore(doc, *, include_turn_count: bool = True) -> dict[str, Any] | None:
    if not doc.exists:
        return None
    row = dict(doc.to_dict() or {})
    row["id"] = doc.id
    if include_turn_count:
        row["turn_count"] = _session_turn_count(doc.id)
    return _session_defaults(row)


def _event_from_firestore(doc) -> dict[str, Any]:
    item = dict(doc.to_dict() or {})
    metadata = item.pop("metadata", None)
    raw_metadata = item.pop("metadata_json", "{}") or "{}"
    if isinstance(metadata, dict):
        item["metadata"] = metadata
    else:
        item["metadata"] = _load_json(raw_metadata, {})
    return item


def _normalize_turn_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=True)


def _raw_conn():
    if _use_firestore():
        raise RuntimeError("SQLite connection requested while Firestore persistence is active.")

    db_url = os.environ.get("SIFT_DATABASE_URL", "").strip()
    if db_url:
        try:
            import libsql_experimental as db_driver  # type: ignore
            con = db_driver.connect(db_url, auth_token=os.environ.get("SIFT_DATABASE_TOKEN", ""))
            con.row_factory = db_driver.Row
            return con
        except ImportError:
            pass

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con


def _conn():
    global _DB_READY
    if not _DB_READY:
        init_db()
    return _raw_conn()


@lru_cache(maxsize=1)
def _current_app_build() -> str:
    explicit = os.environ.get("SIFT_APP_BUILD", "").strip()
    if explicit:
        return explicit
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(Path(__file__).resolve().parent),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip() or "dev"
    except Exception:
        return "dev"


def _load_json(raw: str | None, default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every startup."""
    global _DB_READY
    if _use_firestore():
        _firestore_client()
        _DB_READY = True
        return

    with _raw_conn() as con:
        con.executescript(_SCHEMA)

        session_columns = {row["name"] for row in con.execute("PRAGMA table_info(sessions)").fetchall()}
        if "display_name" not in session_columns:
            con.execute("ALTER TABLE sessions ADD COLUMN display_name TEXT DEFAULT ''")
        if "session_type" not in session_columns:
            con.execute("ALTER TABLE sessions ADD COLUMN session_type TEXT DEFAULT 'mentor'")
        if "question_budget" not in session_columns:
            con.execute("ALTER TABLE sessions ADD COLUMN question_budget INTEGER DEFAULT 15")
        if "geography" not in session_columns:
            con.execute("ALTER TABLE sessions ADD COLUMN geography TEXT DEFAULT 'unspecified'")
        if "provider" not in session_columns:
            con.execute("ALTER TABLE sessions ADD COLUMN provider TEXT DEFAULT 'ollama'")
        if "model" not in session_columns:
            con.execute("ALTER TABLE sessions ADD COLUMN model TEXT DEFAULT ''")
        if "website_url" not in session_columns:
            con.execute("ALTER TABLE sessions ADD COLUMN website_url TEXT DEFAULT ''")
        if "metadata_json" not in session_columns:
            con.execute("ALTER TABLE sessions ADD COLUMN metadata_json TEXT DEFAULT '{}'")

        turn_columns = {row["name"] for row in con.execute("PRAGMA table_info(turns)").fetchall()}
        if "metadata_json" not in turn_columns:
            con.execute("ALTER TABLE turns ADD COLUMN metadata_json TEXT DEFAULT '{}'")
    _DB_READY = True


def create_session(
    state,
    user_identifier: str = "",
    display_name: str = "",
    session_type: str = "mentor",
    question_budget: int | None = None,
    provider: str = "ollama",
    model: str = "",
    website_url: str = "",
    metadata: dict | None = None,
) -> str:
    """Insert a new session row. Returns the new session UUID."""
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": session_id,
        "user_identifier": user_identifier.strip().lower() if user_identifier else "",
        "display_name": (display_name or "").strip(),
        "session_type": session_type or "mentor",
        "founder_type": getattr(state, "founder_type", "unknown"),
        "sector": getattr(state, "sector", "unknown"),
        "stage": getattr(state, "stage", "unknown"),
        "mode": getattr(state, "mode", "think_it_through"),
        "geography": getattr(state, "geography", "unspecified") or "unspecified",
        "question_budget": question_budget or 15,
        "provider": provider or "ollama",
        "model": model or "",
        "website_url": (website_url or "").strip(),
        "company_name": getattr(state, "company_name", ""),
        "coverage_json": json.dumps(getattr(state, "coverage", {})),
        "facts_json": json.dumps(getattr(state, "facts", {})),
        "metadata_json": json.dumps(metadata or {}),
        "created_at": now,
        "last_active": now,
    }
    if _use_firestore():
        _firestore_sessions().document(session_id).set(row)
        return session_id

    with _conn() as con:
        con.execute(
            """INSERT INTO sessions
               (id, user_identifier, display_name, session_type, founder_type, sector, stage, mode,
                geography, question_budget, provider, model, website_url, company_name, coverage_json, facts_json,
                metadata_json, created_at, last_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["id"],
                row["user_identifier"],
                row["display_name"],
                row["session_type"],
                row["founder_type"],
                row["sector"],
                row["stage"],
                row["mode"],
                row["geography"],
                row["question_budget"],
                row["provider"],
                row["model"],
                row["website_url"],
                row["company_name"],
                row["coverage_json"],
                row["facts_json"],
                row["metadata_json"],
                row["created_at"],
                row["last_active"],
            ),
        )
    return session_id


def load_session(user_identifier: str) -> dict | None:
    """Look up the most recent session for a user identifier."""
    if not user_identifier:
        return None
    key = user_identifier.strip().lower()
    if _use_firestore():
        rows = [
            _session_from_firestore(doc)
            for doc in _firestore_sessions().where("user_identifier", "==", key).stream()
        ]
        rows = [row for row in rows if row is not None]
        rows.sort(key=lambda item: item.get("last_active", ""), reverse=True)
        return rows[0] if rows else None

    with _conn() as con:
        row = con.execute(
            """SELECT s.*, COUNT(t.id) AS turn_count
               FROM sessions s
               LEFT JOIN turns t ON t.session_id = s.id
               WHERE s.user_identifier = ?
               GROUP BY s.id
               ORDER BY s.last_active DESC
               LIMIT 1""",
            (key,),
        ).fetchone()
    return dict(row) if row is not None else None


def get_session(session_id: str) -> dict | None:
    """Return a session row by its UUID."""
    if not session_id:
        return None
    if _use_firestore():
        return _session_from_firestore(_firestore_sessions().document(session_id).get())

    with _conn() as con:
        row = con.execute(
            """SELECT s.*, COUNT(t.id) AS turn_count
               FROM sessions s
               LEFT JOIN turns t ON t.session_id = s.id
               WHERE s.id = ?
               GROUP BY s.id
               LIMIT 1""",
            (session_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def delete_session(session_id: str) -> None:
    """Delete a session entirely."""
    if not session_id:
        return
    if _use_firestore():
        _firestore_sessions().document(session_id).delete()
        return

    with _conn() as con:
        con.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        con.commit()


def update_session(session_id: str, state) -> None:
    """Sync coverage, facts, company_name and last_active back to the DB."""
    if not session_id:
        return
    payload = {
        "coverage_json": json.dumps(getattr(state, "coverage", {})),
        "facts_json": json.dumps(getattr(state, "facts", {})),
        "company_name": getattr(state, "company_name", ""),
        "sector": getattr(state, "sector", "unknown"),
        "stage": getattr(state, "stage", "unknown"),
        "founder_type": getattr(state, "founder_type", "unknown"),
        "mode": getattr(state, "mode", "think_it_through"),
        "geography": getattr(state, "geography", "unspecified") or "unspecified",
        "last_active": datetime.now(timezone.utc).isoformat(),
    }
    if _use_firestore():
        _firestore_sessions().document(session_id).set(payload, merge=True)
        return

    with _conn() as con:
        con.execute(
            """UPDATE sessions SET
               coverage_json = ?,
               facts_json    = ?,
               company_name  = ?,
               sector        = ?,
               stage         = ?,
               founder_type  = ?,
               mode          = ?,
               geography     = ?,
               last_active   = ?
               WHERE id = ?""",
            (
                payload["coverage_json"],
                payload["facts_json"],
                payload["company_name"],
                payload["sector"],
                payload["stage"],
                payload["founder_type"],
                payload["mode"],
                payload["geography"],
                payload["last_active"],
                session_id,
            ),
        )


def update_session_runtime(session_id: str, provider: str, model: str) -> None:
    """Persist non-secret runtime selection for a session."""
    if not session_id:
        return
    payload = {
        "provider": provider or "ollama",
        "model": model or "",
        "last_active": datetime.now(timezone.utc).isoformat(),
    }
    if _use_firestore():
        _firestore_sessions().document(session_id).set(payload, merge=True)
        return

    with _conn() as con:
        con.execute(
            """UPDATE sessions SET
               provider = ?,
               model = ?,
               last_active = ?
               WHERE id = ?""",
            (
                payload["provider"],
                payload["model"],
                payload["last_active"],
                session_id,
            ),
        )


def get_session_metadata(session_row: dict | None) -> dict:
    if not session_row:
        return {}
    return _load_json(session_row.get("metadata_json"), {})


def update_session_metadata(session_id: str, metadata: dict) -> None:
    if not session_id:
        return
    payload = {
        "metadata_json": json.dumps(metadata or {}),
        "last_active": datetime.now(timezone.utc).isoformat(),
    }
    if _use_firestore():
        _firestore_sessions().document(session_id).set(payload, merge=True)
        return

    with _conn() as con:
        con.execute(
            """UPDATE sessions SET metadata_json = ?, last_active = ? WHERE id = ?""",
            (
                payload["metadata_json"],
                payload["last_active"],
                session_id,
            ),
        )


def store_turn(session_id: str, role: str, content: Any, metadata: dict | None = None) -> None:
    """Append one conversation turn."""
    if not session_id:
        return
    timestamp = datetime.now(timezone.utc).isoformat()
    content_text = _normalize_turn_content(content)
    if _use_firestore():
        _firestore_sessions().document(session_id).collection("turns").document(str(uuid.uuid4())).set(
            {
                "session_id": session_id,
                "role": role,
                "content": content_text,
                "metadata_json": json.dumps(metadata or {}),
                "timestamp": timestamp,
            }
        )
        _firestore_sessions().document(session_id).set({"last_active": timestamp}, merge=True)
        return

    with _conn() as con:
        con.execute(
            """INSERT INTO turns (session_id, role, content, metadata_json, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (
                session_id,
                role,
                content_text,
                json.dumps(metadata or {}),
                timestamp,
            ),
        )


def get_session_turns(session_id: str) -> list[dict]:
    """Return all turns for a session, ordered by insertion."""
    if _use_firestore():
        docs = _firestore_sessions().document(session_id).collection("turns").order_by("timestamp").stream()
        result = []
        for doc in docs:
            item = dict(doc.to_dict() or {})
            raw_metadata = item.pop("metadata_json", "{}") or "{}"
            item["metadata"] = _load_json(raw_metadata, {})
            result.append(
                {
                    "role": item.get("role", ""),
                    "content": item.get("content", ""),
                    "timestamp": item.get("timestamp", ""),
                    "metadata": item["metadata"],
                }
            )
        return result

    with _conn() as con:
        rows = con.execute(
            """SELECT role, content, metadata_json, timestamp
               FROM turns
               WHERE session_id = ?
               ORDER BY id""",
            (session_id,),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        raw_metadata = item.pop("metadata_json", "{}") or "{}"
        try:
            item["metadata"] = json.loads(raw_metadata)
        except json.JSONDecodeError:
            item["metadata"] = {}
        result.append(item)
    return result


def list_sessions(limit: int = 100) -> list[dict]:
    """Return recent sessions with turn counts for the admin dashboard."""
    if _use_firestore():
        try:
            docs = _firestore_sessions().order_by("last_active", direction="DESCENDING").limit(limit).stream()
        except Exception:
            docs = _firestore_sessions().stream()
        rows = [_session_from_firestore(doc) for doc in docs]
        rows = [row for row in rows if row is not None]
        rows.sort(key=lambda item: item.get("last_active", ""), reverse=True)
        return rows[:limit]

    with _conn() as con:
        rows = con.execute(
            """SELECT
                   s.id,
                   s.user_identifier,
                   s.display_name,
                   s.session_type,
                   s.sector,
                   s.stage,
                   s.founder_type,
                   s.company_name,
                   s.mode,
                   s.question_budget,
                   s.provider,
                   s.model,
                   s.website_url,
                   s.metadata_json,
                   s.created_at,
                   s.last_active,
                   COUNT(t.id) AS turn_count
               FROM sessions s
               LEFT JOIN turns t ON t.session_id = s.id
               GROUP BY s.id
               ORDER BY s.last_active DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_sessions_for_user(user_identifier: str, limit: int = 50) -> list[dict]:
    """Return recent sessions for a specific user identifier."""
    key = (user_identifier or "").strip().lower()
    if not key:
        return []
    if _use_firestore():
        rows = [
            _session_from_firestore(doc)
            for doc in _firestore_sessions().where("user_identifier", "==", key).stream()
        ]
        rows = [row for row in rows if row is not None]
        rows.sort(key=lambda item: item.get("last_active", ""), reverse=True)
        return rows[:limit]

    with _conn() as con:
        rows = con.execute(
            """SELECT
                   s.id,
                   s.user_identifier,
                   s.display_name,
                   s.session_type,
                   s.sector,
                   s.stage,
                   s.founder_type,
                   s.company_name,
                   s.mode,
                   s.question_budget,
                   s.provider,
                   s.model,
                   s.website_url,
                   s.metadata_json,
                   s.created_at,
                   s.last_active,
                   COUNT(t.id) AS turn_count
               FROM sessions s
               LEFT JOIN turns t ON t.session_id = s.id
               WHERE s.user_identifier = ?
               GROUP BY s.id
               ORDER BY s.last_active DESC
               LIMIT ?""",
            (key, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def clear_history_for_user(user_identifier: str) -> dict[str, int]:
    """Delete sessions, turns, and analytics linked to one user identifier."""
    key = (user_identifier or "").strip().lower()
    if not key:
        return {"sessions": 0, "turns": 0, "events": 0}

    if _use_firestore():
        session_docs = list(_firestore_sessions().where("user_identifier", "==", key).stream())
        session_ids = [doc.id for doc in session_docs]
        turns_deleted = 0
        for doc in session_docs:
            turns = list(doc.reference.collection("turns").stream())
            for turn in turns:
                turn.reference.delete()
            turns_deleted += len(turns)
            doc.reference.delete()

        event_refs: dict[str, Any] = {}
        for doc in _firestore_events().where("client_id", "==", key).stream():
            event_refs[doc.id] = doc.reference
        for session_id in session_ids:
            for doc in _firestore_events().where("session_id", "==", session_id).stream():
                event_refs[doc.id] = doc.reference
        for ref in event_refs.values():
            ref.delete()

        return {
            "sessions": len(session_docs),
            "turns": turns_deleted,
            "events": len(event_refs),
        }

    with _conn() as con:
        session_rows = con.execute(
            "SELECT id FROM sessions WHERE user_identifier = ?",
            (key,),
        ).fetchall()
        session_ids = [row["id"] for row in session_rows]

        turns_deleted = 0
        events_deleted = 0
        if session_ids:
            placeholders = ",".join("?" for _ in session_ids)
            turns_deleted = con.execute(
                f"DELETE FROM turns WHERE session_id IN ({placeholders})",
                session_ids,
            ).rowcount
            events_deleted += con.execute(
                f"DELETE FROM analytics_events WHERE session_id IN ({placeholders})",
                session_ids,
            ).rowcount

        events_deleted += con.execute(
            "DELETE FROM analytics_events WHERE client_id = ?",
            (key,),
        ).rowcount
        sessions_deleted = con.execute(
            "DELETE FROM sessions WHERE user_identifier = ?",
            (key,),
        ).rowcount

    return {
        "sessions": int(sessions_deleted or 0),
        "turns": int(turns_deleted or 0),
        "events": int(events_deleted or 0),
    }


def track_event(
    event_type: str,
    client_id: str = "",
    session_id: str = "",
    display_name: str = "",
    pathname: str = "",
    metadata: dict | None = None,
) -> None:
    """Append an analytics event for admin monitoring."""
    if not event_type:
        return
    payload = dict(metadata or {})
    payload.setdefault("appBuild", _current_app_build())
    created_at = datetime.now(timezone.utc).isoformat()
    normalized_client_id = (client_id or "").strip().lower()
    normalized_display_name = (display_name or "").strip()

    if _use_firestore():
        _firestore_events().document(str(uuid.uuid4())).set(
            {
                "client_id": normalized_client_id,
                "session_id": session_id,
                "display_name": normalized_display_name,
                "event_type": event_type,
                "pathname": pathname,
                "metadata_json": json.dumps(payload),
                "metadata": payload,
                "created_at": created_at,
            }
        )
        bigquery_analytics.append_event(
            event_type=event_type,
            client_id=normalized_client_id,
            session_id=session_id,
            display_name=normalized_display_name,
            pathname=pathname,
            metadata=payload,
            created_at=created_at,
        )
        return

    with _conn() as con:
        con.execute(
            """INSERT INTO analytics_events
               (client_id, session_id, display_name, event_type, pathname, metadata_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                normalized_client_id,
                session_id,
                normalized_display_name,
                event_type,
                pathname,
                json.dumps(payload),
                created_at,
            ),
        )
    bigquery_analytics.append_event(
        event_type=event_type,
        client_id=normalized_client_id,
        session_id=session_id,
        display_name=normalized_display_name,
        pathname=pathname,
        metadata=payload,
        created_at=created_at,
    )

def list_recent_events(limit: int = 100, *, current_build_only: bool = False, useful_only: bool = False) -> list[dict]:
    """Return the most recent analytics events."""
    if _use_firestore():
        try:
            docs = _firestore_events().order_by("created_at", direction="DESCENDING").limit(max(limit * 4, limit)).stream()
        except Exception:
            docs = _firestore_events().stream()

        events = []
        current_build = _current_app_build()
        for doc in docs:
            item = _event_from_firestore(doc)
            if useful_only and item.get("event_type") not in USEFUL_ADMIN_EVENT_TYPES:
                continue
            if current_build_only and item.get("metadata", {}).get("appBuild") != current_build:
                continue
            events.append(item)
        events.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return events[:limit]

    with _conn() as con:
        rows = con.execute(
            """SELECT client_id, session_id, display_name, event_type, pathname, metadata_json, created_at
               FROM analytics_events
               ORDER BY id DESC""",
        ).fetchall()

    events = []
    current_build = _current_app_build()
    for row in rows:
        item = dict(row)
        raw_metadata = item.pop("metadata_json", "{}") or "{}"
        try:
            item["metadata"] = json.loads(raw_metadata)
        except json.JSONDecodeError:
            item["metadata"] = {}
        if useful_only and item["event_type"] not in USEFUL_ADMIN_EVENT_TYPES:
            continue
        if current_build_only and item.get("metadata", {}).get("appBuild") != current_build:
            continue
        events.append(item)
        if len(events) >= limit:
            break
    return events


def _average_event_metric(event_type: str, metric_key: str, *, current_build_only: bool = False, useful_only: bool = False) -> float:
    values: list[float] = []
    for event in list_recent_events(limit=2000, current_build_only=current_build_only, useful_only=useful_only):
        if event["event_type"] != event_type:
            continue
        value = event.get("metadata", {}).get(metric_key)
        if isinstance(value, (int, float)):
            values.append(float(value))
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _most_common_event_value(event_type: str, metric_key: str, *, current_build_only: bool = False, useful_only: bool = False) -> str:
    counts: dict[str, int] = {}
    for event in list_recent_events(limit=2000, current_build_only=current_build_only, useful_only=useful_only):
        if event["event_type"] != event_type:
            continue
        value = event.get("metadata", {}).get(metric_key)
        if isinstance(value, str) and value.strip():
            counts[value.strip()] = counts.get(value.strip(), 0) + 1
    if not counts:
        return ""
    return max(counts.items(), key=lambda item: item[1])[0]


def get_admin_overview() -> dict:
    """Aggregate product and runtime analytics for the admin dashboard."""
    filtered_events = list_recent_events(limit=5000, current_build_only=True, useful_only=True)
    filtered_event_breakdown: dict[str, int] = {}
    unique_visitors = set()
    events_last_24_hours = 0
    cutoff = datetime.now(timezone.utc).timestamp() - 86400
    for event in filtered_events:
        event_type = event["event_type"]
        filtered_event_breakdown[event_type] = filtered_event_breakdown.get(event_type, 0) + 1
        client_id = (event.get("client_id") or "").strip()
        if client_id:
            unique_visitors.add(client_id)
        try:
            created_at = datetime.fromisoformat((event.get("created_at") or "").replace("Z", "+00:00"))
            if created_at.timestamp() >= cutoff:
                events_last_24_hours += 1
        except ValueError:
            continue

    if _use_firestore():
        session_rows = list_sessions(limit=10000)
        total_sessions = len(session_rows)
        total_turns = sum(int(row.get("turn_count", 0) or 0) for row in session_rows)
        cutoff_7_days = datetime.now(timezone.utc).timestamp() - (86400 * 7)
        sessions_last_7_days = 0
        evaluator_sessions = 0
        provider_breakdown: dict[str, int] = {}
        for row in session_rows:
            if row.get("session_type") == "evaluator":
                evaluator_sessions += 1
            provider = row.get("provider", "unknown") or "unknown"
            provider_breakdown[provider] = provider_breakdown.get(provider, 0) + 1
            try:
                last_active = datetime.fromisoformat((row.get("last_active") or "").replace("Z", "+00:00"))
                if last_active.timestamp() >= cutoff_7_days:
                    sessions_last_7_days += 1
            except ValueError:
                continue
    else:
        with _conn() as con:
            total_sessions = con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            total_turns = con.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
            sessions_last_7_days = con.execute(
                "SELECT COUNT(*) FROM sessions WHERE last_active >= datetime('now', '-7 days')"
            ).fetchone()[0]
            evaluator_sessions = con.execute(
                "SELECT COUNT(*) FROM sessions WHERE session_type = 'evaluator'"
            ).fetchone()[0]
            provider_breakdown = dict(
                con.execute(
                    "SELECT provider, COUNT(*) FROM sessions GROUP BY provider"
                ).fetchall()
            )

    evaluator_completions = filtered_event_breakdown.get("evaluator_completed", 0)
    average_success_score = _average_event_metric(
        "evaluator_completed",
        "overallScore",
        current_build_only=True,
        useful_only=True,
    )
    completion_rate = round((evaluator_completions / evaluator_sessions) * 100.0, 1) if evaluator_sessions else 0.0

    return {
        "totalSessions": total_sessions,
        "totalTurns": total_turns,
        "totalEvents": len(filtered_events),
        "uniqueVisitors": len(unique_visitors),
        "sessionsLast7Days": sessions_last_7_days,
        "eventsLast24Hours": events_last_24_hours,
        "outlineOpens": filtered_event_breakdown.get("outline_opened", 0),
        "uploads": filtered_event_breakdown.get("file_uploaded", 0),
        "chatCompletions": filtered_event_breakdown.get("chat_completed", 0),
        "averageFirstTokenSeconds": _average_event_metric(
            "chat_completed",
            "firstTokenSeconds",
            current_build_only=True,
            useful_only=True,
        ),
        "averageTotalSeconds": _average_event_metric(
            "chat_completed",
            "totalSeconds",
            current_build_only=True,
            useful_only=True,
        ),
        "evaluatorSessions": evaluator_sessions,
        "evaluatorCompletions": evaluator_completions,
        "evaluatorCompletionRate": completion_rate,
        "averageSuccessScore": average_success_score,
        "averageEvaluatorScore": average_success_score,
        "websiteFetchFailures": filtered_event_breakdown.get("website_fetch_failed", 0),
        "dropOffQuestion": _most_common_event_value(
            "evaluator_answered",
            "questionId",
            current_build_only=True,
            useful_only=True,
        ),
        "providerBreakdown": provider_breakdown,
        "eventBreakdown": filtered_event_breakdown,
    }


def get_stats() -> dict:
    """Aggregate stats for admin dashboard."""
    if _use_firestore():
        session_rows = list_sessions(limit=10000)
        total_sessions = len(session_rows)
        total_turns = sum(int(row.get("turn_count", 0) or 0) for row in session_rows)
        avg_turns = (total_turns / total_sessions) if total_sessions else 0
        by_sector: dict[str, int] = {}
        by_stage: dict[str, int] = {}
        by_type: dict[str, int] = {}
        cutoff_7_days = datetime.now(timezone.utc).timestamp() - (86400 * 7)
        recent = 0
        for row in session_rows:
            sector = row.get("sector", "unknown")
            stage = row.get("stage", "unknown")
            founder_type = row.get("founder_type", "unknown")
            by_sector[sector] = by_sector.get(sector, 0) + 1
            by_stage[stage] = by_stage.get(stage, 0) + 1
            by_type[founder_type] = by_type.get(founder_type, 0) + 1
            try:
                last_active = datetime.fromisoformat((row.get("last_active") or "").replace("Z", "+00:00"))
                if last_active.timestamp() >= cutoff_7_days:
                    recent += 1
            except ValueError:
                continue
        return {
            "total_sessions": total_sessions,
            "total_turns": total_turns,
            "avg_turns_per_session": round(avg_turns, 1),
            "sessions_last_7_days": recent,
            "by_sector": by_sector,
            "by_stage": by_stage,
            "by_founder_type": by_type,
        }

    with _conn() as con:
        total_sessions = con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        total_turns = con.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
        avg_turns = (total_turns / total_sessions) if total_sessions else 0

        by_sector = dict(con.execute("SELECT sector, COUNT(*) FROM sessions GROUP BY sector").fetchall())
        by_stage = dict(con.execute("SELECT stage, COUNT(*) FROM sessions GROUP BY stage").fetchall())
        by_type = dict(con.execute("SELECT founder_type, COUNT(*) FROM sessions GROUP BY founder_type").fetchall())
        recent = con.execute(
            "SELECT COUNT(*) FROM sessions WHERE last_active >= datetime('now', '-7 days')"
        ).fetchone()[0]

    return {
        "total_sessions": total_sessions,
        "total_turns": total_turns,
        "avg_turns_per_session": round(avg_turns, 1),
        "sessions_last_7_days": recent,
        "by_sector": by_sector,
        "by_stage": by_stage,
        "by_founder_type": by_type,
    }


def export_jsonl(filename: str | None = None) -> tuple[str, int]:
    """Export all sessions as JSONL for fine-tuning."""
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if filename is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"finetune_{ts}.jsonl"
    out_path = EXPORTS_DIR / filename

    sessions = list_sessions(limit=10000)
    written = 0

    with out_path.open("w") as fh:
        for session in sessions:
            turns = get_session_turns(session["id"])
            if len(turns) < 4:
                continue
            messages = []
            for turn in turns:
                if turn["role"] in ("user", "assistant"):
                    messages.append({"role": turn["role"], "content": turn["content"]})
            if messages:
                fh.write(json.dumps({"messages": messages}) + "\n")
                written += 1

    return str(out_path), written


def persistence_status() -> dict[str, Any]:
    return {
        "backend": "firestore" if _use_firestore() else "sqlite",
        "dataDir": str(DATA_DIR),
        "firestoreCollectionPrefix": FIRESTORE_COLLECTION_PREFIX if _use_firestore() else "",
        "bigQuery": bigquery_analytics.status(),
    }
