import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { SignalLockup } from "../../app/SignalBrand";
import type { AdminEvent, AdminOverview, SessionSummary, ThemeMode } from "../../app/types";
import { ThemePicker } from "../../app/ThemePicker";
import { getAdminEvents, getAdminOverview } from "../../lib/api/client";

const ADMIN_TOKEN_STORAGE_KEY = "vishwakarma-admin-token";

type Props = {
  theme: ThemeMode;
  onThemeChange: (theme: ThemeMode) => void;
};

type MetricCard = {
  label: string;
  value: string;
};

function metricCards(overview: AdminOverview | null): MetricCard[] {
  if (!overview) {
    return [];
  }
  return [
    { label: "Unique visitors", value: String(overview.uniqueVisitors) },
    { label: "Total sessions", value: String(overview.totalSessions) },
    { label: "Evaluate sessions", value: String(overview.evaluatorSessions) },
    { label: "Completion rate", value: `${overview.evaluatorCompletionRate}%` },
    { label: "Avg success", value: `${overview.averageSuccessScore}` },
    { label: "Avg first token", value: `${overview.averageFirstTokenSeconds}s` },
    { label: "Uploads", value: String(overview.uploads) },
    { label: "Website fails", value: String(overview.websiteFetchFailures) },
  ];
}

export function AdminScreen({ theme, onThemeChange }: Props) {
  const [token, setToken] = useState(() => localStorage.getItem(ADMIN_TOKEN_STORAGE_KEY) ?? "");
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [events, setEvents] = useState<AdminEvent[]>([]);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [status, setStatus] = useState("Loading admin data...");

  useEffect(() => {
    localStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, token);
  }, [token]);

  useEffect(() => {
    let cancelled = false;
    setStatus("Loading admin data...");
    Promise.all([getAdminOverview(token), getAdminEvents(token)])
      .then(([overviewResponse, eventsResponse]) => {
        if (cancelled) {
          return;
        }
        setOverview(overviewResponse);
        setEvents(eventsResponse.events.slice(0, 18));
        setSessions(eventsResponse.sessions);
        setStatus("Admin mode");
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        setStatus(error instanceof Error ? error.message : "Failed to load admin data");
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const cards = useMemo(() => metricCards(overview), [overview]);
  const eventBreakdown = useMemo(
    () =>
      Object.entries(overview?.eventBreakdown ?? {}).sort((left, right) => right[1] - left[1]),
    [overview],
  );
  const providerBreakdown = useMemo(
    () =>
      Object.entries(overview?.providerBreakdown ?? {}).sort((left, right) => right[1] - left[1]),
    [overview],
  );

  return (
    <div className="outline-shell admin-shell">
      <aside className="left-rail outline-rail">
        <SignalLockup compact className="workspace-lockup" />

        <div className="rail-card">
          <span className="rail-label">Admin mode</span>
          <p className="muted-copy">{status}</p>
        </div>

        <label className="identity-field">
          <span className="rail-label">Admin token</span>
          <input type="password" value={token} onChange={(event) => setToken(event.target.value)} placeholder="Optional locally, recommended in deploy" />
        </label>

        <div className="rail-footer">
          <Link to="/" className="ghost-button">
            Back to app
          </Link>
          <ThemePicker theme={theme} onChange={onThemeChange} />
        </div>
      </aside>

      <main className="outline-main admin-main">
        <section className="admin-grid">
          {cards.map((card) => (
            <article key={card.label} className="drawer-card admin-metric">
              <span className="rail-label">{card.label}</span>
              <strong>{card.value}</strong>
            </article>
          ))}
        </section>

        <section className="admin-dashboard">
          <article className="outline-card admin-card admin-card-large">
            <div className="admin-card-head">
              <strong>Recent activity</strong>
              <span className="rail-label">{events.length} latest signals</span>
            </div>
            <div className="admin-list">
              {events.map((event, index) => (
                <div key={`${event.created_at}-${index}`} className="admin-row">
                  <div>
                    <strong>{event.display_name || event.client_id || "Anonymous visitor"}</strong>
                    <p>{event.event_type.replace(/_/g, " ")}</p>
                  </div>
                  <div className="admin-row-meta">
                    <span>{event.pathname || "-"}</span>
                    <small>{new Date(event.created_at).toLocaleString()}</small>
                  </div>
                </div>
              ))}
            </div>
          </article>

          <div className="admin-stack">
            <article className="outline-card admin-card">
              <div className="admin-card-head">
                <strong>Session feed</strong>
                <span className="rail-label">{sessions.length} recent sessions</span>
              </div>
              <div className="admin-list">
                {sessions.map((session) => (
                  <div key={session.sessionId} className="admin-row">
                    <div>
                      <strong>{session.title}</strong>
                      <p>{session.subtitle}</p>
                    </div>
                    <div className="admin-row-meta">
                      <span>{session.turnCount} turns</span>
                      <small>{session.lastActive ? new Date(session.lastActive).toLocaleString() : "-"}</small>
                    </div>
                  </div>
                ))}
              </div>
            </article>

            <article className="outline-card admin-card">
              <div className="admin-card-head">
                <strong>Runtime signals</strong>
                <span className="rail-label">{overview?.dropOffQuestion || "No drop-off data yet"}</span>
              </div>
              <div className="admin-list">
                {providerBreakdown.map(([label, count]) => (
                  <div key={label} className="admin-row compact-row">
                    <strong>{label}</strong>
                    <span>{count}</span>
                  </div>
                ))}
              </div>
            </article>

            <article className="outline-card admin-card">
              <div className="admin-card-head">
                <strong>Event breakdown</strong>
                <span className="rail-label">What users are doing</span>
              </div>
              <div className="admin-list">
                {eventBreakdown.slice(0, 8).map(([label, count]) => (
                  <div key={label} className="admin-row compact-row">
                    <strong>{label.replace(/_/g, " ")}</strong>
                    <span>{count}</span>
                  </div>
                ))}
              </div>
            </article>
          </div>
        </section>
      </main>
    </div>
  );
}
