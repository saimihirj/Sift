import { useEffect, useMemo, useRef, useState } from "react";

import type { FounderType, Mode, Sector, SessionSummary, Stage } from "../../app/types";

type Props = {
  onStart: (payload: {
    founderType: FounderType;
    sector: Sector;
    stage: Stage;
    mode: Mode;
    displayName: string;
  }) => Promise<void>;
  onBackToLanding: () => void;
  recentSessions: SessionSummary[];
  onResume: (sessionId: string) => Promise<void>;
  displayName: string;
  loading: boolean;
};

const founderOptions: Array<{ value: FounderType; label: string; note: string }> = [
  { value: "student", label: "Student innovator", note: "Simpler language, more guidance, less jargon." },
  { value: "professional", label: "Working professional", note: "Ground it in real workflows, buyers, and proof." },
  { value: "founder", label: "First-time founder", note: "Balanced challenge across problem, proof, and story." },
  { value: "serial", label: "Repeat founder", note: "Skip basics and challenge assumptions faster." },
];

const sectorOptions: Array<{ value: Sector; label: string; note: string }> = [
  { value: "saas", label: "Software / SaaS", note: "Tools, workflows, B2B software." },
  { value: "d2c", label: "Consumer / D2C", note: "Brands, apps, or consumer behavior." },
  { value: "fintech", label: "Fintech", note: "Payments, lending, insurance, or money tools." },
  { value: "marketplace", label: "Marketplace", note: "Supply, demand, and transaction flow." },
  { value: "edtech", label: "Education", note: "Learning, teaching, or student outcomes." },
  { value: "healthtech", label: "Health", note: "Care delivery, health access, or patient flow." },
  { value: "deeptech", label: "Deep tech / AI", note: "Model-heavy, technical, or research-led ideas." },
  { value: "unknown", label: "Other", note: "Use a general mentor lens first." },
];

const stageOptions: Array<{ value: Stage; label: string; note: string }> = [
  { value: "idea", label: "Exploring the problem", note: "Still shaping the user, pain, and insight." },
  { value: "pre-revenue", label: "Testing or building", note: "Prototype, interviews, or early experiments." },
  { value: "early-revenue", label: "Early proof", note: "Some users, pilots, or early revenue." },
  { value: "growth", label: "Growing", note: "Clearer proof, stronger story, bigger decisions." },
];

const modeOptions: Array<{ value: Mode; label: string; note: string }> = [
  { value: "think_it_through", label: "Guided build", note: "Calm, structured, one gap at a time." },
  { value: "quick_stress_test", label: "Tight review", note: "More direct, faster pressure-testing." },
];

function getStarterPreview(founderType: FounderType, stage: Stage) {
  if (founderType === "student") {
    return [
      "Can you help simplify my idea?",
      "The user pain is...",
      "I am unsure who needs this most",
    ];
  }
  if (founderType === "professional") {
    return [
      "The problem in my industry is...",
      "Current teams handle it by...",
      "I need help pressure-testing this",
    ];
  }
  if (founderType === "serial") {
    return [
      "The wedge this time is...",
      "The market changed because...",
      "The real risk is...",
    ];
  }
  if (stage === "pre-revenue") {
    return [
      "We tested this by...",
      "Users care because...",
      "We may charge for...",
    ];
  }
  if (stage === "early-revenue") {
    return [
      "Our strongest signal is...",
      "Customers stay because...",
      "The next proof point is...",
    ];
  }
  if (stage === "growth") {
    return [
      "Our strongest proof is...",
      "Growth is driven by...",
      "We are raising to...",
    ];
  }
  return [
    "The user pain is...",
    "They solve it today by...",
    "Why now matters because...",
  ];
}

export function OnboardingCard({
  onStart,
  onBackToLanding,
  recentSessions,
  onResume,
  displayName,
  loading,
}: Props) {
  const shellRef = useRef<HTMLElement | null>(null);
  const [step, setStep] = useState(0);
  const [founderType, setFounderType] = useState<FounderType>("founder");
  const [sector, setSector] = useState<Sector>("saas");
  const [stage, setStage] = useState<Stage>("idea");
  const [mode, setMode] = useState<Mode>("think_it_through");
  const starterPreview = useMemo(() => getStarterPreview(founderType, stage), [founderType, stage]);

  useEffect(() => {
    if (!shellRef.current) {
      return;
    }
    const active = document.activeElement;
    if (active instanceof HTMLElement && (active.tagName === "INPUT" || active.tagName === "TEXTAREA")) {
      return;
    }
    shellRef.current.focus();
  }, [step]);

  const title = useMemo(() => {
    if (step === 0) return "What best describes you right now?";
    if (step === 1) return "What space are you working in?";
    if (step === 2) return "How far along are you?";
    return "What kind of session do you want?";
  }, [step]);

  const subtitle = useMemo(() => {
    if (step === 0) return "This helps VK choose the right tone and depth.";
    if (step === 1) return "This shapes which assumptions get challenged first.";
    if (step === 2) return "This sets how much proof the mentor should expect.";
    return "You can switch this later from the left rail.";
  }, [step]);

  const moveStepSelection = (delta: number) => {
    if (step === 0) {
      const index = founderOptions.findIndex((option) => option.value === founderType);
      const next = founderOptions[Math.max(0, Math.min(founderOptions.length - 1, index + delta))];
      setFounderType(next.value);
      return;
    }
    if (step === 1) {
      const index = sectorOptions.findIndex((option) => option.value === sector);
      const next = sectorOptions[Math.max(0, Math.min(sectorOptions.length - 1, index + delta))];
      setSector(next.value);
      return;
    }
    if (step === 2) {
      const index = stageOptions.findIndex((option) => option.value === stage);
      const next = stageOptions[Math.max(0, Math.min(stageOptions.length - 1, index + delta))];
      setStage(next.value);
      return;
    }
    const index = modeOptions.findIndex((option) => option.value === mode);
    const next = modeOptions[Math.max(0, Math.min(modeOptions.length - 1, index + delta))];
    setMode(next.value);
  };

  const handleKeyDown: React.KeyboardEventHandler<HTMLElement> = (event) => {
    const target = event.target as HTMLElement;
    if (target.tagName === "INPUT" || target.tagName === "TEXTAREA") {
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      moveStepSelection(step === 1 ? 2 : 1);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      moveStepSelection(step === 1 ? -2 : -1);
      return;
    }
    if (event.key === "ArrowRight") {
      event.preventDefault();
      if (step === 1) {
        moveStepSelection(1);
      } else {
        setStep((current) => Math.min(3, current + 1));
      }
      return;
    }
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      if (step === 1) {
        moveStepSelection(-1);
      } else if (step === 0) {
        onBackToLanding();
      } else {
        setStep((current) => Math.max(0, current - 1));
      }
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      if (step < 3) {
        setStep((current) => current + 1);
        return;
      }
      if (!loading) {
        void onStart({ founderType, sector, stage, mode, displayName });
      }
    }
  };

  return (
    <section
      ref={shellRef}
      className="onboarding-shell"
      onKeyDown={handleKeyDown}
      tabIndex={0}
      aria-label="Vishwakarma onboarding"
    >
      <div className="onboarding-card">
        <div className="onboarding-meta">
          <span className="eyebrow">Vishwakarma · VK</span>
          <div className="step-dots" aria-hidden="true">
            {[0, 1, 2, 3].map((value) => (
              <span key={value} className={value === step ? "dot active" : "dot"} />
            ))}
          </div>
        </div>

        <div className="onboarding-copy">
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>

        <div className="interaction-hint">
          <span className="rail-label">Keys</span>
          <small>Arrow keys move. Enter continues.</small>
        </div>

        {step === 0 && (
          <div className="choice-grid single-column">
            {founderOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                className={founderType === option.value ? "choice-card active" : "choice-card"}
                onClick={() => setFounderType(option.value)}
              >
                <span>{option.label}</span>
                <small>{option.note}</small>
              </button>
            ))}
          </div>
        )}

        {step === 1 && (
          <div className="chip-grid">
            {sectorOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                className={sector === option.value ? "chip-card active" : "chip-card"}
                onClick={() => setSector(option.value)}
              >
                <span>{option.label}</span>
                <small>{option.note}</small>
              </button>
            ))}
          </div>
        )}

        {step === 2 && (
          <div className="choice-grid single-column">
            {stageOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                className={stage === option.value ? "choice-card active" : "choice-card"}
                onClick={() => setStage(option.value)}
              >
                <span>{option.label}</span>
                <small>{option.note}</small>
              </button>
            ))}
          </div>
        )}

        {step === 3 && (
          <div className="choice-grid single-column">
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
        )}

        <div className="starter-preview">
          <div className="resume-head">
            <span className="rail-label">Starter prompts</span>
            <small>These show up when the session opens</small>
          </div>
          <div className="starter-chip-row">
            {starterPreview.map((chip) => (
              <div key={chip} className="starter-chip">
                {chip}
              </div>
            ))}
          </div>
        </div>

        <div className="onboarding-actions">
          <button
            type="button"
            className="ghost-button"
            onClick={() => {
              if (step === 0) {
                onBackToLanding();
                return;
              }
              setStep((current) => Math.max(0, current - 1));
            }}
            disabled={loading}
          >
            Back
          </button>
          {step < 3 ? (
            <button type="button" className="solid-button" onClick={() => setStep((current) => current + 1)}>
              Continue
            </button>
          ) : (
            <button
              type="button"
              className="solid-button"
              onClick={() => onStart({ founderType, sector, stage, mode, displayName: displayName.trim() })}
              disabled={loading}
            >
              {loading ? "Starting..." : "Open Mentor"}
            </button>
          )}
        </div>

        {recentSessions.length > 0 && (
          <div className="resume-panel">
            <div className="resume-head">
              <span className="rail-label">Recent sessions</span>
              <small>Pick up where you left off</small>
            </div>
            <div className="resume-list">
              {recentSessions.slice(0, 4).map((session) => (
                <button
                  key={session.sessionId}
                  type="button"
                  className="resume-card"
                  onClick={() => void onResume(session.sessionId)}
                >
                  <strong>{session.title}</strong>
                  <span>{session.subtitle}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
