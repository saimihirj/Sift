import { useMemo, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";

import type { FounderType, Mode, Provider, ProviderOption, Sector, SessionType, Stage } from "../../app/types";

type Props = {
  providerOptions: ProviderOption[];
  loading: boolean;
  onBack: () => void;
  onStart: (payload: {
    sessionType: SessionType;
    founderType: FounderType;
    sector: Sector;
    stage: Stage;
    mode: Mode;
    provider: Provider;
    model: string;
    apiKey: string;
    questionBudget: 10 | 15 | 20;
    websiteUrl: string;
    setupContext: string;
  }) => Promise<void>;
};

type RuntimeKind = "local" | "external";

const founderOptions: Array<{ value: FounderType; label: string }> = [
  { value: "student", label: "Student innovator" },
  { value: "professional", label: "Working professional" },
  { value: "founder", label: "First-time founder" },
  { value: "serial", label: "Repeat founder" },
];

const sectorOptions: Array<{ value: Sector; label: string }> = [
  { value: "saas", label: "Software / SaaS" },
  { value: "d2c", label: "Consumer / D2C" },
  { value: "fintech", label: "Fintech" },
  { value: "marketplace", label: "Marketplace" },
  { value: "edtech", label: "Education" },
  { value: "healthtech", label: "Health" },
  { value: "deeptech", label: "Deep tech / AI" },
  { value: "unknown", label: "Other" },
];

const stageOptions: Array<{ value: Stage; label: string }> = [
  { value: "idea", label: "Exploring" },
  { value: "pre-revenue", label: "Testing or building" },
  { value: "early-revenue", label: "Early proof" },
  { value: "growth", label: "Growing" },
];

const modeOptions: Array<{ value: Mode; label: string; note: string }> = [
  { value: "think_it_through", label: "Guided build", note: "Calmer coaching with more teaching." },
  { value: "quick_stress_test", label: "Pressure test", note: "Sharper follow-ups and less cushioning." },
];

const workflowOptions: Array<{ value: SessionType; label: string; note: string }> = [
  { value: "mentor", label: "Mentor", note: "Open-ended refinement, back and forth." },
  { value: "evaluator", label: "Evaluator", note: "Adaptive interview, final score and report at the end." },
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
  return "Mentor stays open-ended. Evaluator stays conversational and gives the score only at the end.";
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

export function SetupWizard({ providerOptions, loading, onBack, onStart }: Props) {
  const [step, setStep] = useState(0);
  const [runtimeKind, setRuntimeKind] = useState<RuntimeKind>("local");
  const [provider, setProvider] = useState<Provider>("ollama");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [founderType, setFounderType] = useState<FounderType>("founder");
  const [sector, setSector] = useState<Sector>("saas");
  const [stage, setStage] = useState<Stage>("idea");
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [setupContext, setSetupContext] = useState("");
  const [sessionType, setSessionType] = useState<SessionType>("mentor");
  const [mode, setMode] = useState<Mode>("think_it_through");
  const [questionBudget, setQuestionBudget] = useState<10 | 15 | 20>(15);

  const filteredProviders = useMemo(
    () => (runtimeKind === "local" ? providerOptions.filter((item) => item.key === "ollama") : providerOptions.filter((item) => item.key !== "ollama")),
    [providerOptions, runtimeKind],
  );
  const providerMeta = useMemo(() => {
    const fallback = runtimeKind === "local"
      ? providerOptions.find((item) => item.key === "ollama")
      : filteredProviders[0];
    return providerOptions.find((item) => item.key === provider) ?? fallback ?? providerOptions[0];
  }, [filteredProviders, provider, providerOptions, runtimeKind]);

  const resolvedProvider = runtimeKind === "local" ? "ollama" : (providerMeta?.key ?? "cerebras");
  const resolvedModel = model.trim()
    || (runtimeKind === "local"
      ? providerMeta?.defaultSpeedModel
      : providerMeta?.defaultBalancedModel || providerMeta?.defaultSpeedModel)
    || "";
  const canAdvanceRuntime = Boolean(resolvedModel) && (runtimeKind === "local" || apiKey.trim());

  return (
    <section className="onboarding-shell">
      <div className="onboarding-card clean-wizard-card">
        <div className="onboarding-meta">
          <span className="eyebrow">Setup</span>
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
                className={runtimeKind === "local" ? "choice-card active" : "choice-card"}
                onClick={() => {
                  setRuntimeKind("local");
                  setProvider("ollama");
                  const ollama = providerOptions.find((item) => item.key === "ollama");
                  setModel(ollama?.defaultSpeedModel || "");
                  setApiKey("");
                }}
              >
                <span>Local open source</span>
                <small>Runs through Ollama on this machine.</small>
              </button>
              <button
                type="button"
                className={runtimeKind === "external" ? "choice-card active" : "choice-card"}
                onClick={() => {
                  setRuntimeKind("external");
                  const firstExternal = providerOptions.find((item) => item.key !== "ollama");
                  setProvider(firstExternal?.key ?? "cerebras");
                  setModel(firstExternal?.defaultBalancedModel || firstExternal?.defaultSpeedModel || "");
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
                      setProvider(option.key);
                      setModel(runtimeKind === "local"
                        ? option.defaultSpeedModel
                        : option.defaultBalancedModel || option.defaultSpeedModel);
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
                    onChange={(event) => setModel(event.target.value)}
                    placeholder={resolvedProvider === "cerebras" ? "Example: gpt-oss-120b" : "Type the model id"}
                  />
                </label>
                {runtimeKind === "external" ? (
                  <label className="identity-field">
                    <span className="rail-label">API key</span>
                    <input
                      type="password"
                      value={apiKey}
                      onChange={(event) => setApiKey(event.target.value)}
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
                    className={founderType === option.value ? "chip-card active" : "chip-card"}
                    onClick={() => setFounderType(option.value)}
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
                    className={sector === option.value ? "chip-card active" : "chip-card"}
                    onClick={() => setSector(option.value)}
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
                    className={stage === option.value ? "chip-card active" : "chip-card"}
                    onClick={() => setStage(option.value)}
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
                  <input value={websiteUrl} onChange={(event) => setWebsiteUrl(event.target.value)} placeholder="https://yourproduct.com" />
                </label>
                <label className="identity-field field-span">
                  <span className="rail-label">What should the first reply know?</span>
                  <textarea
                    value={setupContext}
                    onChange={(event) => setSetupContext(event.target.value)}
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
                  className={sessionType === option.value ? "choice-card active" : "choice-card"}
                  onClick={() => setSessionType(option.value)}
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
                    className={mode === option.value ? "choice-card active" : "choice-card"}
                    onClick={() => setMode(option.value)}
                  >
                    <span>{option.label}</span>
                    <small>{option.note}</small>
                  </button>
                ))}
              </div>
            </div>

            {sessionType === "evaluator" ? (
              <div className="drawer-card">
                <span className="rail-label">Assessment depth</span>
                <div className="workflow-row" onKeyDown={handleArrowSelection}>
                  {budgetOptions.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      className={questionBudget === option.value ? "choice-card active" : "choice-card"}
                      onClick={() => setQuestionBudget(option.value)}
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
              setStep((current) => current - 1);
            }}
          >
            Back
          </button>

          {step < 2 ? (
            <button
              type="button"
              className="solid-button"
              onClick={() => setStep((current) => current + 1)}
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
                  sessionType,
                  founderType,
                  sector,
                  stage,
                  mode,
                  provider: resolvedProvider as Provider,
                  model: resolvedModel,
                  apiKey: runtimeKind === "external" ? apiKey.trim() : "",
                  questionBudget,
                  websiteUrl,
                  setupContext,
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
