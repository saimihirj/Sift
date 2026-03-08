import { useEffect, useState } from "react";

import type { SessionSummary } from "../../app/types";

type Props = {
  isOpen: boolean;
  sessions: SessionSummary[];
  currentSessionId: string;
  clearing: boolean;
  onClose: () => void;
  onOpenSession: (sessionId: string) => void;
  onClearHistory: () => void;
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

export function SessionSidebar({ isOpen, sessions, currentSessionId, clearing, onClose, onOpenSession, onClearHistory }: Props) {
  const [confirmClear, setConfirmClear] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      setConfirmClear(false);
    }
  }, [isOpen, sessions.length]);

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
        {sessions.length === 0 ? <p className="muted-copy">Your recent sessions will appear here after the first run.</p> : null}
        {sessions.length > 0 ? (
          <>
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
            <div className="floating-actions">
              <button type="button" className="ghost-button" onClick={() => setConfirmClear(false)}>
                Cancel
              </button>
              <button
                type="button"
                className={confirmClear ? "solid-button" : "ghost-button"}
                onClick={() => {
                  if (!confirmClear) {
                    setConfirmClear(true);
                    return;
                  }
                  onClearHistory();
                  setConfirmClear(false);
                }}
                disabled={clearing}
              >
                {clearing ? "Clearing..." : confirmClear ? "Confirm clear history" : "Clear history"}
              </button>
            </div>
          </>
        ) : null}
      </aside>
    </div>
  );
}
