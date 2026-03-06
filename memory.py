"""Session and analytics persistence for Vishwakarma.

Uses SQLite (stdlib — no extra install). Stores:
  sessions         — founder profile + coverage state per user
  turns            — every conversation message
  analytics_events — page views, session starts, chat completions, uploads, etc.

Also handles JSONL export for fine-tuning.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


DATA_DIR = Path(os.environ.get("VK_DATA_DIR", "data"))
DB_PATH = DATA_DIR / "sessions.db"
EXPORTS_DIR = DATA_DIR / "exports"
_DB_READY = False


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


def _raw_conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con


def _conn() -> sqlite3.Connection:
    global _DB_READY
    if not _DB_READY:
        init_db()
    return _raw_conn()


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
    with _raw_conn() as con:
        con.executescript(_SCHEMA)

        session_columns = {row["name"] for row in con.execute("PRAGMA table_info(sessions)").fetchall()}
        if "display_name" not in session_columns:
            con.execute("ALTER TABLE sessions ADD COLUMN display_name TEXT DEFAULT ''")
        if "session_type" not in session_columns:
            con.execute("ALTER TABLE sessions ADD COLUMN session_type TEXT DEFAULT 'mentor'")
        if "question_budget" not in session_columns:
            con.execute("ALTER TABLE sessions ADD COLUMN question_budget INTEGER DEFAULT 15")
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
    with _conn() as con:
        con.execute(
            """INSERT INTO sessions
               (id, user_identifier, display_name, session_type, founder_type, sector, stage, mode,
                question_budget, provider, model, website_url, company_name, coverage_json, facts_json,
                metadata_json, created_at, last_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                user_identifier.strip().lower() if user_identifier else "",
                (display_name or "").strip(),
                session_type or "mentor",
                getattr(state, "founder_type", "unknown"),
                getattr(state, "sector", "unknown"),
                getattr(state, "stage", "unknown"),
                getattr(state, "mode", "think_it_through"),
                question_budget or 15,
                provider or "ollama",
                model or "",
                (website_url or "").strip(),
                getattr(state, "company_name", ""),
                json.dumps(getattr(state, "coverage", {})),
                json.dumps(getattr(state, "facts", {})),
                json.dumps(metadata or {}),
                now,
                now,
            ),
        )
    return session_id


def load_session(user_identifier: str) -> dict | None:
    """Look up the most recent session for a user identifier."""
    if not user_identifier:
        return None
    key = user_identifier.strip().lower()
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


def update_session(session_id: str, state) -> None:
    """Sync coverage, facts, company_name and last_active back to the DB."""
    if not session_id:
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
               last_active   = ?
               WHERE id = ?""",
            (
                json.dumps(getattr(state, "coverage", {})),
                json.dumps(getattr(state, "facts", {})),
                getattr(state, "company_name", ""),
                getattr(state, "sector", "unknown"),
                getattr(state, "stage", "unknown"),
                getattr(state, "founder_type", "unknown"),
                getattr(state, "mode", "think_it_through"),
                datetime.now(timezone.utc).isoformat(),
                session_id,
            ),
        )


def update_session_runtime(session_id: str, provider: str, model: str) -> None:
    """Persist non-secret runtime selection for a session."""
    if not session_id:
        return
    with _conn() as con:
        con.execute(
            """UPDATE sessions SET
               provider = ?,
               model = ?,
               last_active = ?
               WHERE id = ?""",
            (
                provider or "ollama",
                model or "",
                datetime.now(timezone.utc).isoformat(),
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
    with _conn() as con:
        con.execute(
            """UPDATE sessions SET metadata_json = ?, last_active = ? WHERE id = ?""",
            (
                json.dumps(metadata or {}),
                datetime.now(timezone.utc).isoformat(),
                session_id,
            ),
        )


def store_turn(session_id: str, role: str, content: str, metadata: dict | None = None) -> None:
    """Append one conversation turn."""
    if not session_id:
        return
    with _conn() as con:
        con.execute(
            """INSERT INTO turns (session_id, role, content, metadata_json, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (
                session_id,
                role,
                content,
                json.dumps(metadata or {}),
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def get_session_turns(session_id: str) -> list[dict]:
    """Return all turns for a session, ordered by insertion."""
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
    with _conn() as con:
        con.execute(
            """INSERT INTO analytics_events
               (client_id, session_id, display_name, event_type, pathname, metadata_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                (client_id or "").strip().lower(),
                session_id,
                (display_name or "").strip(),
                event_type,
                pathname,
                json.dumps(metadata or {}),
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def list_recent_events(limit: int = 100) -> list[dict]:
    """Return the most recent analytics events."""
    with _conn() as con:
        rows = con.execute(
            """SELECT client_id, session_id, display_name, event_type, pathname, metadata_json, created_at
               FROM analytics_events
               ORDER BY id DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

    events = []
    for row in rows:
        item = dict(row)
        raw_metadata = item.pop("metadata_json", "{}") or "{}"
        try:
            item["metadata"] = json.loads(raw_metadata)
        except json.JSONDecodeError:
            item["metadata"] = {}
        events.append(item)
    return events


def _average_event_metric(event_type: str, metric_key: str) -> float:
    values: list[float] = []
    for event in list_recent_events(limit=500):
        if event["event_type"] != event_type:
            continue
        value = event.get("metadata", {}).get(metric_key)
        if isinstance(value, (int, float)):
            values.append(float(value))
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _most_common_event_value(event_type: str, metric_key: str) -> str:
    counts: dict[str, int] = {}
    for event in list_recent_events(limit=1000):
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
    with _conn() as con:
        total_sessions = con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        total_turns = con.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
        total_events = con.execute("SELECT COUNT(*) FROM analytics_events").fetchone()[0]
        unique_visitors = con.execute(
            "SELECT COUNT(DISTINCT client_id) FROM analytics_events WHERE client_id != ''"
        ).fetchone()[0]
        sessions_last_7_days = con.execute(
            "SELECT COUNT(*) FROM sessions WHERE last_active >= datetime('now', '-7 days')"
        ).fetchone()[0]
        events_last_24_hours = con.execute(
            "SELECT COUNT(*) FROM analytics_events WHERE created_at >= datetime('now', '-1 day')"
        ).fetchone()[0]
        outline_opens = con.execute(
            "SELECT COUNT(*) FROM analytics_events WHERE event_type = 'outline_opened'"
        ).fetchone()[0]
        uploads = con.execute(
            "SELECT COUNT(*) FROM analytics_events WHERE event_type = 'file_uploaded'"
        ).fetchone()[0]
        chat_completions = con.execute(
            "SELECT COUNT(*) FROM analytics_events WHERE event_type = 'chat_completed'"
        ).fetchone()[0]
        evaluator_sessions = con.execute(
            "SELECT COUNT(*) FROM sessions WHERE session_type = 'evaluator'"
        ).fetchone()[0]
        provider_breakdown = dict(
            con.execute(
                "SELECT provider, COUNT(*) FROM sessions WHERE session_type = 'evaluator' GROUP BY provider"
            ).fetchall()
        )
        by_event = dict(
            con.execute("SELECT event_type, COUNT(*) FROM analytics_events GROUP BY event_type").fetchall()
        )

    evaluator_completions = by_event.get("evaluator_completed", 0)
    average_success_score = _average_event_metric("evaluator_completed", "overallScore")
    completion_rate = round((evaluator_completions / evaluator_sessions) * 100.0, 1) if evaluator_sessions else 0.0

    return {
        "totalSessions": total_sessions,
        "totalTurns": total_turns,
        "totalEvents": total_events,
        "uniqueVisitors": unique_visitors,
        "sessionsLast7Days": sessions_last_7_days,
        "eventsLast24Hours": events_last_24_hours,
        "outlineOpens": outline_opens,
        "uploads": uploads,
        "chatCompletions": chat_completions,
        "averageFirstTokenSeconds": _average_event_metric("chat_completed", "firstTokenSeconds"),
        "averageTotalSeconds": _average_event_metric("chat_completed", "totalSeconds"),
        "evaluatorSessions": evaluator_sessions,
        "evaluatorCompletions": evaluator_completions,
        "evaluatorCompletionRate": completion_rate,
        "averageSuccessScore": average_success_score,
        "averageEvaluatorScore": average_success_score,
        "websiteFetchFailures": by_event.get("website_fetch_failed", 0),
        "dropOffQuestion": _most_common_event_value("evaluator_answered", "questionId"),
        "providerBreakdown": provider_breakdown,
        "eventBreakdown": by_event,
    }


def get_stats() -> dict:
    """Aggregate stats for admin dashboard."""
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
