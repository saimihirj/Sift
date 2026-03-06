import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import type { EvaluatorReportPayload, ThemeMode } from "../../app/types";
import { ThemePicker } from "../../app/ThemePicker";
import { getEvaluatorReport } from "../../lib/api/client";

type Props = {
  theme: ThemeMode;
  onThemeChange: (theme: ThemeMode) => void;
  onExitSession: () => void;
};

export function EvaluatorReportScreen({ theme, onThemeChange, onExitSession }: Props) {
  const navigate = useNavigate();
  const { sessionId = "" } = useParams();
  const [payload, setPayload] = useState<EvaluatorReportPayload | null>(null);
  const [status, setStatus] = useState("Loading report...");

  useEffect(() => {
    let cancelled = false;
    if (!sessionId) {
      setStatus("Session not found.");
      return;
    }
    void getEvaluatorReport(sessionId)
      .then((response) => {
        if (cancelled) {
          return;
        }
        setPayload(response);
        setStatus("Report ready");
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        setStatus(error instanceof Error ? error.message : "Failed to load report");
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const report = payload?.evaluationReport;

  return (
    <div className="outline-shell evaluator-report-shell">
      <aside className="left-rail outline-rail">
        <div className="brand-lockup">
          <span className="brand-dot" />
          <div>
            <strong>Evaluator report</strong>
            <p>{status}</p>
          </div>
        </div>

        <div className="rail-card">
          <span className="rail-label">Summary</span>
          <div className="score-pulse large">
            <strong>{report?.overallScore?.toFixed(1) ?? "--"}</strong>
            <span>{report?.partial ? "Partial assessment" : "Success rate"}</span>
          </div>
          <small className="muted-copy">
            {report?.answeredQuestions ?? 0} / {report?.questionBudget ?? 0} answered
          </small>
        </div>

        <div className="rail-footer">
          <button type="button" className="ghost-button" onClick={() => navigate("/")}>
            Back to session
          </button>
          <ThemePicker theme={theme} onChange={onThemeChange} />
          <button type="button" className="ghost-button" onClick={onExitSession}>
            Exit session
          </button>
        </div>
      </aside>

      <main className="outline-main">
        <section className="report-grid">
          <article className="outline-card report-hero">
            <span className="eyebrow">Signal report</span>
            <h2>{report?.summary || "No report available yet."}</h2>
            <p>{report?.why?.[0] || "Answer more questions to generate stronger evaluation feedback."}</p>
          </article>

          <article className="outline-card report-card">
            <div className="admin-card-head">
              <strong>Dimension scores</strong>
              <span className="rail-label">{payload?.provider || "ollama"} · {payload?.model || "-"}</span>
            </div>
            <div className="score-grid dense">
              {(report?.dimensionScores ?? []).map((item) => (
                <div key={item.key} className="score-chip">
                  <strong>{item.score.toFixed(0)}</strong>
                  <span>{item.label}</span>
                </div>
              ))}
            </div>
          </article>
        </section>

        <section className="report-grid report-grid-bottom">
          <article className="outline-card report-card">
            <div className="admin-card-head">
              <strong>Why the score landed here</strong>
              <span className="rail-label">Main reasons</span>
            </div>
            <ul className="upload-list">
              {(report?.why ?? []).map((item) => (
                <li key={item}>
                  <strong>{item}</strong>
                </li>
              ))}
            </ul>
          </article>

          <article className="outline-card report-card">
            <div className="admin-card-head">
              <strong>Fixes to make next</strong>
              <span className="rail-label">Concrete improvements</span>
            </div>
            <ul className="upload-list">
              {(report?.suggestions ?? []).map((item) => (
                <li key={item}>
                  <strong>{item}</strong>
                </li>
              ))}
            </ul>
          </article>
        </section>

        <article className="outline-card report-card question-appendix">
          <div className="admin-card-head">
            <strong>Question appendix</strong>
            <span className="rail-label">Drill-down</span>
          </div>
          <div className="admin-list">
            {(report?.questions ?? []).map((item) => (
              <div key={item.questionId} className="admin-row report-question-row">
                <div>
                  <strong>{item.question}</strong>
                  <p>{item.why}</p>
                  {item.suggestions.length > 0 ? <small>{item.suggestions.join(" · ")}</small> : null}
                </div>
                <div className="admin-row-meta">
                  <span>{item.category}</span>
                  <strong>{item.score.toFixed(1)}</strong>
                </div>
              </div>
            ))}
          </div>
        </article>
      </main>
    </div>
  );
}
