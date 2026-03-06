import type { SessionSummary } from "../../app/types";

type Props = {
  isOpen: boolean;
  sessions: SessionSummary[];
  currentSessionId: string;
  onClose: () => void;
  onOpenSession: (sessionId: string) => void;
};

function formatTime(raw?: string | null): string {
  if (!raw) {
    return "No activity yet";
  }
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) {
    return "Recent";
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed);
}

export function SessionSidebar({ isOpen, sessions, currentSessionId, onClose, onOpenSession }: Props) {
  return (
    <div className={isOpen ? "floating-panel is-open" : "floating-panel"} aria-hidden={!isOpen}>
      <button type="button" className={isOpen ? "floating-backdrop is-open" : "floating-backdrop"} onClick={onClose} aria-label="Close sessions" />
      <aside className={isOpen ? "floating-card is-open" : "floating-card"}>
        <div className="floating-head">
          <div>
            <span className="rail-label">Sessions</span>
            <strong>Resume without clutter</strong>
          </div>
          <button type="button" className="ghost-button compact" onClick={onClose}>
            Close
          </button>
        </div>
        {sessions.length === 0 ? (
          <p className="muted-copy">Your recent sessions will appear here after the first run.</p>
        ) : (
          <div className="session-list floating-list">
            {sessions.map((item) => (
              <button
                key={item.sessionId}
                type="button"
                className={item.sessionId === currentSessionId ? "session-card active" : "session-card"}
                onClick={() => onOpenSession(item.sessionId)}
              >
                <strong>{item.title}</strong>
                <span>{item.subtitle}</span>
                <span>
                  {item.sessionType === "evaluator" ? "Evaluate" : "Ideate"} · {formatTime(item.lastActive)}
                </span>
              </button>
            ))}
          </div>
        )}
      </aside>
    </div>
  );
}
