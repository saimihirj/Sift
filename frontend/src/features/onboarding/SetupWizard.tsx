import { useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";

import { ThemePicker } from "../../app/ThemePicker";
import type { HelpMode, Provider, ProviderOption, SessionSummary, SetupDraft, ThemeMode } from "../../app/types";

type Props = {
  providerOptions: ProviderOption[];
  loading: boolean;
  error: string;
  canStart: boolean;
  step: number;
  draft: SetupDraft;
  theme: ThemeMode;
  onThemeChange: (theme: ThemeMode) => void;
  identityLabel: string;
  identityKey: string;
  recentSessions: SessionSummary[];
  onStepChange: (step: number) => void;
  onDraftChange: (updater: (current: SetupDraft) => SetupDraft) => void;
  onOpenSession: (sessionId: string) => void | Promise<void>;
  onSwitchIdentity: () => void;
  onBack: () => void;
  onStart: (payload: {
    sessionType: SetupDraft["sessionType"];
    evaluatorMode: SetupDraft["evaluatorMode"];
    founderType: SetupDraft["founderType"];
    sector: SetupDraft["sector"];
    stage: SetupDraft["stage"];
    geography: string;
    mode: SetupDraft["mode"];
    provider: Provider;
    model: string;
    apiKey: string;
    websiteUrl: string;
    setupContext: string;
    helpMode: HelpMode;
    liveWebEnabled: boolean;
  }) => Promise<void>;
};

const founderOptions: Array<{ value: SetupDraft["founderType"]; label: string }> = [
  { value: "student", label: "Student" },
  { value: "operator", label: "Operator" },
  { value: "founder", label: "Founder" },
  { value: "investor", label: "Investor" },
  { value: "professional", label: "Working professional" },
  { value: "serial", label: "Repeat founder" },
  { value: "other", label: "Other" },
];

const sectorOptions: Array<{ value: SetupDraft["sector"]; label: string }> = [
  { value: "saas", label: "Software / SaaS" },
  { value: "d2c", label: "Consumer / D2C" },
  { value: "fintech", label: "Fintech" },
  { value: "marketplace", label: "Marketplace" },
  { value: "edtech", label: "Education" },
  { value: "healthtech", label: "Health" },
  { value: "deeptech", label: "Deep tech / AI" },
  { value: "unknown", label: "Other" },
];

const stageOptions: Array<{ value: SetupDraft["stage"]; label: string }> = [
  { value: "idea", label: "Exploring" },
  { value: "pre-revenue", label: "Testing or building" },
  { value: "early-revenue", label: "Early proof" },
  { value: "growth", label: "Growing" },
];

const modeOptions: Array<{ value: SetupDraft["mode"]; label: string; note: string }> = [
  { value: "think_it_through", label: "Guided", note: "Build with help." },
  { value: "quick_stress_test", label: "Direct", note: "Find weak spots." },
];

const workflowOptions: Array<{ value: SetupDraft["sessionType"]; label: string; note: string }> = [
  { value: "mentor", label: "Ideate", note: "Sharper pitch draft." },
  { value: "evaluator", label: "Evaluate", note: "Score and report." },
  { value: "expert", label: "Expert", note: "Evidence-backed answer." },
];

const geographyOptions: Array<{ value: string; label: string }> = [
  { value: "auto", label: "Auto" },
  { value: "india", label: "India" },
  { value: "us", label: "US" },
  { value: "global", label: "Global" },
];

const sampleContexts = [
  {
    label: "Sample SaaS",
    context: "We are building a workflow intelligence platform for finance teams that catches reconciliation errors before month-end close. The first wedge is mid-market companies using spreadsheets and ERP exports. We have spoken with 9 finance managers and found that close delays usually come from duplicate manual checks.",
    sector: "saas",
    stage: "pre-revenue",
  },
  {
    label: "Sample marketplace",
    context: "We are testing a curated marketplace that helps boutique hotels find verified local experience operators. Hotels currently use informal WhatsApp networks and manual vendor checks. The first experiment is a concierge MVP with 5 hotels and 20 operators in one city.",
    sector: "marketplace",
    stage: "idea",
  },
] as const;

const stepLabels = ["Workflow", "Context", "Runtime"];

function formatSessionTime(raw?: string | null): string {
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

function providerAccessLabel(option: ProviderOption | undefined): string {
  if (!option) {
    return "Runtime";
  }
  if (!option.requiresApiKey) {
    return "Local";
  }
  return option.serverConfigured ? "Server ready" : "Bring key";
}

function modelPresetLabel(option: ProviderOption | undefined, profile: "speed" | "balanced"): string {
  if (!option) {
    return profile === "speed" ? "Fast" : "Sharper";
  }
  return profile === "speed"
    ? option.speedLabel || "Fast"
    : option.balancedLabel || "Sharper";
}

function stepTitle(step: number) {
  if (step === 0) return "What do you want to do?";
  if (step === 1) return "About you";
  return "AI engine";
}

function stepSubtitle(step: number) {
  if (step === 0) return "Pick the output you need right now.";
  if (step === 1) return "A little context improves the result.";
  return "Groq is the fastest hosted open-weight path; Ollama stays local.";
}

function handleArrowSelection(event: ReactKeyboardEvent<HTMLElement>) {
  if (!["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(event.key)) {
    return;
  }
  const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"));
  if (buttons.length < 2) {
    return;
  }
  const currentIndex = buttons.findIndex((button) => button === document.activeElement);
  const fallbackIndex = buttons.findIndex((button) => button.classList.contains("active"));
  const activeIndex = currentIndex >= 0 ? currentIndex : Math.max(fallbackIndex, 0);
  const direction = event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : -1;
  const nextIndex = (activeIndex + direction + buttons.length) % buttons.length;
  const nextButton = buttons[nextIndex];
  event.preventDefault();
  nextButton.focus();
  nextButton.click();
}

export function SetupWizard({
  providerOptions,
  loading,
  error,
  canStart,
  step,
  draft,
  theme,
  onThemeChange,
  identityLabel,
  identityKey,
  recentSessions,
  onStepChange,
  onDraftChange,
  onOpenSession,
  onSwitchIdentity,
  onBack,
  onStart,
}: Props) {
  const [optionalContextOpen, setOptionalContextOpen] = useState(false);
  const [identityKeyCopied, setIdentityKeyCopied] = useState(false);
  const cardRef = useRef<HTMLDivElement | null>(null);
  const filteredProviders = useMemo(
    () => (draft.runtimeKind === "local" ? providerOptions.filter((item) => item.key === "ollama") : providerOptions.filter((item) => item.key !== "ollama")),
    [providerOptions, draft.runtimeKind],
  );
  const providerMeta = useMemo(() => {
    const fallback = draft.runtimeKind === "local"
      ? providerOptions.find((item) => item.key === "ollama")
      : filteredProviders[0];
    return providerOptions.find((item) => item.key === draft.provider) ?? fallback ?? providerOptions[0];
  }, [draft.provider, draft.runtimeKind, filteredProviders, providerOptions]);

  const resolvedProvider = draft.runtimeKind === "local" ? "ollama" : (providerMeta?.key ?? "groq");
  const resolvedModel = draft.model.trim()
    || (draft.runtimeKind === "local"
      ? providerMeta?.defaultSpeedModel
      : providerMeta?.defaultBalancedModel || providerMeta?.defaultSpeedModel)
    || "";
  const requiresClientApiKey = Boolean(providerMeta?.requiresApiKey && !providerMeta.serverConfigured);
  const canAdvanceRuntime = Boolean(resolvedModel) && (draft.runtimeKind === "local" || !requiresClientApiKey || draft.apiKey.trim());
  const canStartFromCurrentStep = canStart && canAdvanceRuntime && !loading;

  const startWithCurrentDraft = () => onStart({
    sessionType: draft.sessionType,
    evaluatorMode: draft.evaluatorMode,
    founderType: draft.founderType,
    sector: draft.sector,
    stage: draft.stage,
    geography: draft.geography,
    mode: draft.mode,
    provider: resolvedProvider as Provider,
    model: resolvedModel,
    apiKey: draft.runtimeKind === "external" ? draft.apiKey.trim() : "",
    websiteUrl: draft.websiteUrl,
    setupContext: draft.setupContext,
    helpMode: draft.helpMode,
    liveWebEnabled: draft.sessionType === "expert" ? true : draft.liveWebEnabled,
  });

  const copyIdentityKey = async () => {
    if (!identityKey) {
      return;
    }
    try {
      await navigator.clipboard.writeText(identityKey);
      setIdentityKeyCopied(true);
      window.setTimeout(() => setIdentityKeyCopied(false), 1800);
    } catch {
      setIdentityKeyCopied(false);
    }
  };

  useEffect(() => {
    cardRef.current?.scrollTo({ top: 0 });
  }, [step]);

  return (
    <section className="onboarding-shell">
      <div className="onboarding-card clean-wizard-card" ref={cardRef}>
        <div className="onboarding-meta">
          <div className="plain-header-block">
            <span className="eyebrow">Setup</span>
            <strong>{identityLabel ? `Workspace: ${identityLabel}` : "Session"}</strong>
          </div>
          <div className="setup-key-actions">
            <button type="button" className="ghost-button compact" onClick={() => void copyIdentityKey()} disabled={!identityKey}>
              {identityKeyCopied ? "Key copied" : "Copy key"}
            </button>
            <button type="button" className="ghost-button compact" onClick={onSwitchIdentity}>
              Switch key
            </button>
          </div>
          <div className="step-dots step-dots-clickable" aria-label="Jump to setup section">
            {[0, 1, 2].map((value) => (
              <button
                key={value}
                type="button"
                className={value === step ? "dot active" : "dot"}
                onClick={() => onStepChange(value)}
                aria-label={stepLabels[value]}
                aria-current={value === step ? "step" : undefined}
              />
            ))}
          </div>
          <ThemePicker theme={theme} onChange={onThemeChange} />
        </div>

        <div className="onboarding-copy">
          <h1>{stepTitle(step)}</h1>
          <p>{stepSubtitle(step)}</p>
        </div>

        <div className="beta-note-card">
          <span className="rail-label">Beta</span>
          <p>Sift is ready for controlled user testing. Keep sensitive decks private unless you trust the selected model provider.</p>
        </div>

        {recentSessions.length > 0 ? (
          <div className="drawer-card">
            <div className="setup-section-head">
              <div>
                <span className="rail-label">Previous sessions</span>
                <strong>Resume this workspace directly.</strong>
              </div>
            </div>
            <div className="session-list setup-session-list">
              {recentSessions.slice(0, 4).map((item) => (
                <button
                  key={item.sessionId}
                  type="button"
                  className="session-card"
                  onClick={() => void onOpenSession(item.sessionId)}
                >
                  <strong>{item.title}</strong>
                  <span>{item.subtitle}</span>
                  <span>{formatSessionTime(item.lastActive)}</span>
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {error ? <div className="setup-alert" role="alert">{error}</div> : null}

        {step === 2 ? (
          <>
            <div className="workflow-row" onKeyDown={handleArrowSelection}>
              <button
                type="button"
                className={draft.runtimeKind === "local" ? "choice-card active" : "choice-card"}
                onClick={() => {
                  const ollama = providerOptions.find((item) => item.key === "ollama");
                  onDraftChange((current) => ({
                    ...current,
                    runtimeKind: "local",
                    provider: "ollama",
                    model: ollama?.defaultSpeedModel || current.model,
                    apiKey: "",
                  }));
                }}
              >
                <span>Local</span>
                <small>Runs on this machine.</small>
              </button>
              <button
                type="button"
                className={draft.runtimeKind === "external" ? "choice-card active" : "choice-card"}
                onClick={() => {
                  const firstExternal = providerOptions.find((item) => item.key !== "ollama" && item.serverConfigured)
                    ?? providerOptions.find((item) => item.key !== "ollama");
                  onDraftChange((current) => ({
                    ...current,
                    runtimeKind: "external",
                    provider: firstExternal?.key ?? "groq",
                    model: firstExternal?.defaultBalancedModel || firstExternal?.defaultSpeedModel || current.model,
                  }));
                }}
              >
                <span>Hosted</span>
                <small>Use API models.</small>
              </button>
            </div>

            <div className="drawer-card">
              <span className="rail-label">Provider</span>
              <div className="runtime-provider-grid" onKeyDown={handleArrowSelection}>
                {filteredProviders.map((option) => (
                  <button
                    key={option.key}
                    type="button"
                    className={resolvedProvider === option.key ? "chip-card active" : "chip-card"}
                    onClick={() => {
                      onDraftChange((current) => ({
                        ...current,
                        provider: option.key,
                        model: draft.runtimeKind === "local"
                          ? option.defaultSpeedModel
                          : option.defaultBalancedModel || option.defaultSpeedModel,
                      }));
                    }}
                  >
                    <span>{option.label}</span>
                    <small>{providerAccessLabel(option)}</small>
                  </button>
                ))}
              </div>
            </div>

            <div className="drawer-card">
              <div className="runtime-recommendation-card">
                <div>
                  <span className="rail-label">{providerAccessLabel(providerMeta)}</span>
                  <strong>{providerMeta?.label || "Runtime"}</strong>
                </div>
                <p>{draft.runtimeKind === "local" ? "Private by default." : "Best for public demos."}</p>
              </div>
              <div className="runtime-preset-row">
                <button
                  type="button"
                  className={resolvedModel === providerMeta?.defaultSpeedModel ? "runtime-preset active" : "runtime-preset"}
                  onClick={() => onDraftChange((current) => ({ ...current, model: providerMeta?.defaultSpeedModel || current.model }))}
                >
                  <span>Fast</span>
                  <strong>{modelPresetLabel(providerMeta, "speed")}</strong>
                </button>
                <button
                  type="button"
                  className={resolvedModel === providerMeta?.defaultBalancedModel ? "runtime-preset active" : "runtime-preset"}
                  onClick={() => onDraftChange((current) => ({ ...current, model: providerMeta?.defaultBalancedModel || current.model }))}
                >
                  <span>Sharper</span>
                  <strong>{modelPresetLabel(providerMeta, "balanced")}</strong>
                </button>
              </div>
              <div className="field-grid">
                <label className="identity-field">
                  <span className="rail-label">Model</span>
                  <input
                    value={resolvedModel}
                    onChange={(event) => onDraftChange((current) => ({ ...current, model: event.target.value }))}
                    placeholder={resolvedProvider === "cerebras" ? "Example: gpt-oss-120b" : "Type the model id"}
                  />
                </label>
                {draft.runtimeKind === "external" ? (
                  <label className="identity-field">
                    <span className="rail-label">{providerMeta?.serverConfigured ? "Session API key override" : "API key"}</span>
                    <input
                      type="password"
                      value={draft.apiKey}
                      onChange={(event) => onDraftChange((current) => ({ ...current, apiKey: event.target.value }))}
                      placeholder={providerMeta?.serverConfigured ? "Optional override" : "Paste key"}
                    />
                    {providerMeta?.serverConfigured ? <small className="muted-copy">Server key ready.</small> : null}
                  </label>
                ) : (
                  <div className="starter-preview">
                    <span className="rail-label">Runtime</span>
                    <strong>Key-free</strong>
                    <small>Ollama</small>
                  </div>
                )}
              </div>
            </div>
          </>
        ) : null}

        {step === 1 ? (
          <>
            <div className="drawer-card">
              <span className="rail-label">Role</span>
              <div className="chip-grid" onKeyDown={handleArrowSelection}>
                {founderOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    className={draft.founderType === option.value ? "chip-card active" : "chip-card"}
                    onClick={() => onDraftChange((current) => ({ ...current, founderType: option.value }))}
                  >
                    <span>{option.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="drawer-card">
              <span className="rail-label">Sector</span>
              <div className="chip-grid" onKeyDown={handleArrowSelection}>
                {sectorOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    className={draft.sector === option.value ? "chip-card active" : "chip-card"}
                    onClick={() => onDraftChange((current) => ({ ...current, sector: option.value }))}
                  >
                    <span>{option.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="drawer-card">
              <span className="rail-label">Stage</span>
              <div className="chip-grid" onKeyDown={handleArrowSelection}>
                {stageOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    className={draft.stage === option.value ? "chip-card active" : "chip-card"}
                    onClick={() => onDraftChange((current) => ({ ...current, stage: option.value }))}
                  >
                    <span>{option.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="drawer-card">
              <div className="identity-field field-span">
                <span className="rail-label">Geography</span>
                <div className="chip-grid" onKeyDown={handleArrowSelection}>
                  {geographyOptions.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      className={draft.geography === option.value ? "chip-card active" : "chip-card"}
                      onClick={() => onDraftChange((current) => ({ ...current, geography: option.value }))}
                    >
                      <span>{option.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="drawer-card">
              <div className="setup-section-head">
                <div>
                  <span className="rail-label">Optional context</span>
                  <strong>Add a website or notes only if it helps.</strong>
                </div>
                <button type="button" className="ghost-button compact" onClick={() => setOptionalContextOpen((current) => !current)}>
                  {optionalContextOpen ? "Hide" : "Add context"}
                </button>
              </div>
              {optionalContextOpen ? (
                <div className="field-grid">
                  <label className="identity-field field-span">
                    <span className="rail-label">Website URL</span>
                    <input
                      value={draft.websiteUrl}
                      onChange={(event) => onDraftChange((current) => ({ ...current, websiteUrl: event.target.value }))}
                      placeholder="https://yourproduct.com"
                    />
                    <small className="muted-copy">Website review uses the first readable HTML page as context in this beta.</small>
                  </label>
                  <label className="identity-field field-span">
                    <span className="rail-label">Anything important?</span>
                    <textarea
                      value={draft.setupContext}
                      onChange={(event) => onDraftChange((current) => ({ ...current, setupContext: event.target.value }))}
                      placeholder="Idea summary, current users, deck notes, or anything else useful."
                      rows={5}
                    />
                  </label>
                  <div className="sample-starter-row field-span">
                    {sampleContexts.map((sample) => (
                      <button
                        key={sample.label}
                        type="button"
                        className="ghost-button compact"
                        onClick={() => onDraftChange((current) => ({
                          ...current,
                          setupContext: sample.context,
                          sector: sample.sector,
                          stage: sample.stage,
                        }))}
                      >
                        {sample.label}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="muted-copy">You can skip this and add detail later inside the session.</p>
              )}
            </div>
          </>
        ) : null}

        {step === 0 ? (
          <>
            <div className="workflow-row" onKeyDown={handleArrowSelection}>
              {workflowOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={draft.sessionType === option.value ? "choice-card active" : "choice-card"}
                  onClick={() => onDraftChange((current) => ({ ...current, sessionType: option.value }))}
                >
                  <span>{option.label}</span>
                  <small>{option.note}</small>
                </button>
              ))}
            </div>

            <div className="drawer-card">
              <span className="rail-label">Style</span>
              <div className="workflow-row" onKeyDown={handleArrowSelection}>
                {modeOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    className={draft.mode === option.value ? "choice-card active" : "choice-card"}
                    onClick={() => onDraftChange((current) => ({ ...current, mode: option.value }))}
                  >
                    <span>{option.label}</span>
                    <small>{option.note}</small>
                  </button>
                ))}
              </div>
            </div>

          </>
        ) : null}

        <div className="onboarding-actions">
          <button
            type="button"
            className="ghost-button"
            onClick={() => {
              if (step === 0) {
                onBack();
                return;
              }
              onStepChange(step - 1);
            }}
          >
            Back
          </button>

          {step < 2 ? (
            <>
              <button
                type="button"
                className="ghost-button"
                disabled={!canStartFromCurrentStep}
                onClick={() => void startWithCurrentDraft()}
              >
                Start now
              </button>
              <button
                type="button"
                className="solid-button"
                onClick={() => onStepChange(step + 1)}
              >
                Continue
              </button>
            </>
          ) : (
            <button
              type="button"
              className="solid-button"
              disabled={loading || !canStart || !canAdvanceRuntime}
              onClick={() => void startWithCurrentDraft()}
            >
              {loading ? "Starting..." : "Start session"}
            </button>
          )}
        </div>

        {step === 2 && !canStart ? (
          <small className="setup-inline-hint">Workspace key missing. Switch key to enter your identity first.</small>
        ) : null}
      </div>
    </section>
  );
}
