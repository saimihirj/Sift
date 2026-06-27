import { useEffect, useRef, useState } from "react";
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from "recharts";
import type { EvaluatorReport, Issue, SiftSession } from "../../app/sift.types";

interface ScorecardProps {
  session: SiftSession;
  report: EvaluatorReport;
  onFixIt: () => void;
  onStartOver: () => void;
}

const CIRCUMFERENCE = 2 * Math.PI * 52;

function ScoreRing({ score }: { score: number }) {
  const [animated, setAnimated] = useState(false);
  const clamped = Math.max(0, Math.min(100, score));
  const offset = animated ? CIRCUMFERENCE * (1 - clamped / 100) : CIRCUMFERENCE;

  useEffect(() => {
    const timer = setTimeout(() => setAnimated(true), 80);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="score-ring" aria-label={`Readiness score: ${clamped} out of 100`}>
      <svg width="120" height="120" viewBox="0 0 120 120" aria-hidden="true">
        <circle
          className="score-ring-track"
          cx="60"
          cy="60"
          r="52"
        />
        <circle
          className="score-ring-fill"
          cx="60"
          cy="60"
          r="52"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={offset}
          style={{ stroke: "var(--brand)" }}
        />
      </svg>
      <div className="score-number">
        <span className="score-value">{clamped}</span>
        <span className="score-total">/ 100</span>
      </div>
    </div>
  );
}

function VCRadarChart({ dimensions }: { dimensions: NonNullable<EvaluatorReport["dimensionScores"]> }) {
  const data = dimensions.map(d => {
    let score = 50;
    if (d.status === "strong") score = 95;
    if (d.status === "weak") score = 40;
    if (d.status === "missing") score = 10;
    
    // Abbreviate labels for the radar chart to fit nicely
    let label = d.label;
    if (label.includes("Product Fit")) label = "Team-Product";
    if (label.includes("Opportunity") || label.includes("TAM")) label = "Market";
    if (label.includes("Implementation") || label.includes("Traction")) label = "Execution";
    if (label.includes("Profit") || label.includes("Model")) label = "Economics";
    if (label.includes("Solutions") || label.includes("Competition")) label = "Moat";

    return {
      subject: label,
      A: score,
      fullMark: 100,
    };
  });

  // Ensure we have at least 3 points for a radar chart
  if (data.length < 3) return null;

  return (
    <div style={{ width: "100%", height: 260, marginTop: 16 }}>
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data}>
          <PolarGrid stroke="var(--border-strong)" />
          <PolarAngleAxis dataKey="subject" tick={{ fill: "var(--text-secondary)", fontSize: 11 }} />
          <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
          <Radar name="Startup" dataKey="A" stroke="var(--brand)" fill="var(--brand)" fillOpacity={0.4} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

function IssueRow({ issue, index }: { issue: Issue; index: number }) {
  const isCritical = issue.severity === "critical";
  return (
    <div className="issue-row" role="listitem">
      <div
        className={`issue-severity${isCritical ? " critical" : ""}`}
        aria-label={issue.severity}
      >
        <span className="issue-severity-dot" style={{ backgroundColor: isCritical ? "#ef4444" : "#f59e0b" }} />
      </div>
      <div className="issue-body">
        <span className="issue-title">{issue.title}</span>
        <span className="issue-explanation">{issue.explanation}</span>
        {issue.reference && (
          <span className="issue-ref">{issue.reference}</span>
        )}
      </div>
      <span
        className="badge"
        aria-label={`Issue ${index + 1}`}
        style={{ flexShrink: 0, alignSelf: "flex-start", background: "var(--surface-hover)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}
      >
        {String(index + 1).padStart(2, "0")}
      </span>
    </div>
  );
}

export function ScorecardScreen({ session, report, onFixIt, onStartOver }: ScorecardProps) {
  const fixRef = useRef<HTMLDivElement>(null);
  const criticalCount = report.issues.filter((i) => i.severity === "critical").length;
  const warningCount = report.issues.filter((i) => i.severity === "warning").length;

  return (
    <main className="page" style={{ background: "radial-gradient(ellipse at top, var(--surface) 0%, var(--bg) 100%)" }}>
      <div className="scorecard-page" style={{ animation: "fade-in-up 0.6s ease" }}>
        
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 24, marginBottom: 24 }}>
          {/* Main Score Section */}
          <section className="score-header" style={{ background: "rgba(24, 24, 27, 0.4)", backdropFilter: "blur(12px)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 32, display: "flex", flexDirection: "column", alignItems: "center" }} aria-label="Readiness overview">
            {report.sourceName && (
              <span className="score-source" style={{ marginBottom: 16 }}>{report.sourceName}</span>
            )}
            <div className="score-ring-wrapper">
              <ScoreRing score={report.readinessScore} />
              <span className="score-label" style={{ marginTop: 12 }}>Readiness Score</span>
            </div>
            {(criticalCount > 0 || warningCount > 0) && (
              <p style={{ fontSize: 13, color: "var(--text-muted)", textAlign: "center", marginTop: 16 }}>
                {criticalCount > 0 && <><span style={{ color: "#ef4444" }}>{criticalCount} critical</span>{criticalCount > 1 ? " issues" : " issue"}</>}
                {criticalCount > 0 && warningCount > 0 && " · "}
                {warningCount > 0 && <><span style={{ color: "#f59e0b" }}>{warningCount} warning</span>{warningCount > 1 ? "s" : ""}</>}
              </p>
            )}
          </section>

          {/* VC Lenses Radar Chart Section */}
          {report.dimensionScores && report.dimensionScores.length > 0 && (
            <section className="score-header" style={{ background: "rgba(24, 24, 27, 0.4)", backdropFilter: "blur(12px)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 24 }} aria-label="VC Dimension Analysis">
              <div className="issues-heading" style={{ textAlign: "center", marginBottom: 0 }}>Venture Capital Lenses</div>
              <VCRadarChart dimensions={report.dimensionScores} />
            </section>
          )}
        </div>

        <section className="issues-section" style={{ background: "rgba(24, 24, 27, 0.4)", backdropFilter: "blur(12px)", border: "1px solid var(--border)", borderRadius: "var(--radius)" }} aria-label="Evaluation findings">
          <div className="issues-heading" style={{ padding: "24px 24px 16px", borderBottom: "1px solid var(--border)", margin: 0 }}>Findings to Fix</div>

          {report.issues.length === 0 ? (
            <div style={{ padding: 24 }}>
              <p className="error-bar" style={{ background: "var(--brand-glow)", color: "var(--brand)", border: "1px solid var(--brand)" }}>
                No critical issues detected! Your startup looks solid. Fix it with Sift to refine further.
              </p>
            </div>
          ) : (
            <div role="list" style={{ padding: 12 }}>
              {report.issues.map((issue, idx) => (
                <IssueRow key={idx} issue={issue} index={idx} />
              ))}
            </div>
          )}

          <div className="issues-summary" style={{ padding: "16px 24px", borderTop: "1px solid var(--border)", background: "var(--surface)" }}>
            <span style={{ color: "var(--text-secondary)" }}>{report.issues.length} finding{report.issues.length !== 1 ? "s" : ""} total</span>
            <button
              type="button"
              className="nav-link"
              onClick={onStartOver}
              aria-label="Start a new evaluation"
            >
              New evaluation
            </button>
          </div>
        </section>

        <div className="fix-cta" ref={fixRef} style={{ marginTop: 24 }}>
          <button
            id="fix-it-btn"
            type="button"
            className="btn-primary"
            onClick={onFixIt}
            aria-label="Fix issues with Sift Co-Pilot"
            style={{ fontSize: 16, padding: "16px 24px", background: "linear-gradient(135deg, var(--brand), #2563eb)", border: "1px solid #3b82f6", boxShadow: "0 0 20px var(--brand-glow)" }}
          >
            Fix it with Sift ✨
          </button>
        </div>
      </div>
    </main>
  );
}
