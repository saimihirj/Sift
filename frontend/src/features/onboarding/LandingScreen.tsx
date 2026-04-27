import { useEffect, useRef, useState } from "react";

import type { ThemeMode } from "../../app/types";

type Props = {
  displayName: string;
  emailOrHandle: string;
  accessKey: string;
  onDisplayNameChange: (value: string) => void;
  onEmailOrHandleChange: (value: string) => void;
  onAccessKeyChange: (value: string) => void;
  onGenerateAccessKey: () => void;
  onContinue: () => void;
  theme: ThemeMode;
  onThemeChange: (theme: ThemeMode) => void;
  error: string;
};

// ─── Mode Glyphs ──────────────────────────────────────────────────────────────

function IdeateGlyph() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="10" cy="3.5" r="2.2" />
      <path d="M10 5.7 L10 10.5" />
      <path d="M10 10.5 L5 16" />
      <path d="M10 10.5 L15 16" />
      <circle cx="5" cy="17" r="1.6" />
      <circle cx="15" cy="17" r="1.6" />
    </svg>
  );
}

function EvaluateGlyph() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="1.5" y="13.5" width="3.5" height="5" rx="0.9" />
      <rect x="8" y="8.5" width="3.5" height="10" rx="0.9" />
      <rect x="14.5" y="3.5" width="3.5" height="15" rx="0.9" />
      <path d="M0.5 7.5 L3 10.5 L7.5 4.5" />
    </svg>
  );
}

function ExpertGlyph() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="8.5" cy="8.5" r="5.5" />
      <path d="M13 13 L18.5 18.5" />
      <circle cx="5" cy="6" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="12" cy="5.5" r="1.1" fill="currentColor" stroke="none" />
      <path d="M5 6 L12 5.5" strokeDasharray="1.8 1.8" />
    </svg>
  );
}

// ─── Static Data ──────────────────────────────────────────────────────────────

const THEME_SWATCHES: Array<{ key: ThemeMode; bg: string; label: string }> = [
  { key: "light",  bg: "#164e63", label: "Light" },
  { key: "dark",   bg: "#8bd3dd", label: "Graphite" },
  { key: "dusk",   bg: "#d9b56f", label: "Dusk" },
  { key: "neon",   bg: "#e2e2e2", label: "Focus" },
];

const MODE_CARDS = [
  { idx: "01", key: "ideate",   label: "Ideate",   hint: "Pitch draft",    Glyph: IdeateGlyph },
  { idx: "02", key: "evaluate", label: "Evaluate", hint: "Score + report", Glyph: EvaluateGlyph },
  { idx: "03", key: "expert",   label: "Expert",   hint: "Sourced answer", Glyph: ExpertGlyph },
] as const;

const TICKER_MESSAGES = [
  "Private beta build",
  "Ideate, Evaluate, Expert",
  "Pitch drafts exportable",
  "Live web when it helps",
  "Local or hosted models",
  "Deck reviews supported",
];

function TickerText() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setIndex((current) => (current + 1) % TICKER_MESSAGES.length);
    }, 6000);
    return () => window.clearInterval(timer);
  }, []);

  return <span key={index} className="landing-pro-ticker-text">{TICKER_MESSAGES[index]}</span>;
}

// ─── Component ────────────────────────────────────────────────────────────────

export function LandingScreen({
  displayName,
  emailOrHandle,
  accessKey,
  onDisplayNameChange,
  onEmailOrHandleChange,
  onAccessKeyChange,
  onGenerateAccessKey,
  onContinue,
  theme,
  onThemeChange,
  error,
}: Props) {
  const [hoveredMode, setHoveredMode] = useState<string | null>(null);
  const [feedbackCopied, setFeedbackCopied] = useState(false);
  const [keyCopied, setKeyCopied] = useState(false);
  const nameInputRef = useRef<HTMLInputElement>(null);

  const canContinue = Boolean(displayName.trim() && emailOrHandle.trim() && accessKey.trim().length >= 8);

  const handleModeClick = () => {
    if (!canContinue) {
      nameInputRef.current?.focus();
      return;
    }
    onContinue();
  };

  const copyFeedbackPrompt = async () => {
    const note = "Sift beta feedback:\n\nWhat I tried:\nWhat worked:\nWhere I got stuck:\nWhat I expected instead:";
    try {
      await navigator.clipboard.writeText(note);
      setFeedbackCopied(true);
      window.setTimeout(() => setFeedbackCopied(false), 1800);
    } catch {
      setFeedbackCopied(false);
    }
  };

  const copyAccessKey = async () => {
    if (!accessKey.trim()) {
      return;
    }
    try {
      await navigator.clipboard.writeText(accessKey.trim());
      setKeyCopied(true);
      window.setTimeout(() => setKeyCopied(false), 1800);
    } catch {
      setKeyCopied(false);
    }
  };

  return (
    <div className="landing-pro-shell">

      {/* ── Left: brand + mode showcase ─────────────────────────────────── */}
      <section className="landing-pro-left" aria-label="Sift modes">
        <header className="landing-pro-brand">
          <div className="brand-identity">
            <span className="brand-wordmark">
              SIFT<span className="brand-wordmark-dot">.</span>
            </span>
          </div>
        </header>

        <nav className="landing-pro-modes" aria-label="Choose a workflow">
          {MODE_CARDS.map((mode, index) => (
            <button
              key={mode.key}
              type="button"
              className={`mode-entry-card${hoveredMode === mode.key ? " hovered" : ""}`}
              style={{ "--card-i": index } as React.CSSProperties}
              onMouseEnter={() => setHoveredMode(mode.key)}
              onMouseLeave={() => setHoveredMode(null)}
              onClick={handleModeClick}
              aria-label={`${mode.label} — ${mode.hint}`}
            >
              <span className="mode-card-idx" aria-hidden="true">{mode.idx}</span>
              <span className="mode-card-glyph" aria-hidden="true">
                <mode.Glyph />
              </span>
              <span className="mode-card-label">{mode.label}</span>
              <span className="mode-card-hint" aria-hidden="true">{mode.hint}</span>
            </button>
          ))}
        </nav>

        <div className="landing-pro-ticker" aria-live="polite">
          <span className="landing-pro-ticker-dot" aria-hidden="true" />
          <TickerText />
        </div>
      </section>

      {/* ── Right: entry ─────────────────────────────────────────────────── */}
      <section className="landing-pro-right">

        {/* Theme dots */}
        <div className="theme-swatch-row" role="group" aria-label="Select theme">
          {THEME_SWATCHES.map((swatch) => (
            <button
              key={swatch.key}
              type="button"
              className={`theme-swatch${theme === swatch.key ? " active" : ""}`}
              style={{ "--sw-bg": swatch.bg } as React.CSSProperties}
              onClick={() => onThemeChange(swatch.key)}
              aria-label={swatch.label}
              aria-pressed={theme === swatch.key}
            />
          ))}
        </div>

        {/* Entry form */}
        <div className="landing-pro-entry">
          <div className="entry-pro-head">
            <p className="entry-pro-eyebrow">Workspace</p>
            <h2 className="entry-pro-title">Start</h2>
          </div>

          <label className="identity-field">
            <span className="rail-label">Your name</span>
            <input
              ref={nameInputRef}
              type="text"
              value={displayName}
              onChange={(event) => onDisplayNameChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && canContinue) {
                  event.preventDefault();
                  onContinue();
                }
              }}
              placeholder="How should Sift address you?"
              aria-required="true"
              autoComplete="given-name"
            />
          </label>

          <label className="identity-field">
            <span className="rail-label">Email or handle</span>
            <input
              type="text"
              value={emailOrHandle}
              onChange={(event) => onEmailOrHandleChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && canContinue) {
                  event.preventDefault();
                  onContinue();
                }
              }}
              placeholder="Used with your Sift key"
              aria-required="true"
              autoComplete="email"
            />
          </label>

          <label className="identity-field">
            <span className="rail-label">Sift key</span>
            <input
              type="text"
              value={accessKey}
              onChange={(event) => onAccessKeyChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && canContinue) {
                  event.preventDefault();
                  onContinue();
                }
              }}
              placeholder="Generate or enter your saved key"
              aria-required="true"
              autoComplete="off"
            />
          </label>

          <div className="identity-key-actions">
            <button type="button" className="ghost-button compact" onClick={onGenerateAccessKey}>
              Generate key
            </button>
            <button type="button" className="ghost-button compact" onClick={() => void copyAccessKey()} disabled={!accessKey.trim()}>
              {keyCopied ? "Key copied" : "Copy key"}
            </button>
          </div>

          <small className="muted-copy entry-auth-note">Use the same email or handle and Sift key to see your previous sessions.</small>
          {error ? <div className="setup-alert" role="alert">{error}</div> : null}

          <button
            type="button"
            className="solid-button pro-continue-btn"
            onClick={onContinue}
            disabled={!canContinue}
          >
            Continue
          </button>

          <button type="button" className="ghost-button compact beta-feedback-button" onClick={() => void copyFeedbackPrompt()}>
            {feedbackCopied ? "Feedback note copied" : "Copy beta feedback note"}
          </button>
        </div>

      </section>
    </div>
  );
}
