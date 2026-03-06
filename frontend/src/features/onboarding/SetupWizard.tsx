import { useMemo, type KeyboardEvent as ReactKeyboardEvent } from "react";

import { SignalLockup } from "../../app/SignalBrand";
import type { Provider, ProviderOption, SetupDraft } from "../../app/types";

type Props = {
  providerOptions: ProviderOption[];
  loading: boolean;
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
    mode: SetupDraft["mode"];
    provider: Provider;
    model: string;
    apiKey: string;
    questionBudget: 10 | 15 | 20;
    websiteUrl: string;
    setupContext: string;
  }) => Promise<void>;
};

const founderOptions: Array<{ value: SetupDraft["founderType"]; label: string }> = [
  { value: "student", label: "Student innovator" },
  { value: "professional", label: "Working professional" },
  { value: "founder", label: "First-time founder" },
  { value: "serial", label: "Repeat founder" },
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
];

const budgetOptions: Array<{ value: 10 | 15 | 20; label: string; note: string }> = [
  { value: 10, label: "10 questions", note: "Fast screen" },
  { value: 15, label: "15 questions", note: "Best default" },
  { value: 20, label: "20 questions", note: "Deeper pass" },
];

function stepTitle(step: number) {
  if (step === 0) return "Choose your runtime";
  if (step === 1) return "Tell me the context";
  return "Pick the session style";
}

function stepSubtitle(step: number) {
  if (step === 0) return "Use local open-source models or bring your own provider key for this session.";
  if (step === 1) return "This keeps the next conversation adaptive without wasting time on basics.";
  return "Ideate stays open-ended. Evaluate stays conversational and gives the score only at the end.";
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

export function SetupWizard({ providerOptions, loading, step, draft, onStepChange, onDraftChange, onBack, onStart }: Props) {
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

  const resolvedProvider = draft.runtimeKind === "local" ? "ollama" : (providerMeta?.key ?? "cerebras");
  const resolvedModel = draft.model.trim()
    || (draft.runtimeKind === "local"
      ? providerMeta?.defaultSpeedModel
      : providerMeta?.defaultBalancedModel || providerMeta?.defaultSpeedModel)
    || "";
  const canAdvanceRuntime = Boolean(resolvedModel) && (draft.runtimeKind === "local" || draft.apiKey.trim());

  return (
    <section className="onboarding-shell">
      <div className="onboarding-card clean-wizard-card">
        <div className="onboarding-meta">
          <SignalLockup compact showTagline={false} />
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
                    provider: firstExternal?.key ?? "cerebras",
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
              <span className="rail-label">Founder type</span>
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
                  <span className="rail-label">What should the first reply know?</span>
                  <textarea
                    value={draft.setupContext}
                    onChange={(event) => onDraftChange((current) => ({ ...current, setupContext: event.target.value }))}
                    placeholder="Short summary, draft idea, current users, deck notes, or anything else that helps the conversation start deeper."
                    rows={5}
                  />
                </label>
              </div>
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

            {draft.sessionType === "evaluator" ? (
              <div className="drawer-card">
                <span className="rail-label">Assessment depth</span>
                <div className="workflow-row" onKeyDown={handleArrowSelection}>
                  {budgetOptions.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      className={draft.questionBudget === option.value ? "choice-card active" : "choice-card"}
                      onClick={() => onDraftChange((current) => ({ ...current, questionBudget: option.value }))}
                    >
                      <span>{option.label}</span>
                      <small>{option.note}</small>
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
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
              disabled={loading}
              onClick={() =>
                void onStart({
                  sessionType: draft.sessionType,
                  founderType: draft.founderType,
                  sector: draft.sector,
                  stage: draft.stage,
                  mode: draft.mode,
                  provider: resolvedProvider as Provider,
                  model: resolvedModel,
                  apiKey: draft.runtimeKind === "external" ? draft.apiKey.trim() : "",
                  questionBudget: draft.questionBudget,
                  websiteUrl: draft.websiteUrl,
                  setupContext: draft.setupContext,
                })
              }
            >
              {loading ? "Starting..." : "Start session"}
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
