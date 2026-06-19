import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import type { ThemeMode } from "../../app/types";

type Props = {
  emailOrHandle: string;
  onEmailOrHandleChange: (value: string) => void;
  onContinue: () => void | Promise<void>;
  theme: ThemeMode;
  onThemeChange: (theme: ThemeMode) => void;
  error: string;
  authProviders?: Array<{ key: string; label: string; configured: boolean }>;
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

// ─── Component ────────────────────────────────────────────────────────────────

export function LandingScreen({
  emailOrHandle,
  onEmailOrHandleChange,
  onContinue,
  theme,
  onThemeChange,
  error,
  authProviders = [],
}: Props) {
  const [hoveredMode, setHoveredMode] = useState<string | null>(null);
  const emailInputRef = useRef<HTMLInputElement>(null);

  const canContinue = Boolean(emailOrHandle.trim().length >= 3);

  const handleModeClick = () => {
    if (!canContinue) {
      emailInputRef.current?.focus();
      return;
    }
    onContinue();
  };

  return (
    <div className="landing-pro-shell">

      {/* ── Left: brand + conviction ──────────────────────────────────── */}
      <section className="landing-pro-left" aria-label="Sift — intelligence layer for startups">
        <header className="landing-pro-brand">
          <div className="brand-identity">
            <span className="brand-wordmark">
              SIFT<span className="brand-wordmark-dot">.</span>
            </span>
          </div>
        </header>

        {/* Mode cards — functional, not decorative */}
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

          {authProviders.filter((p) => p.configured).length > 0 && (
            <div className="identity-oauth-providers" style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginBottom: "1.5rem" }}>
              {authProviders.filter((p) => p.configured).map((provider) => (
                <a
                  key={provider.key}
                  href={`/api/auth/login/${provider.key}`}
                  className="solid-button pro-continue-btn"
                  style={{ textDecoration: "none", textAlign: "center", background: "var(--layer-surface-hover)", color: "var(--text-primary)" }}
                >
                  Sign in with {provider.label}
                </a>
              ))}
              <div style={{ textAlign: "center", margin: "0.5rem 0", color: "var(--text-muted)", fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Or use local identity
              </div>
            </div>
          )}

          <label className="identity-field">
            <span className="rail-label">Enter your email</span>
            <input
              ref={emailInputRef}
              type="email"
              value={emailOrHandle}
              onChange={(event) => onEmailOrHandleChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && canContinue) {
                  event.preventDefault();
                  onContinue();
                }
              }}
              placeholder="Used to sync your workspace"
              aria-required="true"
              autoComplete="email"
            />
          </label>
          {error ? <div className="setup-alert" role="alert">{error}</div> : null}

          <button
            type="button"
            className="solid-button pro-continue-btn"
            onClick={onContinue}
            disabled={!canContinue}
          >
            Continue
          </button>

        </div>

      </section>
    </div>
  );
}
