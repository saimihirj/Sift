import { useEffect, useRef, useState } from "react";
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
        />
      </svg>
      <div className="score-number">
        <span className="score-value">{clamped}</span>
        <span className="score-total">/ 100</span>
      </div>
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
        <span className="issue-severity-dot" />
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
        style={{ flexShrink: 0, alignSelf: "flex-start" }}
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
    <main className="page">
      <div className="scorecard-page">
        <section className="score-header" aria-label="Readiness overview">
          {report.sourceName && (
            <span className="score-source">{report.sourceName}</span>
          )}
          <div className="score-ring-wrapper">
            <ScoreRing score={report.readinessScore} />
            <span className="score-label">Readiness Score</span>
          </div>
          {(criticalCount > 0 || warningCount > 0) && (
            <p style={{ fontSize: 13, color: "var(--text-muted)", textAlign: "center" }}>
              {criticalCount > 0 && `${criticalCount} critical issue${criticalCount > 1 ? "s" : ""}`}
              {criticalCount > 0 && warningCount > 0 && " · "}
              {warningCount > 0 && `${warningCount} warning${warningCount > 1 ? "s" : ""}`}
            </p>
          )}
        </section>

        <section className="issues-section" aria-label="Evaluation findings">
          <div className="issues-heading">Findings</div>

          {report.issues.length === 0 ? (
            <p className="error-bar">
              No issues detected. Your startup looks solid. Fix it with Sift to refine further.
            </p>
          ) : (
            <div role="list">
              {report.issues.map((issue, idx) => (
                <IssueRow key={idx} issue={issue} index={idx} />
              ))}
            </div>
          )}

          <div className="issues-summary">
            <span>{report.issues.length} finding{report.issues.length !== 1 ? "s" : ""} total</span>
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

        <div className="fix-cta" ref={fixRef}>
          <button
            id="fix-it-btn"
            type="button"
            className="btn-primary"
            onClick={onFixIt}
            aria-label="Fix issues with Sift Co-Pilot"
          >
            Fix it with Sift
          </button>
        </div>
      </div>
    </main>
  );
}
