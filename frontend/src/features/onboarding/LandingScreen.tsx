import { useState } from "react";

import type { AuthProviderOption, AuthUser, ThemeMode } from "../../app/types";
import { ThemePicker } from "../../app/ThemePicker";
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

function providerState(key: "google" | "apple", providers: AuthProviderOption[]) {
  return providers.find((item) => item.key === key) ?? { key, label: key, configured: false };
}

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
  const [themeOpen, setThemeOpen] = useState(false);
  const google = providerState("google", authProviders);
  const apple = providerState("apple", authProviders);
  const canContinue = Boolean(displayName.trim() || authUser);
  const providerLabel = authUser?.provider === "google" ? "Google" : authUser?.provider === "apple" ? "Apple" : "";
  const authNote = authError
    || (authUser
      ? `Connected with ${providerLabel}. You can still change the display name below.`
      : "Use a local profile or connect an account. Runtime and provider come next.");

  return (
    <section className="landing-shell professional-entry-shell">
      <div className="landing-panel entry-frame">
        <section className="entry-brand-panel">
          <div className="landing-topbar">
            <div className="plain-header-block">
              <span className="eyebrow">SignalX</span>
              <strong>Startup and finance workbench</strong>
            </div>
            <button type="button" className="ghost-button compact" onClick={() => setThemeOpen(true)}>
              Themes
            </button>
          </div>

          <div className="entry-hero-copy">
            <h1>Research, evaluate, decide.</h1>
            <p>One workspace for idea shaping, structured evaluation, and expert analysis. Built for local models or API-key runtimes.</p>
          </div>

          <div className="entry-feature-grid">
            <article className="entry-feature-card">
              <span className="eyebrow">Workflows</span>
              <strong>Ideate, Evaluate, Expert</strong>
              <p>Move from rough thinking to pressure tests and source-backed domain analysis without switching tools.</p>
            </article>
            <article className="entry-feature-card">
              <span className="eyebrow">Runtime</span>
              <strong>Open source or API</strong>
              <p>Use Ollama locally, or connect providers like Groq, Cerebras, OpenAI, OpenRouter, Anthropic, and Gemini.</p>
            </article>
            <article className="entry-feature-card">
              <span className="eyebrow">Evidence</span>
              <strong>Local corpus first, web when needed</strong>
              <p>SignalX uses the bundled knowledge base and can pull fresher web context when the local evidence is thin.</p>
            </article>
          </div>

          <div className="entry-runtime-row">
            <span className="landing-badge">Local models</span>
            <span className="landing-badge">API keys</span>
            <span className="landing-badge">Source-backed answers</span>
          </div>
        </section>

        <section className="entry-access-panel">
          <div className="entry-access-head">
            <span className="eyebrow">Open workspace</span>
            <h2>{authUser ? `Continue as ${authUser.displayName}` : "Access your workspace"}</h2>
            <p>Start with a local profile or sign in. You will choose the workflow and runtime in the next step.</p>
          </div>

          {authUser ? (
            <div className="auth-summary-card">
              <div>
                <strong>{providerLabel} account connected</strong>
                <p>{authUser.email || authUser.displayName}</p>
              </div>
              <button type="button" className="ghost-button compact" onClick={() => void onSignOut()}>
                Sign out
              </button>
            </div>
          ) : null}

          <label className="identity-field">
            <span className="rail-label">Display name</span>
            <input
              type="text"
              value={displayName}
              onChange={(event) => onDisplayNameChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && canContinue) {
                  event.preventDefault();
                  onContinue();
                }
              }}
              placeholder={authUser?.displayName || "How should SignalX address you?"}
              aria-required="true"
            />
          </label>

          <div className="social-row entry-social-row">
            <a
              className={google.configured ? "ghost-button social-button" : "ghost-button social-button disabled-link"}
              href={google.configured ? authLoginUrl("google", "/") : undefined}
              aria-disabled={!google.configured}
              onClick={(event) => {
                if (!google.configured) {
                  event.preventDefault();
                }
              }}
            >
              Continue with Google
            </a>
            <a
              className={apple.configured ? "ghost-button social-button" : "ghost-button social-button disabled-link"}
              href={apple.configured ? authLoginUrl("apple", "/") : undefined}
              aria-disabled={!apple.configured}
              onClick={(event) => {
                if (!apple.configured) {
                  event.preventDefault();
                }
              }}
            >
              Continue with Apple
            </a>
          </div>

          <small className="muted-copy entry-auth-note">{authNote}</small>

          <button type="button" className="solid-button entry-continue" onClick={onContinue} disabled={!canContinue}>
            Continue to setup
          </button>
        </section>
      </div>

      <div className={themeOpen ? "floating-panel is-open align-right" : "floating-panel align-right"} aria-hidden={!themeOpen}>
        <button type="button" className={themeOpen ? "floating-backdrop is-open" : "floating-backdrop"} onClick={() => setThemeOpen(false)} aria-label="Close themes" />
        <aside className={themeOpen ? "floating-card is-open theme-card" : "floating-card theme-card"}>
          <div className="floating-head">
            <div>
              <span className="rail-label">Themes</span>
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
    </section>
  );
}
