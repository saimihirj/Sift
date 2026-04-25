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
  const hasAuthProvider = google.configured || apple.configured;
  const authNote = authError
    || (authUser
      ? `${providerLabel} connected`
      : "");

  return (
    <section className="landing-shell professional-entry-shell">
      <div className="landing-panel entry-frame">
        <section className="entry-brand-panel">
          <div className="landing-topbar">
            <h1 className="signal-wordmark">SignalX</h1>
            <button type="button" className="ghost-button compact theme-trigger" onClick={() => setThemeOpen(true)}>
              Theme
            </button>
          </div>

          <div className="entry-primary-actions" aria-label="SignalX workflows">
            <article className="entry-action-card">
              <strong>Ideate</strong>
              <span>Shape an idea</span>
            </article>
            <article className="entry-action-card">
              <strong>Evaluate</strong>
              <span>Get a report</span>
            </article>
            <article className="entry-action-card">
              <strong>Expert</strong>
              <span>Ask with evidence</span>
            </article>
          </div>
        </section>

        <section className="entry-access-panel">
          <div className="entry-access-head">
            <h2>{authUser ? authUser.displayName : "Start"}</h2>
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

          <button type="button" className="solid-button entry-continue" onClick={onContinue} disabled={!canContinue}>
            Continue
          </button>

          {hasAuthProvider ? (
            <div className="entry-auth-links" aria-label="Account sign in">
              {google.configured ? (
                <a className="text-link" href={authLoginUrl("google", "/")}>
                  Google
                </a>
              ) : null}
              {apple.configured ? (
                <a className="text-link" href={authLoginUrl("apple", "/")}>
                  Apple
                </a>
              ) : null}
            </div>
          ) : null}

          {authNote ? <small className="muted-copy entry-auth-note">{authNote}</small> : null}
        </section>
      </div>

      <div className={themeOpen ? "floating-panel is-open align-right" : "floating-panel align-right"} aria-hidden={!themeOpen}>
        <button type="button" className={themeOpen ? "floating-backdrop is-open" : "floating-backdrop"} onClick={() => setThemeOpen(false)} aria-label="Close themes" />
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
    </section>
  );
}
