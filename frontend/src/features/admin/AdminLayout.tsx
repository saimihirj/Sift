import { useState, useEffect } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import type { ThemeMode } from "../../app/types";
import { ThemePicker } from "../../app/ThemePicker";

const ADMIN_TOKEN_STORAGE_KEY = "sift-admin-token";

type Props = {
  theme: ThemeMode;
  onThemeChange: (theme: ThemeMode) => void;
};

export function AdminLayout({ theme, onThemeChange }: Props) {
  const [tokenInput, setTokenInput] = useState("");
  const [token, setToken] = useState(() => localStorage.getItem(ADMIN_TOKEN_STORAGE_KEY) ?? "");
  const [themeOpen, setThemeOpen] = useState(false);
  const location = useLocation();

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    localStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, tokenInput);
    setToken(tokenInput);
  };

  const handleLogout = () => {
    localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
    setToken("");
    setTokenInput("");
  };

  if (!token) {
    return (
      <div className="landing-pro-shell" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div className="floating-card is-open" style={{ maxWidth: "400px", width: "100%", padding: "2rem" }}>
          <div className="floating-head">
            <div>
              <span className="rail-label">Restricted Access</span>
              <strong>Admin Portal</strong>
            </div>
          </div>
          <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: "1rem", marginTop: "1.5rem" }}>
            <label className="identity-field">
              <span className="rail-label">Admin Token</span>
              <input
                type="password"
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                placeholder="Enter access token"
                autoFocus
              />
            </label>
            <button type="submit" className="solid-button">
              Authenticate
            </button>
          </form>
          <div style={{ marginTop: "1rem", textAlign: "center" }}>
             <Link to="/" style={{ color: "var(--text-muted)", fontSize: "0.85rem", textDecoration: "none" }}>&larr; Return to Sift</Link>
          </div>
        </div>
      </div>
    );
  }

  const currentTab = location.pathname.split("/").pop();

  return (
    <div className="outline-shell admin-shell">
      <aside className="left-rail outline-rail">
        <div className="workspace-title-stack">
          <span className="eyebrow">Workspace</span>
          <strong>Admin Portal</strong>
        </div>

        <nav className="rail-card admin-nav" style={{ display: "flex", flexDirection: "column", gap: "0.5rem", border: "none", background: "transparent", padding: 0 }}>
          <Link to="/admin/observability" className={`ghost-button admin-nav-item ${currentTab === "observability" ? "active" : ""}`}>
            Observability & Logs
          </Link>
          <Link to="/admin/neural" className={`ghost-button admin-nav-item ${currentTab === "neural" ? "active" : ""}`}>
            Neural Engine (SNE)
          </Link>
          <Link to="/admin/version-control" className={`ghost-button admin-nav-item ${currentTab === "version-control" ? "active" : ""}`}>
            Version Control
          </Link>
        </nav>

        <div className="rail-footer">
          <Link to="/" className="ghost-button">
            Back to app
          </Link>
          <button type="button" className="ghost-button" onClick={() => setThemeOpen(true)}>
            Themes
          </button>
          <button type="button" className="ghost-button" onClick={handleLogout}>
            Sign out
          </button>
        </div>
      </aside>

      <main className="outline-main admin-main" style={{ padding: "0" }}>
         {/* Pass the token down to child routes via Outlet context */}
         <Outlet context={{ adminToken: token }} />
      </main>

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
    </div>
  );
}
