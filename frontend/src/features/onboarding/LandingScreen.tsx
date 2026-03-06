import type { AuthProviderOption, AuthUser, ThemeMode } from "../../app/types";
import { SignalLockup } from "../../app/SignalBrand";
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
  const google = providerState("google", authProviders);
  const apple = providerState("apple", authProviders);
  const canContinue = Boolean(displayName.trim() || authUser);
  const authNote = authError
    || (authUser
      ? `Signed in with ${authUser.provider}.`
      : "Use your name or sign in. OAuth buttons activate only when credentials are configured.");

  return (
    <section className="landing-shell minimal-entry-shell">
      <div className="landing-panel minimal-entry-panel">
        <div className="landing-topbar">
          <SignalLockup compact showTagline={false} />
          <ThemePicker theme={theme} onChange={onThemeChange} />
        </div>

        <div className="signal-brand-card">
          <SignalLockup className="signal-brand-hero" />
        </div>

        <div className="landing-hero">
          <h1>Hi.</h1>
          <p>Sign in or enter your name. Then choose your runtime, context, and flow.</p>
        </div>

        {authUser ? (
          <div className="auth-summary-card">
            <div>
              <strong>Signed in</strong>
              <p>{authUser.provider === "google" ? "Google account connected" : "Apple account connected"}</p>
            </div>
            <button type="button" className="ghost-button compact" onClick={() => void onSignOut()}>
              Sign out
            </button>
          </div>
        ) : null}

        <label className="identity-field">
          <span className="rail-label">Name</span>
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
            placeholder="Your name"
            aria-required="true"
          />
        </label>

        <div className="social-row">
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

        <small className="muted-copy">{authNote}</small>

        <button type="button" className="solid-button" onClick={onContinue} disabled={!canContinue}>
          Continue
        </button>
      </div>
    </section>
  );
}
