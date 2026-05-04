import { useEffect, useMemo, useState } from "react";

import type {
  ChatTurn,
  HelpMode,
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
import { ChatMessageList } from "../chat/ChatMessageList";
import { Composer } from "../chat/Composer";


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
  clientId: string;
};

type MobilePane = "chat" | "evidence";

const DEFAULT_QUICK_ACTIONS = [
  "Break down a term",
  "Compare structures",
  "Pre-screen an idea",
  "Review my deck",
  "Check market context",
  "Map key risks",
  "Pressure-test unit economics",
];

const STARTER_PROMPTS = [
  {
    title: "Break down a term",
    prompt: "Explain liquidation preference like I am seeing it for the first time.",
  },
  {
    title: "Compare structures",
    prompt: "Compare SAFE vs convertible note for an early-stage startup.",
  },
  {
    title: "Pre-screen a deck",
    prompt: "Pre-screen this startup idea and tell me the biggest missing evidence.",
  },
];

const HELP_MODES: Array<{ value: HelpMode; label: string }> = [
  { value: "coach_me", label: "Coach me" },
  { value: "challenge_me", label: "Challenge me" },
  { value: "explain_directly", label: "Explain directly" },
];


function defaultModelForProvider(providerOptions: ProviderOption[], provider: string, profile: ResponseProfile): string {
  const providerMeta = providerOptions.find((item) => item.key === provider);
  if (!providerMeta) {
    return "";
  }
  return profile === "balanced" ? providerMeta.defaultBalancedModel : providerMeta.defaultSpeedModel;
}


function profileLabel(profile: ResponseProfile): string {
  return profile === "balanced" ? "Sharper" : "Fast";
}


function tokenStatus(runtimeUsage: SessionPayload["runtimeUsage"] | undefined): string {
  const total = runtimeUsage?.last?.totalTokens ?? 0;
  if (!total) {
    return "";
  }
  return `${Math.round(total).toLocaleString()} tok${runtimeUsage?.last?.estimated ? " est." : ""}`;
}


function laneLabel(lane: string): string {
  if (!lane) {
    return "General";
  }
  return lane.replace(/_/g, " ").replace(/\b\w/g, (match) => match.toUpperCase());
}


function confidenceLabel(confidence: number): string {
  if (confidence >= 0.8) {
    return "High";
  }
  if (confidence >= 0.6) {
    return "Good";
  }
  if (confidence >= 0.4) {
    return "Partial";
  }
  return "Thin";
}

function sourceQualityClass(confidence: string): "high" | "medium" | "low" {
  const normalized = confidence.toLowerCase();
  if (normalized.includes("high") || normalized.includes("strong")) {
    return "high";
  }
  if (normalized.includes("low") || normalized.includes("thin")) {
    return "low";
  }
  return "medium";
}

function sourceQualityLabel(confidence: string): string {
  const quality = sourceQualityClass(confidence);
  return quality === "high" ? "High" : quality === "low" ? "Low" : "Medium";
}


function workflowLabel(sessionType: SessionPayload["sessionType"]) {
  if (sessionType === "expert") {
    return "Expert";
  }
  if (sessionType === "evaluator") {
    return "Evaluate";
  }
  return "Ideate";
}


function SectionList({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <section className="expert-panel-card">
      <div className="expert-panel-head">
        <span className="rail-label">{title}</span>
      </div>
      {items.length === 0 ? <p className="muted-copy">{empty}</p> : (
        <ul className="expert-bullet-list">
          {items.map((item) => (
            <li key={`${title}-${item}`}>{item}</li>
          ))}
        </ul>
      )}
    </section>
  );
}


export function ExpertScreen({
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
  clientId,
}: Props) {
  const [draft, setDraft] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [streamingAssistant, setStreamingAssistant] = useState("");
  const [pending, setPending] = useState(false);
  const [mobilePane, setMobilePane] = useState<MobilePane>("chat");
  const [statusLine, setStatusLine] = useState("");
  const [sessionsOpen, setSessionsOpen] = useState(false);
  const [runtimeOpen, setRuntimeOpen] = useState(false);
  const [themeOpen, setThemeOpen] = useState(false);
  const [filesOpen, setFilesOpen] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(() => session.sources.length > 0);
  const [applyingRuntime, setApplyingRuntime] = useState(false);
  const [runtimeProvider, setRuntimeProvider] = useState<SessionPayload["provider"]>(session.provider);
  const [runtimeModel, setRuntimeModel] = useState(session.model);
  const [runtimeApiKey, setRuntimeApiKey] = useState(() => loadSessionCredential(session.sessionId)?.apiKey ?? "");
  const [helpMode, setHelpMode] = useState<HelpMode>(session.helpMode);

  useEffect(() => {
    setRuntimeProvider(session.provider);
    setRuntimeModel(session.model);
    setRuntimeApiKey(loadSessionCredential(session.sessionId)?.apiKey ?? "");
    setHelpMode(session.helpMode);
    setSessionsOpen(false);
    setRuntimeOpen(false);
    setThemeOpen(false);
    setFilesOpen(false);
    setSourcesOpen(session.sources.length > 0);
  }, [session.sessionId, session.provider, session.model, session.helpMode]);

  useEffect(() => {
    if (session.sources.length > 0) {
      setSourcesOpen(true);
    }
  }, [session.sources.length]);

  const selectedProvider = useMemo(
    () => providerOptions.find((item) => item.key === runtimeProvider) ?? providerOptions[0] ?? null,
    [providerOptions, runtimeProvider],
  );
  const requiresClientApiKey = Boolean(selectedProvider?.requiresApiKey && !selectedProvider.serverConfigured);
  const effectiveModel = runtimeModel.trim() || defaultModelForProvider(providerOptions, runtimeProvider, session.responseProfile);
  const quickActions = session.chips.length > 0 ? session.chips : DEFAULT_QUICK_ACTIONS;
  const confidenceText = confidenceLabel(session.confidence);
  const showStarterCard = session.history.length <= 1 && !streamingAssistant;

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
        clientId,
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
      helpMode,
      liveWebEnabled: true,
    }));

    setDraft("");
    setPending(true);
    setStreamingAssistant("");

    try {
      await streamChat({
        sessionId: session.sessionId,
        clientId,
        message,
        responseProfile: session.responseProfile,
        provider: runtimeProvider,
        model: effectiveModel,
        apiKey: runtimeApiKey.trim() || undefined,
        helpMode,
        liveWebEnabled: true,
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
              coverage: data.coverage as SessionPayload["coverage"],
              nextGap: data.nextGap as string,
              responseProfile: (data.responseProfile as ResponseProfile) ?? previous.responseProfile,
              activeUploads: data.activeUploads as UploadSummary[],
              provider,
              model,
              sources: (data.sources as SessionPayload["sources"]) ?? previous.sources,
              confidence: typeof data.confidence === "number" ? data.confidence : previous.confidence,
              knowledgeLane: (data.knowledgeLane as string) ?? previous.knowledgeLane,
              usedLiveWeb: Boolean(data.usedLiveWeb),
              followUpMode: (data.followUpMode as string) ?? previous.followUpMode,
              helpMode: (data.helpMode as HelpMode) ?? helpMode,
              liveWebEnabled: true,
              analysisSnapshot: (data.analysisSnapshot as SessionPayload["analysisSnapshot"]) ?? previous.analysisSnapshot,
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
    <div className="app-shell expert-workbench-shell">
      <div className={sourcesOpen ? "expert-workbench-grid" : "expert-workbench-grid sources-collapsed"}>
        <aside className="expert-left-column">
          <section className="expert-panel-card">
            <div className="expert-panel-head">
              <span className="eyebrow">Workflow</span>
              <strong>{workflowLabel(session.sessionType)}</strong>
            </div>
            <div className="compact-session-grid">
              <div className="compact-session-pill">
                <span>Lane</span>
                <strong>{laneLabel(session.knowledgeLane)}</strong>
              </div>
              <div className="compact-session-pill">
                <span>Confidence</span>
                <strong>{confidenceText}</strong>
              </div>
              <div className="compact-session-pill">
                <span>Research</span>
                <strong>Automatic</strong>
              </div>
              <div className="compact-session-pill">
                <span>Help</span>
                <strong>{HELP_MODES.find((item) => item.value === helpMode)?.label || "Coach me"}</strong>
              </div>
            </div>
          </section>

          <section className="expert-panel-card">
            <div className="expert-panel-head">
              <span className="rail-label">Recent sessions</span>
            </div>
            <div className="expert-session-list">
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
            <div className="expert-left-actions">
              <button type="button" className="ghost-button compact" onClick={() => setSessionsOpen(true)}>
                Open all sessions
              </button>
              <button type="button" className="ghost-button compact" onClick={onNewSession}>
                New session
              </button>
            </div>
          </section>
        </aside>

        <main className={mobilePane === "chat" ? "expert-main-column mobile-chat" : "expert-main-column mobile-evidence"}>
          <header className="pane-header expert-pane-header">
            <div>
              <span className="eyebrow">Expert</span>
              <h2>{session.state.company_name || "Expert"}</h2>
              <small className="expert-header-subline">
                {laneLabel(session.knowledgeLane)} · {session.sources.length} source{session.sources.length === 1 ? "" : "s"} · {session.usedLiveWeb ? "web + local evidence" : "local corpus led this turn"}
              </small>
            </div>
            <div className="status-stack">
              <div className="header-actions">
                <button type="button" className="ghost-button compact" onClick={() => setSessionsOpen(true)}>
                  History
                </button>
                <button type="button" className="ghost-button compact" onClick={() => setRuntimeOpen(true)}>
                  Model
                </button>
                <button type="button" className="ghost-button compact" onClick={() => setThemeOpen(true)}>
                  Theme
                </button>
                <button type="button" className="ghost-button compact" onClick={() => setSourcesOpen((current) => !current)}>
                  {sourcesOpen ? "Hide sources" : "Show sources"}
                </button>
                {session.activeUploads.length > 0 ? (
                  <button type="button" className="ghost-button compact" onClick={() => setFilesOpen(true)}>
                    Files
                  </button>
                ) : null}
                <button type="button" className="ghost-button compact" onClick={onNewSession}>
                  New
                </button>
                <button type="button" className="ghost-button compact" onClick={onExitSession}>
                  Exit
                </button>
              </div>
              <small>{statusLine || `${confidenceText} confidence · ${selectedProvider?.label || session.provider}`}</small>
            </div>
          </header>

          <section className="expert-panel-card expert-mobile-summary">
            <div className="expert-panel-head">
              <span className="rail-label">Session view</span>
              <strong>{laneLabel(session.knowledgeLane)} · {confidenceText} confidence</strong>
            </div>
            <div className="compact-session-grid">
              <div className="compact-session-pill">
                <span>Sources</span>
                <strong>{session.sources.length}</strong>
              </div>
              <div className="compact-session-pill">
                <span>Uploads</span>
                <strong>{session.activeUploads.length}</strong>
              </div>
              <div className="compact-session-pill">
                <span>Research</span>
                <strong>Automatic</strong>
              </div>
              <div className="compact-session-pill">
                <span>Help</span>
                <strong>{HELP_MODES.find((item) => item.value === helpMode)?.label || "Coach me"}</strong>
              </div>
            </div>
            <p className="muted-copy">Use chat to work through the problem. Switch to evidence when you want sources, concepts, and analysis.</p>
          </section>

          <div className="expert-control-row">
            <div className="expert-toggle-group">
              {HELP_MODES.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={helpMode === option.value ? "chip-button active" : "chip-button"}
                  onClick={() => {
                    setHelpMode(option.value);
                    setSession((previous) => ({ ...previous, helpMode: option.value }));
                  }}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <div className="interaction-hint expert-research-note">
              <strong>Auto research</strong>
              <small>{session.usedLiveWeb ? "This answer used live web because local coverage was weak or stale." : "Sift will pull in live web only when it improves answer quality."}</small>
            </div>
          </div>

          {mobilePane === "chat" ? (
            <div className={showStarterCard ? "chat-panel expert-chat-panel starter-mode" : "chat-panel expert-chat-panel"}>
              <div className="expert-conversation-stack">
                {showStarterCard ? (
                  <section className="expert-panel-card expert-starter-card">
                    <div className="expert-panel-head">
                      <span className="rail-label">Good first prompt</span>
                      <strong>Start with a real decision or claim.</strong>
                    </div>
                    <p className="muted-copy">This workbench is strongest when you ask about a specific term, compare structures, or upload material for review. Keep it concrete when you can.</p>
                    <div className="expert-starter-grid">
                      {STARTER_PROMPTS.map((item) => (
                        <button key={item.title} type="button" className="expert-starter-tile" onClick={() => void submit(item.prompt)} disabled={pending}>
                          <strong>{item.title}</strong>
                          <span>{item.prompt}</span>
                        </button>
                      ))}
                    </div>
                  </section>
                ) : null}
                {!showStarterCard ? (
                  <ChatMessageList
                    history={session.history}
                    streamingAssistant={streamingAssistant}
                    assistantLabel="Expert"
                    sessionId={session.sessionId}
                  />
                ) : null}
              </div>
              {!showStarterCard && quickActions.length > 0 ? (
                <div className="expert-quick-actions">
                  {quickActions.map((chip) => (
                    <button key={chip} type="button" className="chip-button" onClick={() => void submit(chip)} disabled={pending}>
                      {chip}
                    </button>
                  ))}
                </div>
              ) : null}
              <Composer
                value={draft}
                onChange={setDraft}
                onSubmit={() => void submit()}
                pending={pending}
                selectedFile={selectedFile}
                onFileSelected={setSelectedFile}
                placeholder="Ask about a concept, compare options, or upload a deck for review..."
                attachmentHint="Deck, memo, or notes"
                uploadLabel="Upload deck or notes"
                submitLabel="Ask"
              />
            </div>
          ) : (
            <div className="expert-mobile-evidence">
              <section className="expert-panel-card">
                <div className="expert-panel-head">
                  <span className="rail-label">Sources</span>
                </div>
                {session.sources.length === 0 ? (
                  <p className="muted-copy">Relevant sources will appear here when the workbench retrieves them.</p>
                ) : (
                  <div className="expert-source-list">
                    {session.sources.map((source) => (
                      <a
                        key={`${source.title}-${source.url}-${source.label}-mobile`}
                        className="expert-source-card"
                        href={source.url || undefined}
                        target={source.url ? "_blank" : undefined}
                        rel={source.url ? "noreferrer" : undefined}
                      >
                        <div className="expert-source-card-head">
                          <strong>{source.title}</strong>
                          <span className={`src-quality ${sourceQualityClass(source.confidence)}`}>{sourceQualityLabel(source.confidence)}</span>
                        </div>
                        <span>{source.label || source.domain}</span>
                        <small>{source.geographyScope} · {source.confidence}</small>
                      </a>
                    ))}
                  </div>
                )}
              </section>
              <SectionList title="Concepts" items={session.analysisSnapshot.concepts} empty="Concept matches will appear here after retrieval." />
              <SectionList title="Strengths" items={session.analysisSnapshot.strengths} empty="No strengths logged yet." />
              <SectionList title="Risks" items={session.analysisSnapshot.risks} empty="No major risks flagged yet." />
              <SectionList
                title="Gaps"
                items={[...session.analysisSnapshot.missingEvidence, ...session.analysisSnapshot.contradictions]}
                empty="No KB or evidence gaps flagged yet."
              />
            </div>
          )}
        </main>

        {sourcesOpen ? (
        <aside className="expert-right-column">
          <section className="expert-panel-card">
            <div className="expert-panel-head">
              <span className="rail-label">Sources</span>
            </div>
            {session.sources.length === 0 ? (
              <p className="muted-copy">Relevant sources will appear here when the workbench retrieves them.</p>
            ) : (
              <div className="expert-source-list">
                {session.sources.map((source) => (
                  <a
                    key={`${source.title}-${source.url}-${source.label}`}
                    className="expert-source-card"
                    href={source.url || undefined}
                    target={source.url ? "_blank" : undefined}
                    rel={source.url ? "noreferrer" : undefined}
                  >
                    <div className="expert-source-card-head">
                      <strong>{source.title}</strong>
                      <span className={`src-quality ${sourceQualityClass(source.confidence)}`}>{sourceQualityLabel(source.confidence)}</span>
                    </div>
                    <span>{source.label || source.domain}</span>
                    <small>{source.geographyScope} · {source.confidence}</small>
                  </a>
                ))}
              </div>
            )}
          </section>

          <SectionList title="Concepts" items={session.analysisSnapshot.concepts} empty="The top retrieved concepts will show up here." />

          <section className="expert-panel-card">
            <div className="expert-panel-head">
              <span className="rail-label">Analysis</span>
            </div>
            <div className="expert-analysis-grid">
              <SectionList title="Strengths" items={session.analysisSnapshot.strengths} empty="No strengths logged yet." />
              <SectionList title="Risks" items={session.analysisSnapshot.risks} empty="No major risks flagged yet." />
              <SectionList title="Next actions" items={session.analysisSnapshot.recommendedNextActions} empty="Next actions will appear here when useful." />
            </div>
          </section>

          <SectionList
            title="Gaps"
            items={[...session.analysisSnapshot.missingEvidence, ...session.analysisSnapshot.contradictions, ...session.analysisSnapshot.nextQuestions]}
            empty="Knowledge gaps, contradictions, and next questions will surface here."
          />
        </aside>
        ) : null}
      </div>

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
          className={mobilePane === "evidence" ? "mobile-tab active" : "mobile-tab"}
          onClick={() => setMobilePane("evidence")}
        >
          Evidence
        </button>
      </nav>
    </div>
  );
}
