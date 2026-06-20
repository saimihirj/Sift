import { useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";

import type { AdminEvent, AdminOverview, SessionSummary } from "../../app/types";
import { getAdminEvents, getAdminOverview, deleteSession, getSessionTranscript } from "../../lib/api/client";

export function AdminObservability() {
  const { adminToken } = useOutletContext<{ adminToken: string }>();

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

  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [events, setEvents] = useState<AdminEvent[]>([]);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [status, setStatus] = useState("Loading admin data...");
  const [transcriptData, setTranscriptData] = useState<{role: string, content: string}[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    setStatus("Loading admin data...");
    Promise.all([getAdminOverview(adminToken), getAdminEvents(adminToken)])
      .then(([overviewResponse, eventsResponse]) => {
        if (cancelled) return;
        setOverview(overviewResponse);
        setEvents(eventsResponse.events.slice(0, 18));
        setSessions(eventsResponse.sessions);
        setStatus("Admin mode");
      })
      .catch((error) => {
        if (cancelled) return;
        setStatus(error instanceof Error ? error.message : "Failed to load admin data");
      });
    return () => {
      cancelled = true;
    };
  }, [adminToken]);

  const handleDeleteSession = async (sessionId: string) => {
    if (!window.confirm("Are you sure you want to delete this session entirely?")) return;
    try {
      await deleteSession(sessionId, adminToken);
      setStatus("Session deleted");
      setSessions(s => s.filter(x => x.sessionId !== sessionId));
    } catch (e: any) {
      setStatus("Failed to delete session: " + e.message);
    }
  };

  const handleViewTranscript = async (sessionId: string) => {
    try {
      setStatus("Loading transcript...");
      const t = await getSessionTranscript(sessionId, adminToken);
      setTranscriptData(t);
      setStatus("Transcript loaded");
    } catch (e: any) {
      setStatus("Failed to load transcript: " + e.message);
    }
  };

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
    <div className="observability-shell" style={{ height: "100%", overflowY: "auto", display: "flex", flexDirection: "column" }}>
      <header className="pane-header">
        <div>
          <span className="eyebrow">Admin Portal</span>
          <h2>Observability & Logs</h2>
        </div>
        <div className="status-stack">
          <span className="status-dot green" />
          <span className="eyebrow">System Active</span>
        </div>
      </header>

      <div className="admin-main" style={{ padding: "1.5rem", flex: 1 }}>
        <section className="admin-grid">
          {cards.map((card) => (
            <article key={card.label} className="admin-metric">
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
                  <div key={session.sessionId} className="admin-row" style={{ alignItems: "center" }}>
                    <div style={{ flex: 1 }}>
                      <strong>{session.title}</strong>
                      <p>{session.subtitle}</p>
                    </div>
                    <div className="admin-row-meta" style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
                      <span>{session.turnCount} turns</span>
                      <small>{session.lastActive ? new Date(session.lastActive).toLocaleString() : "-"}</small>
                      <div style={{ display: "flex", gap: "8px", marginTop: "4px" }}>
                        <button type="button" onClick={() => handleViewTranscript(session.sessionId)} className="ghost-button compact" style={{ fontSize: "11px", padding: "2px 8px" }}>View</button>
                        <button type="button" onClick={() => handleDeleteSession(session.sessionId)} className="ghost-button compact" style={{ fontSize: "11px", padding: "2px 8px", color: "var(--status-error)" }}>Delete</button>
                      </div>
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

            <article className="outline-card admin-card">
              <div className="admin-card-head">
                <strong>Observability & Control</strong>
                <span className="rail-label">External APM Tools</span>
              </div>
              <div className="admin-list" style={{ padding: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
                <a href="https://smith.langchain.com" target="_blank" rel="noreferrer" className="ghost-button" style={{ justifyContent: "center" }}>
                  Open LangSmith (LLM Tracing)
                </a>
                <a href="https://app.posthog.com" target="_blank" rel="noreferrer" className="ghost-button" style={{ justifyContent: "center" }}>
                  Open PostHog (Analytics)
                </a>
              </div>
            </article>
          </div>
        </section>
      </div>

      {transcriptData && (
        <div className="floating-panel is-open align-right" style={{ zIndex: 9999 }}>
          <button type="button" className="floating-backdrop is-open" onClick={() => setTranscriptData(null)} aria-label="Close transcript" />
          <aside className="floating-card is-open" style={{ width: "600px", maxWidth: "90vw", display: "flex", flexDirection: "column" }}>
            <div className="floating-head" style={{ borderBottom: "1px solid var(--border)", paddingBottom: "16px", marginBottom: "16px" }}>
              <div>
                <span className="rail-label">Transcript View</span>
                <strong>Raw LLM Conversation</strong>
              </div>
              <button type="button" className="ghost-button compact" onClick={() => setTranscriptData(null)}>
                Close
              </button>
            </div>
            <div style={{ overflowY: "auto", flex: 1, paddingRight: "8px", display: "flex", flexDirection: "column", gap: "16px" }}>
              {transcriptData.map((t, idx) => (
                <div key={idx} style={{ 
                  padding: "12px", 
                  background: t.role === "user" ? "var(--surface-sunken)" : "var(--surface-raised)", 
                  borderRadius: "8px",
                  border: t.role === "user" ? "1px solid var(--border)" : "1px solid var(--accent)",
                  whiteSpace: "pre-wrap",
                  fontFamily: "var(--font-mono)",
                  fontSize: "13px"
                }}>
                  <strong style={{ display: "block", marginBottom: "8px", color: t.role === "user" ? "var(--fg-muted)" : "var(--accent)" }}>
                    {t.role.toUpperCase()}
                  </strong>
                  {t.content}
                </div>
              ))}
              {transcriptData.length === 0 && <p className="muted-copy">No messages in transcript.</p>}
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
