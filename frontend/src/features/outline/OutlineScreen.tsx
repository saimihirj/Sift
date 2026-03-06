import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import type { ThemeMode } from "../../app/types";
import { ThemePicker } from "../../app/ThemePicker";
import { getOutline, postAnalyticsEvent } from "../../lib/api/client";

type Props = {
  theme: ThemeMode;
  onThemeChange: (theme: ThemeMode) => void;
  onExitSession: () => void;
  clientId: string;
  displayName: string;
};

export function OutlineScreen({ theme, onThemeChange, onExitSession, clientId, displayName }: Props) {
  const navigate = useNavigate();
  const { sessionId = "" } = useParams();
  const [content, setContent] = useState("Loading outline...");
  const [status, setStatus] = useState("Generating markdown outline");

  useEffect(() => {
    let cancelled = false;
    if (!sessionId) {
      setContent("Session not found.");
      return;
    }
    void getOutline(sessionId)
      .then((response) => {
        if (cancelled) return;
        setContent(response.markdown);
        setStatus(`Generated with ${response.responseProfile.toUpperCase()}`);
        void postAnalyticsEvent({
          eventType: "outline_viewed",
          clientId,
          sessionId,
          displayName,
          pathname: `/outline/${sessionId}`,
          metadata: {
            responseProfile: response.responseProfile,
          },
        }).catch(() => undefined);
      })
      .catch((error) => {
        if (cancelled) return;
        setStatus("Outline unavailable");
        setContent(error instanceof Error ? error.message : "Failed to load outline");
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  return (
    <div className="outline-shell">
      <aside className="left-rail outline-rail">
        <div className="brand-lockup">
          <span className="brand-dot" />
          <div>
            <strong>Signal</strong>
            <p>{status}</p>
          </div>
        </div>
        <div className="rail-footer">
          <button type="button" className="ghost-button" onClick={() => navigate("/")}>
            Back to chat
          </button>
          <button type="button" className="ghost-button" onClick={onExitSession}>
            Exit session
          </button>
          <ThemePicker theme={theme} onChange={onThemeChange} />
        </div>
      </aside>
      <main className="outline-main">
        <article className="outline-card">
          <pre>{content}</pre>
        </article>
      </main>
    </div>
  );
}
