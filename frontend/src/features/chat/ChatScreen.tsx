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
import { SignalLockup } from "../../app/SignalBrand";
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

function defaultModelForProvider(providerOptions: ProviderOption[], provider: string, profile: ResponseProfile): string {
  const providerMeta = providerOptions.find((item) => item.key === provider);
  if (!providerMeta) {
    return "";
  }
  return profile === "balanced" ? providerMeta.defaultBalancedModel : providerMeta.defaultSpeedModel;
}

export function ChatScreen({
  session,
  setSession,
  onNewSession,
  onExitSession,
  onOpenSession,
  onSessionActivity,
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
  const [statusLine, setStatusLine] = useState("Local-first ideation");
  const [sessionsOpen, setSessionsOpen] = useState(false);
  const [runtimeOpen, setRuntimeOpen] = useState(false);
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
  }, [session.sessionId, session.provider, session.model]);

  const selectedProvider = useMemo(
    () => providerOptions.find((item) => item.key === runtimeProvider) ?? providerOptions[0] ?? null,
    [providerOptions, runtimeProvider],
  );
  const requiresApiKey = Boolean(selectedProvider?.requiresApiKey);
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

  const applyRuntime = async () => {
    if (!runtimeProvider) {
      return;
    }
    if (requiresApiKey && !runtimeApiKey.trim()) {
      setStatusLine(`Add an API key for ${selectedProvider?.label || runtimeProvider} before switching.`);
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
    if (requiresApiKey && !runtimeApiKey.trim()) {
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
            setSession((previous) => ({
              ...previous,
              provider: provider as SessionPayload["provider"],
              model,
            }));
            setStatusLine(fallbackUsed ? `${provider} fell back to ${model}` : `${profile.toUpperCase()} · ${provider} · ${model}`);
          },
          onDelta: (delta) => {
            setStreamingAssistant((current) => current + delta);
          },
          onDone: (data) => {
            const assistantMessage = (data.message as string) ?? "";
            const timings = data.timings as Record<string, number> | undefined;
            const provider = ((data.provider as string | undefined) ?? runtimeProvider) as SessionPayload["provider"];
            const model = (data.model as string | undefined) ?? effectiveModel;
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
            }));
            if (runtimeApiKey.trim()) {
              saveSessionCredential(session.sessionId, {
                provider,
                model,
                apiKey: runtimeApiKey.trim(),
              });
            }
            if (timings?.firstTokenSeconds !== undefined) {
              setStatusLine(
                `${((data.responseProfile as ResponseProfile) ?? session.responseProfile).toUpperCase()} · first token ${timings.firstTokenSeconds}s`,
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
        <div>
          <SignalLockup compact className="workspace-lockup" />

          <div className="rail-card">
            <span className="rail-label">Response profile</span>
            <div className="segmented">
              {(["speed", "balanced"] as ResponseProfile[]).map((profile) => (
                <button
                  key={profile}
                  type="button"
                  className={session.responseProfile === profile ? "segment active" : "segment"}
                  onClick={() => {
                    setSession((previous) => ({ ...previous, responseProfile: profile }));
                    setRuntimeModel((current) => current || defaultModelForProvider(providerOptions, runtimeProvider, profile));
                  }}
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
              <div>
                <dt>Runtime</dt>
                <dd>{session.provider}</dd>
              </div>
            </dl>
          </div>
        </div>

        <div className="rail-footer">
          <ThemePicker theme={theme} onChange={onThemeChange} />
          <button type="button" className="ghost-button" onClick={() => setSessionsOpen(true)}>
            Sessions
          </button>
          <button type="button" className="ghost-button" onClick={() => setRuntimeOpen(true)}>
            Runtime
          </button>
          <button type="button" className="ghost-button" onClick={onNewSession}>
            Start new session
          </button>
          <button type="button" className="ghost-button" onClick={() => navigate(`/outline/${session.sessionId}`)}>
            Open outline
          </button>
          <button type="button" className="ghost-button" onClick={onExitSession}>
            Exit session
          </button>
        </div>
      </aside>

      <main className={mobilePane === "chat" ? "main-pane mobile-chat" : "main-pane mobile-coverage"}>
        <header className="pane-header">
          <div>
            <span className="eyebrow">Cut Through The Noise.</span>
            <h2>{session.state.company_name || "Ideate"}</h2>
          </div>
          <div className="status-stack">
            <span>{statusLine}</span>
            <div className="header-actions">
              <button type="button" className="ghost-button compact" onClick={() => setSessionsOpen(true)}>
                Sessions
              </button>
              <button type="button" className="ghost-button compact" onClick={() => setRuntimeOpen(true)}>
                Runtime
              </button>
              <button type="button" className="ghost-button compact" onClick={onNewSession}>
                New
              </button>
              <button type="button" className="ghost-button compact" onClick={() => navigate(`/outline/${session.sessionId}`)}>
                Outline
              </button>
              <button type="button" className="ghost-button compact" onClick={onExitSession}>
                Exit
              </button>
            </div>
            {session.activeUploads.length > 0 && <small>{session.activeUploads.length} active uploads</small>}
          </div>
        </header>

        {mobilePane === "chat" ? (
          <div className="chat-panel">
            <ChatMessageList history={session.history} streamingAssistant={streamingAssistant} assistantLabel="Ideate" />
            <div className="chip-row">
              {session.chips.map((chip) => (
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
            <p className="muted-copy">Attach a deck, notes, or research. Only the relevant parts will be used.</p>
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

      <SessionSidebar
        isOpen={sessionsOpen}
        sessions={recentSessions}
        currentSessionId={session.sessionId}
        onClose={() => setSessionsOpen(false)}
        onOpenSession={(sessionId) => {
          setSessionsOpen(false);
          void onOpenSession(sessionId);
        }}
      />

      <RuntimeSidebar
        isOpen={runtimeOpen}
        title="Switch model live"
        providerOptions={providerOptions}
        provider={runtimeProvider}
        model={runtimeModel}
        apiKey={runtimeApiKey}
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
        onApply={() => void applyRuntime()}
      />

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
