import { useMemo, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";

import type { HelpMode, Provider, ProviderOption, SetupDraft } from "../../app/types";

type Props = {
  providerOptions: ProviderOption[];
  loading: boolean;
  error: string;
  canStart: boolean;
  step: number;
  draft: SetupDraft;
  onStepChange: (step: number) => void;
  onDraftChange: (updater: (current: SetupDraft) => SetupDraft) => void;
  onBack: () => void;
  onStart: (payload: {
    sessionType: SetupDraft["sessionType"];
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
  { value: "think_it_through", label: "Guided build", note: "Calmer coaching with more teaching." },
  { value: "quick_stress_test", label: "Pressure test", note: "Sharper follow-ups and less cushioning." },
];

const workflowOptions: Array<{ value: SetupDraft["sessionType"]; label: string; note: string }> = [
  { value: "mentor", label: "Ideate", note: "Open-ended refinement, back and forth." },
  { value: "evaluator", label: "Evaluate", note: "Adaptive interview, final score and report at the end." },
  { value: "expert", label: "Expert", note: "Discuss concepts, compare options, analyze decks, and pre-screen ideas." },
];

const geographyOptions: Array<{ value: string; label: string }> = [
  { value: "auto", label: "Auto" },
  { value: "india", label: "India" },
  { value: "us", label: "US" },
  { value: "global", label: "Global" },
];

const helpModeOptions: Array<{ value: HelpMode; label: string; note: string }> = [
  { value: "coach_me", label: "Coach me", note: "Answer, then ask one sharp follow-up." },
  { value: "challenge_me", label: "Challenge me", note: "Push harder on weak assumptions." },
  { value: "explain_directly", label: "Explain directly", note: "Give the straight answer first." },
];

const workflowGuides: Record<SetupDraft["sessionType"], { label: string; title: string; body: string }> = {
  mentor: {
    label: "Ideate flow",
    title: "Open-ended shaping",
    body: "Best when the idea is still rough and you want a sharper back-and-forth on the problem, wedge, customer, and pitch story.",
  },
  evaluator: {
    label: "Evaluate flow",
    title: "Structured pressure test",
    body: "Best when you want the platform to interview the idea, stop when it has enough evidence, and produce a report with fixes.",
  },
  expert: {
    label: "Expert flow",
    title: "Domain discussion and analysis",
    body: "Best when you want concept explanations, comparisons, pre-screening, or evidence-backed discussion over startup, VC, finance, or regulation.",
  },
};

function stepTitle(step: number) {
  if (step === 0) return "Pick a model";
  if (step === 1) return "Set your context";
  return "Choose the workflow";
}

function stepSubtitle(step: number) {
  if (step === 0) return "Stay local or use your own API key for this session.";
  if (step === 1) return "Role, scope, and geography make the workbench sharper from the first turn.";
  return "Pick how SignalX should work with you on this session.";
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

export function SetupWizard({ providerOptions, loading, error, canStart, step, draft, onStepChange, onDraftChange, onBack, onStart }: Props) {
  const [optionalContextOpen, setOptionalContextOpen] = useState(false);
  const [advancedControlsOpen, setAdvancedControlsOpen] = useState(false);
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
  const canAdvanceRuntime = Boolean(resolvedModel) && (draft.runtimeKind === "local" || draft.apiKey.trim());
  const workflowGuide = workflowGuides[draft.sessionType];
  const showAdvancedControls = draft.sessionType === "expert" || advancedControlsOpen;

  return (
    <section className="onboarding-shell">
      <div className="onboarding-card clean-wizard-card">
        <div className="onboarding-meta">
          <div className="plain-header-block">
            <span className="eyebrow">Setup</span>
            <strong>Session</strong>
          </div>
          <div className="step-dots" aria-hidden="true">
            {[0, 1, 2].map((value) => (
              <span key={value} className={value === step ? "dot active" : "dot"} />
            ))}
          </div>
        </div>

        <div className="onboarding-copy">
          <h1>{stepTitle(step)}</h1>
          <p>{stepSubtitle(step)}</p>
        </div>

        {error ? <div className="setup-alert" role="alert">{error}</div> : null}

        {step === 0 ? (
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
                <span>Local open source</span>
                <small>Runs through Ollama on this machine.</small>
              </button>
              <button
                type="button"
                className={draft.runtimeKind === "external" ? "choice-card active" : "choice-card"}
                onClick={() => {
                  const firstExternal = providerOptions.find((item) => item.key !== "ollama");
                  onDraftChange((current) => ({
                    ...current,
                    runtimeKind: "external",
                    provider: firstExternal?.key ?? "groq",
                    model: firstExternal?.defaultBalancedModel || firstExternal?.defaultSpeedModel || current.model,
                  }));
                }}
              >
                <span>Use API key</span>
                <small>Switch to another provider for this session only.</small>
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
                    <small>{option.requiresApiKey ? "API key" : "Local"}</small>
                  </button>
                ))}
              </div>
            </div>

            <div className="drawer-card">
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
                    <span className="rail-label">API key</span>
                    <input
                      type="password"
                      value={draft.apiKey}
                      onChange={(event) => onDraftChange((current) => ({ ...current, apiKey: event.target.value }))}
                      placeholder="Paste the key for this session"
                    />
                  </label>
                ) : (
                  <div className="starter-preview">
                    <span className="rail-label">Runtime</span>
                    <strong>Zero-key local mode</strong>
                    <small>Stays on-device and keeps setup light.</small>
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
                </div>
              ) : (
                <p className="muted-copy">You can skip this and add detail later inside the session.</p>
              )}
            </div>
          </>
        ) : null}

        {step === 2 ? (
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
              <span className="rail-label">{workflowGuide.label}</span>
              <div className="focus-card">
                <strong>{workflowGuide.title}</strong>
                <p>{workflowGuide.body}</p>
              </div>
            </div>

            <div className="drawer-card">
              <span className="rail-label">Conversation style</span>
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

            {showAdvancedControls ? (
              <>
                <div className="drawer-card">
                  <div className="setup-section-head">
                    <div>
                      <span className="rail-label">Mode of help</span>
                      {draft.sessionType !== "expert" ? <strong>Advanced control</strong> : null}
                    </div>
                    {draft.sessionType !== "expert" ? (
                      <button type="button" className="ghost-button compact" onClick={() => setAdvancedControlsOpen(false)}>
                        Hide
                      </button>
                    ) : null}
                  </div>
                  <div className="workflow-row" onKeyDown={handleArrowSelection}>
                    {helpModeOptions.map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        className={draft.helpMode === option.value ? "choice-card active" : "choice-card"}
                        onClick={() => onDraftChange((current) => ({ ...current, helpMode: option.value }))}
                      >
                        <span>{option.label}</span>
                        <small>{option.note}</small>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="drawer-card">
                  <span className="rail-label">Knowledge behavior</span>
                  <div className="workflow-row" onKeyDown={handleArrowSelection}>
                    <button
                      type="button"
                      className={!draft.liveWebEnabled ? "choice-card active" : "choice-card"}
                      onClick={() => onDraftChange((current) => ({ ...current, liveWebEnabled: false }))}
                    >
                      <span>Local corpus first</span>
                      <small>Stay on the curated knowledge base unless the corpus is thin.</small>
                    </button>
                    <button
                      type="button"
                      className={draft.liveWebEnabled ? "choice-card active" : "choice-card"}
                      onClick={() => onDraftChange((current) => ({ ...current, liveWebEnabled: true }))}
                    >
                      <span>Allow live web fallback</span>
                      <small>Use labeled live web results for freshness or KB gaps.</small>
                    </button>
                  </div>
                </div>
              </>
            ) : (
              <div className="drawer-card">
                <div className="setup-section-head">
                  <div>
                    <span className="rail-label">Advanced controls</span>
                    <strong>Help mode and live-web fallback</strong>
                  </div>
                  <button type="button" className="ghost-button compact" onClick={() => setAdvancedControlsOpen(true)}>
                    Show
                  </button>
                </div>
                <p className="muted-copy">Defaults are safe for Ideate and Evaluate. Expert keeps these controls visible because they change behavior more directly.</p>
              </div>
            )}
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
            <button
              type="button"
              className="solid-button"
              onClick={() => onStepChange(step + 1)}
              disabled={step === 0 && !canAdvanceRuntime}
            >
              Continue
            </button>
          ) : (
            <button
              type="button"
              className="solid-button"
              disabled={loading || !canStart}
              onClick={() =>
                void onStart({
                  sessionType: draft.sessionType,
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
                  liveWebEnabled: draft.liveWebEnabled,
                })
              }
            >
              {loading ? "Starting..." : "Start session"}
            </button>
          )}
        </div>

        {step === 2 && !canStart ? (
          <small className="setup-inline-hint">Name missing. Click back and enter your name on the first screen.</small>
        ) : null}
      </div>
    </section>
  );
}
