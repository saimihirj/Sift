import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { EvaluatorMode, ProviderOption, ResponseProfile, SessionPayload, SessionSummary, ThemeMode } from "../../app/types";
import { ThemePicker } from "../../app/ThemePicker";
import { answerEvaluator, updateSessionRuntime } from "../../lib/api/client";
import { loadSessionCredential, saveSessionCredential } from "../../lib/sessionCredentials";
import { ALL_UPLOAD_EXTENSIONS, DECK_UPLOAD_EXTENSIONS, uploadAccept, uploadHint, validateUploadFile } from "../../lib/uploadValidation";
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
  onClearHistory: () => void;
  clearingHistory: boolean;
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

function tokenStatus(runtimeUsage: SessionPayload["runtimeUsage"] | undefined): string {
  const total = runtimeUsage?.last?.totalTokens ?? 0;
  if (!total) {
    return "";
  }
  return `${Math.round(total).toLocaleString()} tok${runtimeUsage?.last?.estimated ? " est." : ""}`;
}

export function EvaluatorScreen({
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
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [draft, setDraft] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [pending, setPending] = useState(false);
  const [statusLine, setStatusLine] = useState("");
  const [sessionsOpen, setSessionsOpen] = useState(false);
  const [runtimeOpen, setRuntimeOpen] = useState(false);
  const [progressOpen, setProgressOpen] = useState(false);
  const [themeOpen, setThemeOpen] = useState(false);
  const [completionOpen, setCompletionOpen] = useState(false);
  const [applyingRuntime, setApplyingRuntime] = useState(false);
  const [runtimeProvider, setRuntimeProvider] = useState<SessionPayload["provider"]>(session.provider);
  const [runtimeModel, setRuntimeModel] = useState(session.model);
  const [runtimeApiKey, setRuntimeApiKey] = useState(() => loadSessionCredential(session.sessionId)?.apiKey ?? "");
  const [evaluatorMode, setEvaluatorMode] = useState<EvaluatorMode>(session.evaluatorMode ?? "idea_review");

  useEffect(() => {
    setRuntimeProvider(session.provider);
    setRuntimeModel(session.model);
    setRuntimeApiKey(loadSessionCredential(session.sessionId)?.apiKey ?? "");
    setEvaluatorMode(session.evaluatorMode ?? "idea_review");
    setSessionsOpen(false);
    setRuntimeOpen(false);
    setProgressOpen(false);
    setThemeOpen(false);
    setCompletionOpen(false);
  }, [session.sessionId, session.provider, session.model]);

  const selectedProvider = useMemo(
    () => providerOptions.find((item) => item.key === runtimeProvider) ?? providerOptions[0] ?? null,
    [providerOptions, runtimeProvider],
  );
  const requiresClientApiKey = Boolean(selectedProvider?.requiresApiKey && !selectedProvider.serverConfigured);
  const effectiveModel = runtimeModel.trim() || defaultModelForProvider(providerOptions, runtimeProvider, "speed");

  const progress = session.evaluationProgress;
  const report = session.evaluationReport;
  const deckReport = session.deckEvaluationReport;
  const currentQuestion = progress?.currentQuestion ?? null;
  const showIntroCard = session.history.length <= 1;
  const canSwitchMode = session.history.length <= 1 && session.activeUploads.length === 0 && !progress?.completed;
  const runtimeSupportsVision = Boolean(session.supportsVision);
  const reportHighlights = useMemo(
    () => (progress?.completed ? (report?.nextExperiments ?? report?.suggestions ?? []).slice(0, 3) : []),
    [progress?.completed, report],
  );

  const selectedFileIsPdf = selectedFile?.name.toLowerCase().endsWith(".pdf") ?? false;
  const selectedFileIsPptx = selectedFile?.name.toLowerCase().endsWith(".pptx") ?? false;
  const allowedUploadExtensions = evaluatorMode === "deck_review" ? DECK_UPLOAD_EXTENSIONS : ALL_UPLOAD_EXTENSIONS;
  const currentUploadHint = uploadHint(allowedUploadExtensions);
  const deckReviewCapability = useMemo(() => {
    if (evaluatorMode !== "deck_review") {
      return null;
    }
    if (!runtimeSupportsVision) {
      return {
        label: "Text transcript review",
        note: "This model can review extracted deck text only. It will not pretend it saw layout or visuals.",
      };
    }
    if (selectedFileIsPptx) {
      return {
        label: "Text-first PPTX review",
        note: "This environment extracts slide text from PPTX. Export to PDF if you want the strongest slide-image review.",
      };
    }
    if (selectedFileIsPdf || session.activeUploads.some((item) => item.docType === "pitch deck" && item.hasRenderableSlides)) {
      return {
        label: "Vision-ready review",
        note: "This runtime can review PDF deck pages slide by slide and still call out anything missing or unverified.",
      };
    }
    return {
      label: "Vision-ready runtime",
      note: "PDF decks can be reviewed with slide-image evidence. PPTX decks may still fall back to extracted text.",
    };
  }, [evaluatorMode, runtimeSupportsVision, selectedFileIsPdf, selectedFileIsPptx, session.activeUploads]);

  const applyEvaluatorResponse = (response: Awaited<ReturnType<typeof answerEvaluator>>) => {
    const assistantMessage = response.evaluatorMode === "deck_review"
      ? response.reciprocal
      : response.evaluationProgress.completed
      ? `${response.reciprocal}\n\nI have enough. I’m building the report now.`
      : response.question
        ? `${response.reciprocal}\n\n${response.question.text}`
        : response.reciprocal;

    setSession((previous) => ({
      ...previous,
      history: [...previous.history, { role: "assistant", content: assistantMessage }],
      activeUploads: response.activeUploads,
      evaluatorMode: response.evaluatorMode,
      evaluationProgress: response.evaluationProgress,
      evaluationReport: response.evaluationReport ?? undefined,
      deckEvaluationReport: response.deckEvaluationReport ?? undefined,
      provider: runtimeProvider as SessionPayload["provider"],
      model: effectiveModel,
      supportsVision: response.supportsVision,
      runtimeUsage: response.runtimeUsage,
    }));
    const usageLabel = tokenStatus(response.runtimeUsage);
    setStatusLine(
      response.warning
        || `${response.evaluatorMode === "deck_review"
          ? (response.deckEvaluationReport?.reviewMode === "multimodal" ? "Deck review ready." : "Deck transcript review ready.")
          : (response.evaluationProgress.completed ? "Evaluation complete." : "Ready for the next step.")}${usageLabel ? ` · ${usageLabel}` : ""}`,
    );
    onSessionActivity();
    if (response.evaluationProgress.completed && response.evaluatorMode !== "deck_review") {
      setCompletionOpen(true);
    }
  };

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
        supportsVision: response.supportsVision,
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

  const handleFileSelected = (file: File | null) => {
    if (!file) {
      setSelectedFile(null);
      return;
    }
    const error = validateUploadFile(file, allowedUploadExtensions);
    if (error) {
      setSelectedFile(null);
      setStatusLine(error);
      return;
    }
    setSelectedFile(file);
    setStatusLine(`${file.name} ready · ${currentUploadHint}`);
  };

  const submit = async () => {
    if (progress?.completed) {
      if (evaluatorMode !== "deck_review") {
        setCompletionOpen(true);
        return;
      }
    }
    if ((!draft.trim() && !selectedFile) || pending) {
      return;
    }
    if (requiresClientApiKey && !runtimeApiKey.trim()) {
      setStatusLine(`Add an API key for ${selectedProvider?.label || runtimeProvider} to continue.`);
      setRuntimeOpen(true);
      return;
    }

    const displayMessage = draft.trim()
      ? selectedFile
        ? `${draft.trim()}\n\n[Attached ${selectedFile.name}]`
        : draft.trim()
      : `[Attached ${selectedFile?.name}]`;
    const submittedDraft = draft.trim();
    const submittedFile = selectedFile;
    const previousHistory = session.history;

    setSession((previous) => ({
      ...previous,
      history: [...previous.history, { role: "user", content: displayMessage }],
    }));
    setDraft("");
    setSelectedFile(null);
    setPending(true);
    setStatusLine(
      evaluatorMode === "deck_review"
        ? (submittedFile ? "Uploading and reviewing the deck..." : "Reviewing the active deck...")
        : (submittedFile ? "Uploading context and scoring..." : "Scoring your answer..."),
    );

    try {
      const response = await answerEvaluator({
        sessionId: session.sessionId,
        answer: submittedDraft,
        evaluatorMode,
        provider: runtimeProvider,
        model: effectiveModel,
        apiKey: runtimeApiKey.trim(),
        file: submittedFile,
      });
      if (runtimeApiKey.trim()) {
        saveSessionCredential(session.sessionId, {
          provider: runtimeProvider,
          model: effectiveModel,
          apiKey: runtimeApiKey.trim(),
        });
      }
      applyEvaluatorResponse(response);
    } catch (error) {
      setSession((previous) => ({
        ...previous,
        history: previousHistory,
      }));
      setDraft(submittedDraft);
      setSelectedFile(submittedFile);
      const message = error instanceof Error ? error.message : "Failed to score answer";
      if (message.toLowerCase().includes("already complete")) {
        setStatusLine("Evaluation complete.");
        setCompletionOpen(true);
      } else {
        setStatusLine(message);
      }
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="app-shell compact-workspace-shell">
      <main className="main-pane">
        <header className="pane-header">
          <div>
            <span className="eyebrow">Evaluate</span>
            <h2>Evaluate</h2>
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
                Status
              </button>
              <button type="button" className="ghost-button compact" onClick={() => setThemeOpen(true)}>
                Theme
              </button>
              {progress?.completed ? (
                <button type="button" className="ghost-button compact" onClick={() => navigate(`/evaluate/${session.sessionId}/report`)}>
                  Report
                </button>
              ) : null}
              <button type="button" className="ghost-button compact" onClick={onNewSession}>
                New
              </button>
              <button type="button" className="ghost-button compact" onClick={onExitSession}>
                Exit
              </button>
            </div>
            <small>
              {progress?.website?.warning
                ? String(progress.website.warning)
                : statusLine || (progress?.completed ? "Report ready" : evaluatorMode === "deck_review" ? "Waiting for the deck." : `${progress?.questionsAsked ?? 0} questions asked`)}
            </small>
          </div>
        </header>

        <div className="chat-panel evaluator-panel">
          <div className="evaluator-mode-row">
            <div className="segmented runtime-segmented">
              {([
                { key: "idea_review", label: "Idea review" },
                { key: "deck_review", label: "Deck review" },
              ] as Array<{ key: EvaluatorMode; label: string }>).map((option) => (
                <button
                  key={option.key}
                  type="button"
                  className={evaluatorMode === option.key ? "segment active" : "segment"}
                  onClick={() => {
                    if (canSwitchMode) {
                      setEvaluatorMode(option.key);
                    }
                  }}
                  disabled={!canSwitchMode && evaluatorMode !== option.key}
                >
                  {option.label}
                </button>
              ))}
            </div>
            {!canSwitchMode ? <small className="muted-copy">Mode locks after the first real submission to keep the report consistent.</small> : null}
          </div>

          {showIntroCard ? (
            <div className="evaluator-question-card evaluator-focus-card">
              <span className="rail-label">Evaluate</span>
              <strong>{evaluatorMode === "deck_review" ? "Start with the deck." : "Start with the pitch."}</strong>
              <p>
                {evaluatorMode === "deck_review"
                  ? "Upload the deck and I’ll judge it against the template, call out what is missing, and avoid guesswork."
                  : "Paste the pitch, notes, or URL. I’ll only ask what is still missing."}
              </p>
            </div>
          ) : null}

          <ChatMessageList
            history={session.history}
            streamingAssistant=""
            assistantLabel="Evaluate"
            sessionId={session.sessionId}
          />

          {progress?.completed && evaluatorMode !== "deck_review" ? (
            <div className="evaluator-complete-banner">
              <div className="evaluator-complete-copy">
                <span className="rail-label">Complete</span>
                <strong>Evaluation complete.</strong>
                <p>{progress.stopReason || "The report is ready. Review it when you want. If you want more pressure-testing, start it from the report."}</p>
              </div>
              <div className="completion-dialog-actions">
                <button type="button" className="solid-button compact" onClick={() => navigate(`/evaluate/${session.sessionId}/report`)}>
                  View report
                </button>
              </div>
            </div>
          ) : null}

          {(!progress?.completed || evaluatorMode === "deck_review") ? (
            <div className="composer-shell">
              {deckReviewCapability ? (
                <div className="focus-card evaluator-capability-card">
                  <span className="rail-label">{deckReviewCapability.label}</span>
                  <p>{deckReviewCapability.note}</p>
                </div>
              ) : null}
              <div className="attachment-row">
                <div className="attachment-meta">
                  <span className="rail-label">Context</span>
                  <small>{evaluatorMode === "deck_review" ? `Deck only · ${currentUploadHint}` : `Optional context · ${currentUploadHint}`}</small>
                </div>
                <div className="attachment-actions">
                  <button type="button" className="ghost-button compact" onClick={() => inputRef.current?.click()}>
                    {selectedFile ? "Change file" : "Upload file"}
                  </button>
                  {selectedFile ? <span className="attachment-pill">{selectedFile.name}</span> : null}
                  {selectedFile ? (
                    <button type="button" className="ghost-button compact" onClick={() => handleFileSelected(null)}>
                      Remove
                    </button>
                  ) : null}
                </div>
                <input
                  ref={inputRef}
                  type="file"
                  hidden
                  accept={uploadAccept(allowedUploadExtensions)}
                  onChange={(event) => {
                    handleFileSelected(event.target.files?.[0] ?? null);
                    event.currentTarget.value = "";
                  }}
                />
              </div>
              <div className="composer-row">
                <textarea
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder={
                    evaluatorMode === "deck_review"
                      ? (progress?.completed
                        ? "Ask about a slide, claim, rewrite, or what to fix next."
                        : "Optional focus for the review. Example: be ruthless on story flow and proof.")
                      : (currentQuestion ? "Answer naturally. Specifics help." : "Tell me what you are building, who it is for, and why it matters.")
                  }
                  rows={4}
                  disabled={pending}
                />
                <button type="button" className="solid-button composer-send" onClick={() => void submit()} disabled={pending}>
                  {evaluatorMode === "deck_review" && !progress?.completed ? "Review deck" : evaluatorMode === "deck_review" ? "Ask" : "Submit"}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </main>

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
        title="Change model"
        providerOptions={providerOptions}
        provider={runtimeProvider}
        model={runtimeModel}
        apiKey={runtimeApiKey}
        runtimeUsage={session.runtimeUsage}
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

      <div className={progressOpen ? "floating-panel is-open align-right" : "floating-panel align-right"} aria-hidden={!progressOpen}>
        <button type="button" className={progressOpen ? "floating-backdrop is-open" : "floating-backdrop"} onClick={() => setProgressOpen(false)} aria-label="Close progress" />
        <aside className={progressOpen ? "floating-card runtime-card is-open" : "floating-card runtime-card"}>
          <div className="floating-head">
            <div>
              <span className="rail-label">Progress</span>
              <strong>Evaluate details</strong>
            </div>
            <button type="button" className="ghost-button compact" onClick={() => setProgressOpen(false)}>
              Close
            </button>
          </div>
          <div className="floating-scroll">
            <div className="drawer-card">
              <span className="rail-label">Assessment</span>
              <div className="focus-card">
                <strong>{evaluatorMode === "deck_review" ? "Deck review" : "Adaptive flow"}</strong>
                <p>
                  {evaluatorMode === "deck_review"
                    ? "Deck review uses the uploaded deck as the primary evidence source and marks missing sections instead of guessing."
                    : "Evaluate asks only what is still missing, then stops as soon as the report is justified."}
                </p>
              </div>
              <small className="muted-copy">
                {evaluatorMode === "deck_review"
                  ? (deckReport?.reviewMode === "multimodal" ? "Slide-image review active" : "Transcript review active")
                  : `${progress?.questionsAsked ?? progress?.answeredQuestions ?? 0} questions asked`}
              </small>
              {progress?.stopReason ? <small className="muted-copy">{progress.stopReason}</small> : null}
            </div>
            <div className="drawer-card">
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
                  <dt>Review</dt>
                  <dd>{evaluatorMode === "deck_review" ? (deckReport?.reviewMode === "multimodal" || runtimeSupportsVision ? "Deck review" : "Deck transcript review") : "Idea review"}</dd>
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
            <div className="drawer-card">
              <span className="rail-label">What matters</span>
              {reportHighlights.length === 0 ? (
                <p className="muted-copy">
                  {evaluatorMode === "deck_review"
                    ? "The best deck reviews stay concrete on missing evidence, weak claims, story flow, and what each slide still needs to prove."
                    : "Stay concrete on the pitch, user pain, proof, and why this matters now."}
                </p>
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
          </div>
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

      <div className={completionOpen ? "floating-panel is-open" : "floating-panel"} aria-hidden={!completionOpen}>
        <button
          type="button"
          className={completionOpen ? "floating-backdrop is-open" : "floating-backdrop"}
          onClick={() => setCompletionOpen(false)}
          aria-label="Close completion dialog"
        />
        <aside className={completionOpen ? "completion-dialog is-open" : "completion-dialog"}>
          <span className="rail-label">Evaluate</span>
          <strong>We&apos;re done with this evaluation.</strong>
          <p>
            {progress?.canGoDeeper
              ? "The report is ready. Open it to review the verdict, fixes, and next experiments. If you want more questions, start that from the report."
              : "The report is ready. Open it to review the verdict, fixes, and next experiments."}
          </p>
          <div className="completion-dialog-actions">
            <button type="button" className="ghost-button" onClick={() => setCompletionOpen(false)}>
              Stay here
            </button>
            <button type="button" className="solid-button" onClick={() => navigate(`/evaluate/${session.sessionId}/report`)}>
              View report
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
}
