import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import type {
  ChatTurn,
  CoverageItem,
  ProviderOption,
  ResponseProfile,
  SessionPayload,
  SessionSummary,
  ThemeMode,
  UploadSummary,
} from "../../app/types";
import { ThemePicker } from "../../app/ThemePicker";
import { streamChat, updateSessionRuntime } from "../../lib/api/client";
import { loadSessionCredential, saveSessionCredential } from "../../lib/sessionCredentials";
import { RuntimeSidebar } from "../session/RuntimeSidebar";
import { SessionSidebar } from "../session/SessionSidebar";
import { ChatMessageList } from "./ChatMessageList";
import { Composer } from "./Composer";

type Props = {
  session: SessionPayload;
  setSession: (updater: (previous: SessionPayload) => SessionPayload) => void;
  onNewSession: () => void;
  onExitSession: () => void;
  onOpenSession: (sessionId: string) => void | Promise<void>;
  onSessionActivity: () => void;
  onClearHistory: () => void;
  clearingHistory: boolean;
  recentSessions: SessionSummary[];
  providerOptions: ProviderOption[];
  theme: ThemeMode;
  onThemeChange: (theme: ThemeMode) => void;
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

function pitchHealthColor(score: number) {
  if (score >= 60) {
    return "#22c55e";
  }
  if (score >= 35) {
    return "#f59e0b";
  }
  return "#ef4444";
}

function PitchHealthRing({ coverage }: { coverage: CoverageItem[] }) {
  const average = coverage.length
    ? Math.round(coverage.reduce((total, item) => total + item.score, 0) / coverage.length)
    : 0;
  const radius = 26;
  const circumference = 2 * Math.PI * radius;
  const dash = (average / 100) * circumference;
  const color = pitchHealthColor(average);

  return (
    <div className="health-ring-wrap">
      <svg className="health-ring-svg" width="64" height="64" viewBox="0 0 64 64" aria-hidden="true">
        <circle className="track" cx="32" cy="32" r={radius} />
        <circle
          className="fill"
          cx="32"
          cy="32"
          r={radius}
          strokeDasharray={`${dash.toFixed(2)} ${(circumference - dash).toFixed(2)}`}
          style={{ stroke: color }}
        />
      </svg>
      <div className="health-ring-info">
        <span className="health-ring-score" style={{ color }}>{average}%</span>
        <span className="health-ring-label">Pitch health</span>
        <span className="health-ring-sub">{coverage.length} sections tracked</span>
      </div>
    </div>
  );
}

function promptHelper(founderType: string, nextGap: string) {
  if (founderType === "student" || founderType === "professional") {
    if (nextGap === "Problem") {
      return "Easy start: user -> pain -> current workaround.";
    }
    if (nextGap === "Market") {
      return "Easy start: first segment -> why them -> why now.";
    }
    if (nextGap === "Solution") {
      return "Easy start: user outcome -> product -> why better.";
    }
    if (nextGap === "Business Model") {
      return "Easy start: value -> price -> delivery cost.";
    }
    if (nextGap === "Traction") {
      return "Easy start: proof -> learning -> next step.";
    }
  }
  return "";
}

function defaultModelForProvider(providerOptions: ProviderOption[], provider: string, profile: ResponseProfile): string {
  const providerMeta = providerOptions.find((item) => item.key === provider);
  if (!providerMeta) {
    return "";
  }
  return profile === "balanced" ? providerMeta.defaultBalancedModel : providerMeta.defaultSpeedModel;
}

function tokenStatus(runtimeUsage: SessionPayload["runtimeUsage"] | undefined): string {
  const total = runtimeUsage?.last?.totalTokens ?? 0;
  if (!total) {
    return "";
  }
  return `${Math.round(total).toLocaleString()} tok${runtimeUsage?.last?.estimated ? " est." : ""}`;
}

function profileLabel(profile: ResponseProfile): string {
  return profile === "balanced" ? "Sharper" : "Fast";
}

function formatSessionTime(raw?: string | null): string {
  if (!raw) {
    return "Recent";
  }
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) {
    return "Recent";
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  }).format(parsed);
}

function workflowLabel(sessionType: SessionSummary["sessionType"]): string {
  if (sessionType === "evaluator") {
    return "Evaluate";
  }
  if (sessionType === "expert") {
    return "Expert";
  }
  return "Ideate";
}

export function ChatScreen({
  session,
  setSession,
  onNewSession,
  onExitSession,
  onOpenSession,
  onSessionActivity,
  onClearHistory,
  clearingHistory,
  recentSessions,
  providerOptions,
  theme,
  onThemeChange,
}: Props) {
  const navigate = useNavigate();
  const [draft, setDraft] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [streamingAssistant, setStreamingAssistant] = useState("");
  const [pending, setPending] = useState(false);
  const [mobilePane, setMobilePane] = useState<MobilePane>("chat");
  const [statusLine, setStatusLine] = useState("");
  const [sessionsOpen, setSessionsOpen] = useState(false);
  const [runtimeOpen, setRuntimeOpen] = useState(false);
  const [progressOpen, setProgressOpen] = useState(false);
  const [filesOpen, setFilesOpen] = useState(false);
  const [themeOpen, setThemeOpen] = useState(false);
  const [applyingRuntime, setApplyingRuntime] = useState(false);
  const [runtimeProvider, setRuntimeProvider] = useState<SessionPayload["provider"]>(session.provider);
  const [runtimeModel, setRuntimeModel] = useState(session.model);
  const [runtimeApiKey, setRuntimeApiKey] = useState(() => loadSessionCredential(session.sessionId)?.apiKey ?? "");

  useEffect(() => {
    setRuntimeProvider(session.provider);
    setRuntimeModel(session.model);
    setRuntimeApiKey(loadSessionCredential(session.sessionId)?.apiKey ?? "");
    setSessionsOpen(false);
    setRuntimeOpen(false);
    setProgressOpen(false);
    setFilesOpen(false);
    setThemeOpen(false);
  }, [session.sessionId, session.provider, session.model]);

  const selectedProvider = useMemo(
    () => providerOptions.find((item) => item.key === runtimeProvider) ?? providerOptions[0] ?? null,
    [providerOptions, runtimeProvider],
  );
  const requiresClientApiKey = Boolean(selectedProvider?.requiresApiKey && !selectedProvider.serverConfigured);
  const effectiveModel = runtimeModel.trim() || defaultModelForProvider(providerOptions, runtimeProvider, session.responseProfile);

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
  const starterHelper = useMemo(
    () => promptHelper(session.state.founder_type, session.nextGap),
    [session.state.founder_type, session.nextGap],
  );
  const coverageCompactSections = useMemo(() => coverageSections.slice(0, 8), [coverageSections]);
  const visibleChips = useMemo(() => {
    if (session.history.length <= 3) {
      return session.chips;
    }
    return session.chips.slice(0, 3);
  }, [session.chips, session.history.length]);
  const visibleSessions = useMemo(() => recentSessions.slice(0, 6), [recentSessions]);

  const applyRuntime = async () => {
    if (!runtimeProvider) {
      return;
    }
    if (requiresClientApiKey && !runtimeApiKey.trim()) {
      setStatusLine(`Add an API key for ${selectedProvider?.label || runtimeProvider} before switching, or configure one on the server.`);
      return;
    }

    setApplyingRuntime(true);
    try {
      const response = await updateSessionRuntime({
        sessionId: session.sessionId,
        provider: runtimeProvider,
        model: effectiveModel,
      });
      if (runtimeApiKey.trim()) {
        saveSessionCredential(session.sessionId, {
          provider: response.provider,
          model: response.model,
          apiKey: runtimeApiKey.trim(),
        });
      } else {
        saveSessionCredential(session.sessionId, null);
      }
      setSession((previous) => ({
        ...previous,
        provider: response.provider as SessionPayload["provider"],
        model: response.model,
        runtimeUsage: response.runtimeUsage,
      }));
      setStatusLine(`${selectedProvider?.label || response.provider} · ${response.model}`);
      setRuntimeOpen(false);
      onSessionActivity();
    } catch (error) {
      setStatusLine(error instanceof Error ? error.message : "Failed to update runtime");
    } finally {
      setApplyingRuntime(false);
    }
  };

  const submit = async (chipText?: string) => {
    const message = (chipText ?? draft).trim();
    if ((!message && !selectedFile) || pending) {
      return;
    }
    if (requiresClientApiKey && !runtimeApiKey.trim()) {
      setStatusLine(`Add an API key for ${selectedProvider?.label || runtimeProvider} to use this runtime.`);
      setRuntimeOpen(true);
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
        provider: runtimeProvider,
        model: effectiveModel,
        apiKey: runtimeApiKey.trim() || undefined,
        file: selectedFile,
        handlers: {
          onMeta: (data) => {
            const profile = (data.responseProfile as ResponseProfile) ?? session.responseProfile;
            const provider = (data.provider as string | undefined) ?? runtimeProvider;
            const model = (data.model as string | undefined) ?? effectiveModel;
            const fallbackUsed = Boolean(data.fallbackUsed);
            const stableWorkflow = Boolean(data.stableWorkflow);
            setSession((previous) => ({
              ...previous,
              provider: provider as SessionPayload["provider"],
              model,
              runtimeUsage: (data.runtimeUsage as SessionPayload["runtimeUsage"]) ?? previous.runtimeUsage,
            }));
            if (fallbackUsed) {
              setStatusLine(`${provider} fell back to ${model}`);
            } else if (stableWorkflow) {
              setStatusLine(`${profileLabel(profile)} · ${provider} · ${model} · stable flow`);
            } else {
              setStatusLine(`${profileLabel(profile)} · ${provider} · ${model}`);
            }
          },
          onDelta: (delta) => {
            setStreamingAssistant((current) => current + delta);
          },
          onDone: (data) => {
            const assistantMessage = (data.message as string) ?? "";
            const timings = data.timings as Record<string, number> | undefined;
            const provider = ((data.provider as string | undefined) ?? runtimeProvider) as SessionPayload["provider"];
            const model = (data.model as string | undefined) ?? effectiveModel;
            const stableWorkflow = Boolean(data.stableWorkflow);
            setSession((previous) => ({
              ...previous,
              history: [...previous.history, { role: "assistant", content: assistantMessage }],
              state: data.state as SessionPayload["state"],
              chips: data.chips as string[],
              coverage: data.coverage as CoverageItem[],
              nextGap: data.nextGap as string,
              responseProfile: (data.responseProfile as ResponseProfile) ?? previous.responseProfile,
              activeUploads: data.activeUploads as UploadSummary[],
              provider,
              model,
              runtimeUsage: (data.runtimeUsage as SessionPayload["runtimeUsage"]) ?? previous.runtimeUsage,
            }));
            if (runtimeApiKey.trim()) {
              saveSessionCredential(session.sessionId, {
                provider,
                model,
                apiKey: runtimeApiKey.trim(),
              });
            }
            if (timings?.firstTokenSeconds !== undefined) {
              const usageLabel = tokenStatus(data.runtimeUsage as SessionPayload["runtimeUsage"]);
              const totalSeconds = typeof timings.totalBackendSeconds === "number" ? timings.totalBackendSeconds : timings.totalSeconds;
              setStatusLine(
                `${profileLabel(((data.responseProfile as ResponseProfile) ?? session.responseProfile))} · first token ${timings.firstTokenSeconds}s${typeof totalSeconds === "number" ? ` · total ${totalSeconds}s` : ""}${usageLabel ? ` · ${usageLabel}` : ""}${stableWorkflow ? " · stable flow" : ""}`,
              );
            }
            setStreamingAssistant("");
            setSelectedFile(null);
            onSessionActivity();
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
        <div className="rail-card">
          <div className="rail-stack-head">
            <div>
              <span className="eyebrow">Ideate</span>
              <strong>{session.state.company_name || "Workspace"}</strong>
            </div>
            <span className="brand-dot" aria-hidden="true" />
          </div>
          <dl className="meta-list dense-meta-list">
            <div>
              <dt>Stage</dt>
              <dd>{session.state.stage}</dd>
            </div>
            <div>
              <dt>Sector</dt>
              <dd>{session.state.sector}</dd>
            </div>
            <div>
              <dt>Mode</dt>
              <dd>{session.state.mode === "think_it_through" ? "Guided" : "Direct"}</dd>
            </div>
          </dl>
        </div>

        <div className="rail-card rail-session-card">
          <div className="rail-stack-head">
            <span className="rail-label">Sessions</span>
            <button type="button" className="ghost-button compact" onClick={() => setSessionsOpen(true)}>
              All
            </button>
          </div>
          <div className="session-list rail-session-list">
            {visibleSessions.length === 0 ? (
              <p className="muted-copy">Recent work will appear here.</p>
            ) : (
              visibleSessions.map((item) => (
                <button
                  key={item.sessionId}
                  type="button"
                  className={item.sessionId === session.sessionId ? "session-card active" : "session-card"}
                  onClick={() => void onOpenSession(item.sessionId)}
                >
                  <strong>{item.title}</strong>
                  <span>{item.subtitle}</span>
                  <span>{workflowLabel(item.sessionType)} · {formatSessionTime(item.lastActive)}</span>
                </button>
              ))
            )}
          </div>
        </div>

        <div className="rail-footer">
          <div className="rail-action-grid">
            <button type="button" className="ghost-button" onClick={onNewSession}>
              New
            </button>
            <button type="button" className="ghost-button" onClick={() => setSessionsOpen(true)}>
              Clear
            </button>
          </div>
          <p className="ws-model-tag">{session.provider} · {session.model}</p>
        </div>
      </aside>

      <main className={mobilePane === "chat" ? "main-pane mobile-chat" : "main-pane mobile-coverage"}>
        <header className="pane-header">
          <div>
            <span className="eyebrow">Ideate</span>
            <h2>{session.state.company_name || "Ideate"}</h2>
          </div>
          <div className="status-stack">
            <div className="header-actions">
              <button type="button" className="ghost-button compact" onClick={() => setSessionsOpen(true)}>
                History
              </button>
              <button type="button" className="ghost-button compact" onClick={() => setRuntimeOpen(true)}>
                Model
              </button>
              <button type="button" className="ghost-button compact" onClick={() => setProgressOpen(true)}>
                Map
              </button>
              <button type="button" className="ghost-button compact" onClick={() => setThemeOpen(true)}>
                Theme
              </button>
              {session.activeUploads.length > 0 ? (
                <button type="button" className="ghost-button compact" onClick={() => setFilesOpen(true)}>
                  Files
                </button>
              ) : null}
              <button type="button" className="ghost-button compact" onClick={onNewSession}>
                New
              </button>
              <button type="button" className="ghost-button compact" onClick={() => navigate(`/outline/${session.sessionId}`)}>
                Draft
              </button>
              <button type="button" className="ghost-button compact" onClick={onExitSession}>
                Exit
              </button>
            </div>
            <small>{statusLine || (session.activeUploads.length > 0 ? `${session.activeUploads.length} file${session.activeUploads.length > 1 ? "s" : ""} in context` : "")}</small>
          </div>
        </header>

        {mobilePane === "chat" ? (
          <div className="chat-panel">
            <ChatMessageList
              history={session.history}
              streamingAssistant={streamingAssistant}
              assistantLabel="Ideate"
              sessionId={session.sessionId}
            />
            {starterHelper && session.history.length <= 3 ? <div className="prompt-helper">{starterHelper}</div> : null}
            <div className="chip-row">
              {visibleChips.map((chip) => (
                <button key={chip} type="button" className="chip-button" onClick={() => void submit(chip)} disabled={pending}>
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
        ) : (
          <div className="mobile-coverage-panel">
            <div className="drawer-card">
              <span className="rail-label">Deck progress</span>
              <PitchHealthRing coverage={session.coverage} />
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
          <PitchHealthRing coverage={session.coverage} />
          <div className="focus-card">
            <span className="focus-tag">Next focus</span>
            <strong>{nextGapMeta.title}</strong>
            <p>{nextGapMeta.hint}</p>
          </div>
          <div className="coverage-list">
            {coverageCompactSections.map((item) => (
              <div key={item.section} className="coverage-item deck-item compact-deck-item">
                <div className="coverage-head">
                  <strong>{item.meta.title}</strong>
                  <span>{item.score}%</span>
                </div>
                <div className="coverage-bar">
                  <div style={{ width: `${item.score}%` }} />
                </div>
                <small>{item.status}</small>
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

        <button type="button" className="ghost-button rail-action-wide" onClick={() => navigate(`/outline/${session.sessionId}`)}>
          Open refined pitch
        </button>
      </aside>

      <SessionSidebar
        isOpen={sessionsOpen}
        sessions={recentSessions}
        currentSessionId={session.sessionId}
        clearing={clearingHistory}
        onClose={() => setSessionsOpen(false)}
        onOpenSession={(sessionId) => {
          setSessionsOpen(false);
          void onOpenSession(sessionId);
        }}
        onClearHistory={() => {
          setSessionsOpen(false);
          void onClearHistory();
        }}
      />

      <RuntimeSidebar
        isOpen={runtimeOpen}
        title="Model"
        providerOptions={providerOptions}
        provider={runtimeProvider}
        model={runtimeModel}
        apiKey={runtimeApiKey}
        runtimeUsage={session.runtimeUsage}
        responseProfile={session.responseProfile}
        applying={applyingRuntime}
        onClose={() => setRuntimeOpen(false)}
        onProviderChange={(provider) => {
          setRuntimeProvider(provider as SessionPayload["provider"]);
          setRuntimeModel(defaultModelForProvider(providerOptions, provider, session.responseProfile));
        }}
        onModelChange={setRuntimeModel}
        onApiKeyChange={setRuntimeApiKey}
        onUseDefaultModel={(profile) => setRuntimeModel(defaultModelForProvider(providerOptions, runtimeProvider, profile))}
        onResponseProfileChange={(profile) => {
          setSession((previous) => ({ ...previous, responseProfile: profile }));
          setRuntimeModel(defaultModelForProvider(providerOptions, runtimeProvider, profile));
        }}
        onApply={() => void applyRuntime()}
      />

      <div className={progressOpen ? "floating-panel is-open align-right" : "floating-panel align-right"} aria-hidden={!progressOpen}>
        <button type="button" className={progressOpen ? "floating-backdrop is-open" : "floating-backdrop"} onClick={() => setProgressOpen(false)} aria-label="Close progress" />
        <aside className={progressOpen ? "floating-card runtime-card is-open" : "floating-card runtime-card"}>
          <div className="floating-head">
            <div>
              <span className="rail-label">Progress</span>
              <strong>Pitch map</strong>
            </div>
            <button type="button" className="ghost-button compact" onClick={() => setProgressOpen(false)}>
              Close
            </button>
          </div>
          <div className="floating-scroll">
            <div className="drawer-card">
              <span className="rail-label">Current read</span>
              <div className="compact-session-grid">
                <div className="compact-session-pill">
                  <span>Mode</span>
                  <strong>{session.state.mode === "think_it_through" ? "Ideate" : "Pressure-test"}</strong>
                </div>
                <div className="compact-session-pill">
                  <span>Stage</span>
                  <strong>{session.state.stage}</strong>
                </div>
                <div className="compact-session-pill">
                  <span>Coverage</span>
                  <strong>{Math.round(coverageSummary)}%</strong>
                </div>
                <div className="compact-session-pill">
                  <span>Engine</span>
                  <strong>{session.provider}</strong>
                </div>
              </div>
              <div className="focus-card compact-focus-card">
                <span className="focus-tag">Current strongest output</span>
                <strong>Ideate stays two-way. Open the refined pitch whenever you want a cleaner working draft.</strong>
                <p>Nothing stops the conversation. The pitch doc simply reflects the current thread.</p>
              </div>
              <button type="button" className="ghost-button compact full-width-button" onClick={() => navigate(`/outline/${session.sessionId}`)}>
                Open refined pitch
              </button>
            </div>
            <div className="drawer-card">
              <div className="working-map-head">
                <div>
                  <span className="rail-label">Working map</span>
                  <strong>{nextGapMeta.title}</strong>
                </div>
                <small>{nextGapMeta.hint}</small>
              </div>
              <div className="compact-coverage-grid ideate-coverage-grid">
                {coverageCompactSections.map((item) => (
                  <div key={item.section} className="coverage-item deck-item compact-deck-item">
                    <div className="coverage-head">
                      <strong>{item.meta.title}</strong>
                      <span>{item.score}%</span>
                    </div>
                    <div className="coverage-bar">
                      <div style={{ width: `${item.score}%` }} />
                    </div>
                    <small>{item.status}</small>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </aside>
      </div>

      <div className={filesOpen ? "floating-panel is-open align-right" : "floating-panel align-right"} aria-hidden={!filesOpen}>
        <button type="button" className={filesOpen ? "floating-backdrop is-open" : "floating-backdrop"} onClick={() => setFilesOpen(false)} aria-label="Close files" />
        <aside className={filesOpen ? "floating-card runtime-card is-open" : "floating-card runtime-card"}>
          <div className="floating-head">
            <div>
              <span className="rail-label">Files</span>
              <strong>Context in use</strong>
            </div>
            <button type="button" className="ghost-button compact" onClick={() => setFilesOpen(false)}>
              Close
            </button>
          </div>
          {session.activeUploads.length === 0 ? (
            <p className="muted-copy">No files are active in this session yet.</p>
          ) : (
            <ul className="upload-list floating-scroll">
              {session.activeUploads.map((upload) => (
                <li key={`${upload.name}-${upload.uploadedAt}`}>
                  <strong>{upload.name}</strong>
                  <span>{upload.docType}</span>
                </li>
              ))}
            </ul>
          )}
        </aside>
      </div>

      <div className={themeOpen ? "floating-panel is-open align-right" : "floating-panel align-right"} aria-hidden={!themeOpen}>
        <button type="button" className={themeOpen ? "floating-backdrop is-open" : "floating-backdrop"} onClick={() => setThemeOpen(false)} aria-label="Close theme" />
        <aside className={themeOpen ? "floating-card is-open theme-card" : "floating-card theme-card"}>
          <div className="floating-head">
            <div>
              <span className="rail-label">Theme</span>
              <strong>Display</strong>
            </div>
            <button type="button" className="ghost-button compact" onClick={() => setThemeOpen(false)}>
              Close
            </button>
          </div>
          <ThemePicker
            theme={theme}
            onChange={(nextTheme) => {
              onThemeChange(nextTheme);
              setThemeOpen(false);
            }}
          />
        </aside>
      </div>

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
          Pitch
        </button>
      </nav>
    </div>
  );
}
