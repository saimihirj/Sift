import { useMemo, useState } from "react";

import type { SessionSummary } from "../../app/types";

type Props = {
  displayName: string;
  onDisplayNameChange: (value: string) => void;
  onContinue: () => void;
  recentSessions: SessionSummary[];
  onResume: (sessionId: string) => Promise<void>;
};

const HIGHLIGHTS = [
  {
    title: "Problem first",
    note: "Push the real pain, user, and evidence before features.",
  },
  {
    title: "Simple mentoring",
    note: "VK adapts the questions for students, operators, and founders.",
  },
  {
    title: "Clear next steps",
    note: "Every session closes with a tighter action plan.",
  },
];

export function LandingScreen({
  displayName,
  onDisplayNameChange,
  onContinue,
  recentSessions,
  onResume,
}: Props) {
  const [authNote, setAuthNote] = useState("Name is required. Google and Apple sign-in need OAuth setup before they can be switched on.");
  const canContinue = displayName.trim().length > 0;
  const sessions = useMemo(() => recentSessions.slice(0, 4), [recentSessions]);

  const handleOAuthIntent = (provider: "google" | "apple") => {
    if (provider === "google") {
      setAuthNote("Google sign-in is possible after adding OAuth credentials and redirect URLs.");
      return;
    }
    setAuthNote("Apple sign-in needs Apple Developer setup, so it is not part of the local MVP yet.");
  };

  return (
    <section className="landing-shell">
      <div className="landing-panel">
        <div className="landing-hero">
          <span className="eyebrow">Vishwakarma · VK</span>
          <h1>Pitch clarity before pitch polish.</h1>
          <p>
            A focused mentor for founders who need sharper problem framing, cleaner validation, and tighter next
            steps.
          </p>
        </div>

        <div className="landing-highlight-grid">
          {HIGHLIGHTS.map((item) => (
            <article key={item.title} className="landing-highlight">
              <strong>{item.title}</strong>
              <p>{item.note}</p>
            </article>
          ))}
        </div>
      </div>

      <aside className="landing-card">
        <div className="landing-card-head">
          <div>
            <span className="eyebrow">Start</span>
            <h2>Enter VK</h2>
          </div>
          <span className="landing-badge">Mandatory name</span>
        </div>

        <label className="identity-field">
          <span className="rail-label">Name</span>
          <input
            type="text"
            value={displayName}
            onChange={(event) => onDisplayNameChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && canContinue) {
                event.preventDefault();
                onContinue();
              }
            }}
            placeholder="Your name"
            aria-required="true"
          />
        </label>

        <div className="landing-actions">
          <button type="button" className="solid-button" onClick={onContinue} disabled={!canContinue}>
            Continue with name
          </button>
          <div className="social-row">
            <button type="button" className="ghost-button social-button" onClick={() => handleOAuthIntent("google")}>
              Continue with Google
            </button>
            <button type="button" className="ghost-button social-button" onClick={() => handleOAuthIntent("apple")}>
              Continue with Apple
            </button>
          </div>
          <small className="muted-copy">{authNote}</small>
        </div>

        {sessions.length > 0 && (
          <div className="resume-panel landing-resume">
            <div className="resume-head">
              <span className="rail-label">Recent sessions</span>
              <small>Resume without starting over</small>
            </div>
            <div className="resume-list">
              {sessions.map((session) => (
                <button
                  key={session.sessionId}
                  type="button"
                  className="resume-card"
                  onClick={() => void onResume(session.sessionId)}
                >
                  <strong>{session.title}</strong>
                  <span>{session.subtitle}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </aside>
    </section>
  );
}
