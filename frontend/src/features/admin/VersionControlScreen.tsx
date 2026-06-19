export function VersionControlScreen() {
  return (
    <div style={{ padding: "2rem", height: "100%", display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div className="admin-card-head" style={{ marginBottom: "1rem" }}>
        <strong style={{ fontSize: "1.2rem" }}>Version Control Dashboard</strong>
        <span className="rail-label">Git integration & rollback</span>
      </div>
      <div className="outline-card admin-card" style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ textAlign: "center", color: "var(--text-muted)" }}>
          <p style={{ marginBottom: "1rem" }}>This module is currently under development.</p>
          <span className="ghost-button compact">Coming soon</span>
        </div>
      </div>
    </div>
  );
}
