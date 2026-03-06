import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { ProviderOption, ResponseProfile, SessionPayload, SessionSummary, ThemeMode } from "../../app/types";
import { SignalLockup } from "../../app/SignalBrand";
import { ThemePicker } from "../../app/ThemePicker";
import { answerEvaluator, updateSessionRuntime } from "../../lib/api/client";
import { loadSessionCredential, saveSessionCredential } from "../../lib/sessionCredentials";
import { RuntimeSidebar } from "../session/RuntimeSidebar";
import { SessionSidebar } from "../session/SessionSidebar";
import { ChatMessageList } from "../chat/ChatMessageList";

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

function defaultModelForProvider(providerOptions: ProviderOption[], provider: string, profile: ResponseProfile): string {
  const providerMeta = providerOptions.find((item) => item.key === provider);
  if (!providerMeta) {
    return "";
  }
  return profile === "balanced" ? providerMeta.defaultBalancedModel : providerMeta.defaultSpeedModel;
}

export function EvaluatorScreen({
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
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [draft, setDraft] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [pending, setPending] = useState(false);
  const [statusLine, setStatusLine] = useState("Adaptive conversation");
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
  const effectiveModel = runtimeModel.trim() || defaultModelForProvider(providerOptions, runtimeProvider, "speed");

  const progress = session.evaluationProgress;
  const report = session.evaluationReport;
  const currentQuestion = progress?.currentQuestion ?? null;
  const reportHighlights = useMemo(
    () => (progress?.completed ? report?.suggestions.slice(0, 3) ?? [] : []),
    [progress?.completed, report],
  );

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

  const submit = async () => {
    if ((!draft.trim() && !selectedFile) || pending) {
      return;
    }
    if (requiresApiKey && !runtimeApiKey.trim()) {
      setStatusLine(`Add an API key for ${selectedProvider?.label || runtimeProvider} to continue.`);
      setRuntimeOpen(true);
      return;
    }

    const displayMessage = draft.trim()
      ? selectedFile
        ? `${draft.trim()}\n\n[Attached ${selectedFile.name}]`
        : draft.trim()
      : `[Attached ${selectedFile?.name}]`;
    const previousHistory = session.history;

    setSession((previous) => ({
      ...previous,
      history: [...previous.history, { role: "user", content: displayMessage }],
    }));
    setPending(true);
    setStatusLine("Thinking through your answer...");

    try {
      const response = await answerEvaluator({
        sessionId: session.sessionId,
        answer: draft.trim(),
        provider: runtimeProvider,
        model: effectiveModel,
        apiKey: runtimeApiKey.trim(),
        file: selectedFile,
      });
      if (runtimeApiKey.trim()) {
        saveSessionCredential(session.sessionId, {
          provider: runtimeProvider,
          model: effectiveModel,
          apiKey: runtimeApiKey.trim(),
        });
      }
      const assistantMessage = response.question
        ? `${response.reciprocal}\n\n${response.questionLabel || (response.evaluationProgress.answeredQuestions === 0 ? "First question" : "Next question")}: ${response.question.text}`
        : `${response.reciprocal}\n\nThat is enough. Let me evaluate the idea.`;

      setSession((previous) => ({
        ...previous,
        history: [...previous.history, { role: "assistant", content: assistantMessage }],
        activeUploads: response.activeUploads,
        evaluationProgress: response.evaluationProgress,
        evaluationReport: response.evaluationReport,
        provider: runtimeProvider as SessionPayload["provider"],
        model: effectiveModel,
      }));
      setDraft("");
      setSelectedFile(null);
      setStatusLine(response.warning || (response.evaluationProgress.completed ? "Let me evaluate the idea..." : "Ready for the next step."));
      onSessionActivity();
      if (response.evaluationProgress.completed) {
        window.setTimeout(() => {
          navigate(`/evaluate/${session.sessionId}/report`);
        }, 450);
      }
    } catch (error) {
      setSession((previous) => ({
        ...previous,
        history: previousHistory,
      }));
      setStatusLine(error instanceof Error ? error.message : "Failed to score answer");
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
            <span className="rail-label">Assessment</span>
            <div className="focus-card">
              <strong>Adaptive flow</strong>
              <p>Questions stay conversational. The score is calculated only in the final report.</p>
            </div>
            <div className="coverage-bar">
              <div style={{ width: `${((progress?.answeredQuestions ?? 0) / Math.max(progress?.questionBudget ?? 15, 1)) * 100}%` }} />
            </div>
            <small className="muted-copy">
              {progress?.answeredQuestions ?? 0} answered · up to {progress?.questionBudget ?? 15} questions
            </small>
          </div>

          <div className="rail-card">
            <span className="rail-label">Runtime</span>
            <dl className="meta-list">
              <div>
                <dt>Provider</dt>
                <dd>{session.provider}</dd>
              </div>
              <div>
                <dt>Model</dt>
                <dd>{session.model}</dd>
              </div>
              <div>
                <dt>Stage</dt>
                <dd>{session.state.stage}</dd>
              </div>
              <div>
                <dt>Style</dt>
                <dd>{session.state.mode === "think_it_through" ? "Guided build" : "Tight review"}</dd>
              </div>
              <div>
                <dt>Sector</dt>
                <dd>{session.state.sector}</dd>
              </div>
            </dl>
          </div>
        </div>

        <div className="rail-footer">
          <ThemePicker theme={theme} onChange={onThemeChange} />
          <div className="rail-action-grid">
            <button type="button" className="ghost-button" onClick={() => setSessionsOpen(true)}>
              Sessions
            </button>
            <button type="button" className="ghost-button" onClick={() => setRuntimeOpen(true)}>
              Runtime
            </button>
            <button type="button" className="ghost-button" onClick={() => navigate(`/evaluate/${session.sessionId}/report`)}>
              Score report
            </button>
            <button type="button" className="ghost-button" onClick={onNewSession}>
              New session
            </button>
          </div>
          <button type="button" className="ghost-button rail-action-wide" onClick={onExitSession}>
            Exit session
          </button>
        </div>
      </aside>

      <main className="main-pane">
        <header className="pane-header">
          <div>
            <span className="eyebrow">Adaptive conversation</span>
            <h2>Evaluate</h2>
          </div>
          <div className="status-stack">
            <span>{progress ? `${progress.answeredQuestions}/${progress.questionBudget} complete` : statusLine}</span>
            <div className="header-actions">
              <button type="button" className="ghost-button compact" onClick={() => setSessionsOpen(true)}>
                Sessions
              </button>
              <button type="button" className="ghost-button compact" onClick={() => setRuntimeOpen(true)}>
                Runtime
              </button>
              <button type="button" className="ghost-button compact" onClick={() => navigate(`/evaluate/${session.sessionId}/report`)}>
                Report
              </button>
              <button type="button" className="ghost-button compact" onClick={onNewSession}>
                New
              </button>
              <button type="button" className="ghost-button compact" onClick={onExitSession}>
                Exit
              </button>
            </div>
            <small>{progress?.website?.warning ? String(progress.website.warning) : statusLine}</small>
          </div>
        </header>

        <div className="chat-panel evaluator-panel">
          <div className="evaluator-question-card">
            <span className="rail-label">{currentQuestion?.category || "Assessment"}</span>
            {currentQuestion?.contextHint ? <span className="question-context-hint">{currentQuestion.contextHint}</span> : null}
            <strong>{currentQuestion?.text || "Start with the idea. The next question will adapt to what you say."}</strong>
            <p>{progress?.lastFeedback || "Keep it natural. Clear specifics help the final evaluation."}</p>
          </div>

          <ChatMessageList history={session.history} streamingAssistant="" assistantLabel="Evaluate" />

          <div className="composer-shell">
            <div className="attachment-row">
              <div className="attachment-meta">
                <span className="rail-label">Context</span>
                <small>Optional deck, notes, or PDF</small>
              </div>
              <div className="attachment-actions">
                <button type="button" className="ghost-button compact" onClick={() => inputRef.current?.click()}>
                  {selectedFile ? "Change file" : "Upload file"}
                </button>
                {selectedFile ? <span className="attachment-pill">{selectedFile.name}</span> : null}
                {selectedFile ? (
                  <button type="button" className="ghost-button compact" onClick={() => setSelectedFile(null)}>
                    Remove
                  </button>
                ) : null}
              </div>
              <input
                ref={inputRef}
                type="file"
                hidden
                accept=".pdf,.pptx,.docx,.txt"
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              />
            </div>
            <div className="composer-row">
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder={currentQuestion ? "Answer naturally. Specifics help." : "Tell me what you are building, who it is for, and why it matters."}
                rows={4}
                disabled={pending}
              />
              <button type="button" className="solid-button composer-send" onClick={() => void submit()} disabled={pending}>
                {pending ? "Scoring..." : "Submit"}
              </button>
            </div>
          </div>
        </div>
      </main>

      <aside className="right-drawer">
        <div className="drawer-card">
          <span className="rail-label">Conversation mode</span>
          <div className="focus-card">
            <strong>{session.state.mode === "think_it_through" ? "Guided build" : "Tight review"}</strong>
            <p>{session.state.mode === "think_it_through" ? "More teaching, more context, calmer follow-ups." : "Sharper pressure-testing with more direct follow-ups."}</p>
          </div>
        </div>

        <div className="drawer-card">
          <span className="rail-label">What matters</span>
          {reportHighlights.length === 0 ? (
            <p className="muted-copy">Stay concrete on user, problem, proof, and why this matters now.</p>
          ) : (
            <ul className="upload-list">
              {reportHighlights.map((item) => (
                <li key={item}>
                  <strong>{item}</strong>
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
        title="Change model"
        providerOptions={providerOptions}
        provider={runtimeProvider}
        model={runtimeModel}
        apiKey={runtimeApiKey}
        responseProfile="speed"
        applying={applyingRuntime}
        onClose={() => setRuntimeOpen(false)}
        onProviderChange={(provider) => {
          setRuntimeProvider(provider as SessionPayload["provider"]);
          setRuntimeModel(defaultModelForProvider(providerOptions, provider, "speed"));
        }}
        onModelChange={setRuntimeModel}
        onApiKeyChange={setRuntimeApiKey}
        onUseDefaultModel={(profile) => setRuntimeModel(defaultModelForProvider(providerOptions, runtimeProvider, profile))}
        onApply={() => void applyRuntime()}
      />
    </div>
  );
}
