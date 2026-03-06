import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { ChatTurn, CoverageItem, ResponseProfile, SessionPayload, SessionSummary, UploadSummary } from "../../app/types";
import { streamChat } from "../../lib/api/client";
import { ChatMessageList } from "./ChatMessageList";
import { Composer } from "./Composer";

type Props = {
  session: SessionPayload;
  recentSessions: SessionSummary[];
  setSession: (updater: (previous: SessionPayload) => SessionPayload) => void;
  onOpenSession: (sessionId: string) => Promise<void>;
  onNewSession: () => void;
  onExitSession: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
};

type MobilePane = "chat" | "coverage";

const SECTION_META: Record<string, { title: string; hint: string }> = {
  Problem: {
    title: "Problem clarity",
    hint: "Who feels this pain, how often, and what it costs.",
  },
  Solution: {
    title: "Solution",
    hint: "What you are building and why it works better.",
  },
  Market: {
    title: "Customer + market",
    hint: "Your first segment, why they care, and why now.",
  },
  "Business Model": {
    title: "Profit model",
    hint: "What users may pay for and what it costs to deliver.",
  },
  Traction: {
    title: "Validation",
    hint: "Interviews, tests, pilots, or early signs of pull.",
  },
  Team: {
    title: "Team",
    hint: "Why this team can execute and what gap remains.",
  },
  Ask: {
    title: "Next plan",
    hint: "Near-term milestone, timeline, and what support is needed.",
  },
};

function sectionMeta(section: string) {
  return SECTION_META[section] ?? { title: section, hint: "Sharpen this section with clearer evidence." };
}

function coverageStatus(score: number) {
  if (score < 25) {
    return "Open";
  }
  if (score < 50) {
    return "Building";
  }
  if (score < 75) {
    return "Clearer";
  }
  return "Strong";
}

export function ChatScreen({
  session,
  recentSessions,
  setSession,
  onOpenSession,
  onNewSession,
  onExitSession,
  theme,
  onToggleTheme,
}: Props) {
  const navigate = useNavigate();
  const [draft, setDraft] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [streamingAssistant, setStreamingAssistant] = useState("");
  const [pending, setPending] = useState(false);
  const [mobilePane, setMobilePane] = useState<MobilePane>("chat");
  const [statusLine, setStatusLine] = useState("Local-first mentoring");

  const coverageSummary = useMemo(
    () => session.coverage.reduce((acc, item) => acc + item.score, 0) / Math.max(session.coverage.length, 1),
    [session.coverage],
  );
  const coverageSections = useMemo(
    () =>
      session.coverage.map((item) => ({
        ...item,
        meta: sectionMeta(item.section),
        status: coverageStatus(item.score),
      })),
    [session.coverage],
  );
  const nextGapMeta = useMemo(() => sectionMeta(session.nextGap), [session.nextGap]);

  const submit = async (chipText?: string) => {
    const message = (chipText ?? draft).trim();
    if (!message && !selectedFile) {
      return;
    }

    const displayMessage = message
      ? selectedFile
        ? `${message}\n\n[Attached ${selectedFile.name}]`
        : message
      : `[Attached ${selectedFile?.name}]`;

    const optimisticUserTurn: ChatTurn = { role: "user", content: displayMessage };
    const priorHistory = session.history;

    setSession((previous) => ({
      ...previous,
      history: [...previous.history, optimisticUserTurn],
    }));

    setDraft("");
    setPending(true);
    setStreamingAssistant("");

    try {
      await streamChat({
        sessionId: session.sessionId,
        message,
        responseProfile: session.responseProfile,
        file: selectedFile,
        handlers: {
          onMeta: (data) => {
            const profile = (data.responseProfile as ResponseProfile) ?? session.responseProfile;
            const model = (data.model as string | undefined) ?? "local model";
            const fallbackUsed = Boolean(data.fallbackUsed);
            setStatusLine(fallbackUsed ? `Balanced fell back to ${model}` : `${profile.toUpperCase()} · ${model}`);
          },
          onDelta: (delta) => {
            setStreamingAssistant((current) => current + delta);
          },
          onDone: (data) => {
            const assistantMessage = (data.message as string) ?? "";
            const timings = data.timings as Record<string, number> | undefined;
            setSession((previous) => ({
              ...previous,
              history: [...previous.history, { role: "assistant", content: assistantMessage }],
              state: data.state as SessionPayload["state"],
              chips: data.chips as string[],
              coverage: data.coverage as CoverageItem[],
              nextGap: data.nextGap as string,
              responseProfile: (data.responseProfile as ResponseProfile) ?? previous.responseProfile,
              activeUploads: data.activeUploads as UploadSummary[],
            }));
            if (timings?.firstTokenSeconds !== undefined) {
              setStatusLine(
                `${((data.responseProfile as ResponseProfile) ?? session.responseProfile).toUpperCase()} · first token ${timings.firstTokenSeconds}s`,
              );
            }
            setStreamingAssistant("");
            setSelectedFile(null);
          },
          onError: (error) => {
            setStatusLine(error);
            setSession((previous) => ({
              ...previous,
              history: priorHistory,
            }));
            setStreamingAssistant("");
          },
        },
      });
    } catch (error) {
      setStatusLine(error instanceof Error ? error.message : "Failed to talk to backend");
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="app-shell">
      <aside className="left-rail">
        <div>
          <div className="brand-lockup">
            <span className="brand-dot" />
            <div>
              <strong>Vishwakarma</strong>
              <p>VK · pitch mentor</p>
            </div>
          </div>

          <div className="rail-card">
            <span className="rail-label">Response profile</span>
            <div className="segmented">
              {(["speed", "balanced"] as ResponseProfile[]).map((profile) => (
                <button
                  key={profile}
                  type="button"
                  className={session.responseProfile === profile ? "segment active" : "segment"}
                  onClick={() => setSession((previous) => ({ ...previous, responseProfile: profile }))}
                >
                  {profile === "speed" ? "Speed" : "Balanced"}
                </button>
              ))}
            </div>
          </div>

          <div className="rail-card">
            <span className="rail-label">Session</span>
            <dl className="meta-list">
              <div>
                <dt>Mode</dt>
                <dd>{session.state.mode.replace(/_/g, " ")}</dd>
              </div>
              <div>
                <dt>Stage</dt>
                <dd>{session.state.stage}</dd>
              </div>
              <div>
                <dt>Coverage</dt>
                <dd>{Math.round(coverageSummary)}%</dd>
              </div>
              <div>
                <dt>Next gap</dt>
                <dd>{nextGapMeta.title}</dd>
              </div>
            </dl>
          </div>

          <div className="rail-card">
            <div className="rail-stack-head">
              <span className="rail-label">Sessions</span>
              <button type="button" className="ghost-button compact" onClick={onNewSession}>
                New
              </button>
            </div>
            <div className="session-list">
              {recentSessions.slice(0, 8).map((item) => (
                <button
                  key={item.sessionId}
                  type="button"
                  className={item.sessionId === session.sessionId ? "session-card active" : "session-card"}
                  onClick={() => void onOpenSession(item.sessionId)}
                >
                  <strong>{item.title}</strong>
                  <span>{item.subtitle}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="rail-footer">
          <button type="button" className="ghost-button" onClick={onToggleTheme}>
            {theme === "light" ? "Dark theme" : "Light theme"}
          </button>
          <button type="button" className="ghost-button" onClick={onNewSession}>
            Start new session
          </button>
          <button type="button" className="ghost-button" onClick={() => navigate(`/outline/${session.sessionId}`)}>
            Open outline
          </button>
          <button type="button" className="ghost-button" onClick={() => navigate("/admin")}>
            Admin
          </button>
          <button type="button" className="ghost-button" onClick={onExitSession}>
            Exit session
          </button>
        </div>
      </aside>

      <main className={mobilePane === "chat" ? "main-pane mobile-chat" : "main-pane mobile-coverage"}>
        <header className="pane-header">
          <div>
            <span className="eyebrow">Vishwakarma live</span>
            <h2>{session.state.company_name || "Mentor Console"}</h2>
          </div>
          <div className="status-stack">
            <span>{statusLine}</span>
            <div className="header-actions">
              <button type="button" className="ghost-button compact" onClick={onNewSession}>
                New
              </button>
              <button type="button" className="ghost-button compact" onClick={() => navigate(`/outline/${session.sessionId}`)}>
                Outline
              </button>
              <button type="button" className="ghost-button compact" onClick={() => navigate("/admin")}>
                Admin
              </button>
              <button type="button" className="ghost-button compact" onClick={onExitSession}>
                Exit session
              </button>
            </div>
            {session.activeUploads.length > 0 && <small>{session.activeUploads.length} active uploads</small>}
          </div>
        </header>

        {mobilePane === "chat" ? (
          <>
            <div className="chat-panel">
              <ChatMessageList history={session.history} streamingAssistant={streamingAssistant} />
              <div className="chip-row">
                {session.chips.map((chip) => (
                  <button key={chip} type="button" className="chip-button" onClick={() => submit(chip)} disabled={pending}>
                    {chip}
                  </button>
                ))}
              </div>
              <Composer
                value={draft}
                onChange={setDraft}
                onSubmit={() => void submit()}
                pending={pending}
                selectedFile={selectedFile}
                onFileSelected={setSelectedFile}
              />
            </div>
          </>
        ) : (
          <div className="mobile-coverage-panel">
            <div className="drawer-card">
              <span className="rail-label">Deck progress</span>
              <div className="focus-card">
                <span className="focus-tag">Next focus</span>
                <strong>{nextGapMeta.title}</strong>
                <p>{nextGapMeta.hint}</p>
              </div>
              <div className="coverage-list">
                {coverageSections.map((item) => (
                  <div key={item.section} className="coverage-item deck-item">
                    <div className="coverage-head">
                      <strong>{item.meta.title}</strong>
                      <span>{item.status}</span>
                    </div>
                    <small className="deck-hint">{item.meta.hint}</small>
                    <div className="coverage-bar">
                      <div style={{ width: `${item.score}%` }} />
                    </div>
                    <small>{item.score}% covered</small>
                  </div>
                ))}
              </div>
            </div>

            <div className="drawer-card">
              <span className="rail-label">Files in context</span>
              {session.activeUploads.length === 0 ? (
                <p className="muted-copy">No files added yet.</p>
              ) : (
                <ul className="upload-list">
                  {session.activeUploads.map((upload) => (
                    <li key={`${upload.name}-${upload.uploadedAt}`}>
                      <strong>{upload.name}</strong>
                      <span>{upload.docType}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </main>

      <aside className="right-drawer">
        <div className="drawer-card">
          <span className="rail-label">Deck progress</span>
          <div className="focus-card">
            <span className="focus-tag">Next focus</span>
            <strong>{nextGapMeta.title}</strong>
            <p>{nextGapMeta.hint}</p>
          </div>
          <div className="coverage-list">
            {coverageSections.map((item) => (
              <div key={item.section} className="coverage-item deck-item">
                <div className="coverage-head">
                  <strong>{item.meta.title}</strong>
                  <span>{item.status}</span>
                </div>
                <small className="deck-hint">{item.meta.hint}</small>
                <div className="coverage-bar">
                  <div style={{ width: `${item.score}%` }} />
                </div>
                <small>{item.score}% covered</small>
              </div>
            ))}
          </div>
        </div>

        <div className="drawer-card">
          <span className="rail-label">Files in context</span>
          {session.activeUploads.length === 0 ? (
            <p className="muted-copy">Attach a deck, notes, or research. VK will pull only the relevant parts.</p>
          ) : (
            <ul className="upload-list">
              {session.activeUploads.map((upload) => (
                <li key={`${upload.name}-${upload.uploadedAt}`}>
                  <strong>{upload.name}</strong>
                  <span>{upload.docType}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>

      <nav className="mobile-nav">
        <button
          type="button"
          className={mobilePane === "chat" ? "mobile-tab active" : "mobile-tab"}
          onClick={() => setMobilePane("chat")}
        >
          Chat
        </button>
        <button
          type="button"
          className={mobilePane === "coverage" ? "mobile-tab active" : "mobile-tab"}
          onClick={() => setMobilePane("coverage")}
        >
          Coverage
        </button>
        <button type="button" className="mobile-tab" onClick={() => navigate(`/outline/${session.sessionId}`)}>
          Outline
        </button>
      </nav>
    </div>
  );
}
