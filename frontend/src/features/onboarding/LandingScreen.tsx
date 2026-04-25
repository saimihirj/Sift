import { useEffect, useRef, useState } from "react";

import type { AuthProviderOption, AuthUser, ThemeMode } from "../../app/types";
import { authLoginUrl } from "../../lib/api/client";

type Props = {
  displayName: string;
  onDisplayNameChange: (value: string) => void;
  onContinue: () => void;
  theme: ThemeMode;
  onThemeChange: (theme: ThemeMode) => void;
  authUser: AuthUser | null;
  authProviders: AuthProviderOption[];
  authError: string;
  onSignOut: () => Promise<void>;
};

// ─── SVG Brand Mark ───────────────────────────────────────────────────────────

function BrandMark() {
  return (
    <svg
      className="brand-mark"
      viewBox="0 0 32 22"
      fill="none"
      aria-hidden="true"
    >
      <rect x="0" y="15" width="4" height="7" rx="2" fill="currentColor" opacity="0.22" />
      <rect x="6" y="9" width="4" height="13" rx="2" fill="currentColor" opacity="0.58" />
      <rect x="12" y="2" width="4" height="20" rx="2" fill="currentColor" />
      <path d="M20.5 5.5 L29 14 M29 5.5 L20.5 14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

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
  "Ideate, Evaluate, Expert",
  "Pitch drafts exportable",
  "Live web when it helps",
  "Local or hosted models",
  "Deck reviews supported",
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function providerState(key: "google" | "apple", providers: AuthProviderOption[]) {
  return providers.find((item) => item.key === key) ?? { key, label: key, configured: false };
}

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

function GoogleMark() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="auth-mark">
      <path fill="#4285F4" d="M21.6 12.23c0-.7-.06-1.37-.18-2.02H12v3.82h5.39a4.62 4.62 0 0 1-2 3.03v2.52h3.24c1.9-1.75 2.97-4.33 2.97-7.35Z" />
      <path fill="#34A853" d="M12 22c2.7 0 4.96-.9 6.61-2.42l-3.24-2.52c-.9.6-2.04.96-3.37.96-2.59 0-4.78-1.75-5.56-4.1H3.09v2.6A9.99 9.99 0 0 0 12 22Z" />
      <path fill="#FBBC05" d="M6.44 13.92A5.98 5.98 0 0 1 6.13 12c0-.67.11-1.31.31-1.92V7.48H3.09A9.99 9.99 0 0 0 2 12c0 1.61.39 3.14 1.09 4.52l3.35-2.6Z" />
      <path fill="#EA4335" d="M12 5.98c1.47 0 2.79.5 3.83 1.48l2.87-2.87C16.95 2.97 14.69 2 12 2A9.99 9.99 0 0 0 3.09 7.48l3.35 2.6c.78-2.35 2.97-4.1 5.56-4.1Z" />
    </svg>
  );
}

function AppleMark() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="auth-mark">
      <path
        fill="currentColor"
        d="M15.1 3.5c.8-1 1.3-2.3 1.2-3.5-1.2.1-2.5.8-3.3 1.8-.7.8-1.3 2.1-1.2 3.3 1.3.1 2.5-.7 3.3-1.6Zm3.8 9.8c0-2.3 1.9-3.4 2-3.4-1.1-1.6-2.9-1.8-3.5-1.8-1.5-.2-2.9.9-3.7.9-.8 0-2-.9-3.4-.8-1.7 0-3.3 1-4.2 2.5-1.8 3.1-.5 7.7 1.3 10.2.9 1.2 1.9 2.5 3.3 2.4 1.3-.1 1.8-.8 3.4-.8s2.1.8 3.4.8c1.4 0 2.3-1.2 3.2-2.5 1-1.4 1.4-2.8 1.4-2.9-.1 0-3.2-1.2-3.2-4.6Z"
      />
    </svg>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

export function LandingScreen({
  displayName,
  onDisplayNameChange,
  onContinue,
  theme,
  onThemeChange,
  authUser,
  authProviders,
  authError,
  onSignOut,
}: Props) {
  const [hoveredMode, setHoveredMode] = useState<string | null>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);

  const google = providerState("google", authProviders);
  const apple = providerState("apple", authProviders);
  const canContinue = Boolean(displayName.trim() || authUser);
  const providerLabel = authUser?.provider === "google" ? "Google" : authUser?.provider === "apple" ? "Apple" : "";
  const authNote = authError || (authUser ? `${providerLabel} connected` : "");

  const handleModeClick = () => {
    if (!canContinue) {
      nameInputRef.current?.focus();
      return;
    }
    onContinue();
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
            <h2 className="entry-pro-title">
              {authUser ? authUser.displayName : "Start"}
            </h2>
          </div>

          {authUser ? (
            <div className="auth-summary-card">
              <div>
                <strong>{providerLabel} account</strong>
                <p>{authUser.email || authUser.displayName}</p>
              </div>
              <button type="button" className="ghost-button compact" onClick={() => void onSignOut()}>
                Sign out
              </button>
            </div>
          ) : null}

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
              placeholder={authUser?.displayName || "How should Sift address you?"}
              aria-required="true"
              autoComplete="given-name"
            />
          </label>

          <button
            type="button"
            className="solid-button pro-continue-btn"
            onClick={onContinue}
            disabled={!canContinue}
          >
            Continue
          </button>

          <div className="pro-auth-stack">
            <div className="pro-auth-separator">or sign in with</div>
            <div className="pro-auth-bubbles" aria-label="Sign in with">
              <a
                className={google.configured ? "auth-bubble" : "auth-bubble disabled-link"}
                href={google.configured ? authLoginUrl("google", "/") : undefined}
                aria-disabled={!google.configured}
                onClick={(event) => {
                  if (!google.configured) {
                    event.preventDefault();
                  }
                }}
              >
                <GoogleMark />
                <span>Google</span>
              </a>
              <a
                className={apple.configured ? "auth-bubble" : "auth-bubble disabled-link"}
                href={apple.configured ? authLoginUrl("apple", "/") : undefined}
                aria-disabled={!apple.configured}
                onClick={(event) => {
                  if (!apple.configured) {
                    event.preventDefault();
                  }
                }}
              >
                <AppleMark />
                <span>Apple</span>
              </a>
            </div>
          </div>

          {authNote ? <small className="muted-copy entry-auth-note">{authNote}</small> : null}
        </div>

      </section>
    </div>
  );
}
