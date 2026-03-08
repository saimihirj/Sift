import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import type { EvaluatorReportPayload, ThemeMode } from "../../app/types";
import { continueEvaluator, getEvaluatorReport } from "../../lib/api/client";

type Props = {
  theme: ThemeMode;
  onThemeChange: (theme: ThemeMode) => void;
  onExitSession: () => void;
  onResumeSession: (sessionId: string) => Promise<void> | void;
};

function joinBullets(items: string[]): string {
  if (!items.length) {
    return "- None";
  }
  return items.map((item) => `- ${item}`).join("\n");
}

function joinNumbered(items: string[]): string {
  if (!items.length) {
    return "1. None";
  }
  return items.map((item, index) => `${index + 1}. ${item}`).join("\n");
}

function formatLensBullet(item: EvaluatorReportPayload["evaluationReport"]["coreLenses"][number]): string {
  const parts = [`**${item.label} (${item.status})**: ${item.why || "Not available."}`];
  if (item.evidence.length > 0) {
    parts.push(`Evidence used: ${item.evidence.join(" | ")}.`);
  }
  if (item.improvement) {
    parts.push(`Improve next: ${item.improvement}`);
  }
  return parts.join(" ");
}

function pickLensGroups(report: EvaluatorReportPayload["evaluationReport"]) {
  const all = [...(report.coreLenses ?? []), ...(report.supportingLenses ?? [])];
  return {
    working: all.filter((item) => item.status === "strong"),
    needsWork: all.filter((item) => item.status !== "strong"),
  };
}

function buildQuestionAppendix(questions: EvaluatorReportPayload["evaluationReport"]["questions"]): string {
  if (!questions.length) {
    return "## Question Appendix\n\n- No question appendix available.\n";
  }
  return [
    "## Question Appendix",
    "",
    ...questions.flatMap((item, index) => {
      const lines = [
        `### ${index + 1}. ${item.question}`,
        `- Category: ${item.category}`,
        `- Score: ${item.score.toFixed(1)}`,
        `- Why: ${item.why || "Not available"}`,
      ];
      if (item.suggestions.length > 0) {
        lines.push(`- Suggestions: ${item.suggestions.join(" | ")}`);
      }
      lines.push("");
      return lines;
    }),
  ].join("\n");
}

function buildReportMarkdown(payload: EvaluatorReportPayload): string {
  const report = payload.evaluationReport;
  const groups = pickLensGroups(report);
  return [
    "# Signal Evaluation Report",
    "",
    `**Verdict:** ${report.verdict || report.summary || "Not available"}`,
    `**Success score:** ${report.overallScore.toFixed(1)}`,
    `**Confidence:** ${report.confidence ? `${report.confidence.toFixed(0)} / 100` : "Pending"}`,
    `**Questions asked:** ${report.answeredQuestions}`,
    `**Report type:** ${report.partial ? "Partial assessment" : "Complete assessment"}`,
    `**Runtime:** ${payload.provider || "ollama"} · ${payload.model || "-"}`,
    `**Stop reason:** ${report.stopReason || "Not available"}`,
    "",
    "## Plain-English Takeaway",
    "",
    report.summary || report.verdict || "No summary available.",
    "",
    "## Why This Score",
    "",
    joinBullets(report.why ?? []),
    "",
    "## What Is Already Working",
    "",
    joinBullets(groups.working.map(formatLensBullet)),
    "",
    "## What Still Needs Work",
    "",
    joinBullets(groups.needsWork.map(formatLensBullet)),
    "",
    "## Top Fixes",
    "",
    joinNumbered(report.suggestions ?? []),
    "",
    "## Missing Evidence / Open Risks",
    "",
    joinBullets(report.missingEvidence ?? []),
    "",
    "## Next Experiments",
    "",
    joinBullets(report.nextExperiments ?? []),
    "",
    buildQuestionAppendix(report.questions ?? []),
  ].join("\n");
}

export function EvaluatorReportScreen({ theme, onThemeChange, onExitSession, onResumeSession }: Props) {
  const navigate = useNavigate();
  const { sessionId = "" } = useParams();
  const [payload, setPayload] = useState<EvaluatorReportPayload | null>(null);
  const [status, setStatus] = useState("Loading report...");
  const [continuing, setContinuing] = useState(false);

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
  const canGoDeeper = Boolean(payload?.evaluationProgress?.canGoDeeper);
  const reportReady = Boolean(payload?.evaluationProgress?.completed);
  const lensGroups = report ? pickLensGroups(report) : { working: [], needsWork: [] };

  void theme;
  void onThemeChange;

  const handleDownload = () => {
    if (!payload || !report) {
      return;
    }
    const markdown = buildReportMarkdown(payload);
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const suffix = report.partial ? "partial" : "final";
    link.href = url;
    link.download = `signal-evaluation-${sessionId || "report"}-${suffix}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="report-doc-shell">
      <header className="pane-header">
        <div>
          <span className="eyebrow">Evaluate report</span>
          <h2>{reportReady ? "Evaluation report" : "Report not ready yet"}</h2>
        </div>
        <div className="status-stack">
          <div className="header-actions">
            <button type="button" className="ghost-button compact" onClick={() => navigate("/")}>
              Back
            </button>
            <button type="button" className="ghost-button compact" onClick={handleDownload} disabled={!reportReady || !report}>
              Download
            </button>
            {canGoDeeper ? (
              <button
                type="button"
                className="ghost-button compact"
                disabled={continuing}
                onClick={() => {
                  if (!sessionId) {
                    return;
                  }
                  setContinuing(true);
                  void continueEvaluator(sessionId)
                    .then(async () => {
                      await onResumeSession(sessionId);
                      navigate("/");
                    })
                    .finally(() => setContinuing(false));
                }}
              >
                {continuing ? "Opening..." : "Ask more questions"}
              </button>
            ) : null}
            <button type="button" className="ghost-button compact" onClick={onExitSession}>
              Exit
            </button>
          </div>
          <small>{status}</small>
        </div>
      </header>

      <main className="report-doc-main">
        <article className="outline-card report-doc-card">
          {!reportReady || !report ? (
            <section className="report-doc-section">
              <h3>Keep answering for now</h3>
              <p className="report-doc-lead">
                The evaluator is not satisfied enough yet to issue a final verdict. Go back to the session and answer the latest question. The report will appear once the engine has enough evidence.
              </p>
            </section>
          ) : (
            <>
              <div className="report-doc-head">
                <div className="report-doc-title">
                  <span className="eyebrow">Verdict</span>
                  <h1>{report.verdict || report.summary || "No report available yet."}</h1>
                  <p>{report.summary || report.stopReason || report.why?.[0] || "No summary available."}</p>
                </div>
                <div className="report-doc-score">
                  <strong>{report.overallScore.toFixed(1)}</strong>
                  <span>{report.partial ? "Partial assessment" : "Success score"}</span>
                </div>
              </div>

              <section className="report-doc-section">
                <p className="report-doc-lead">
                  {report.summary || report.verdict}
                </p>
                <div className="report-doc-summary">
                  <div>
                    <span className="rail-label">Confidence</span>
                    <strong>{report.confidence ? `${report.confidence.toFixed(0)} / 100` : "Pending"}</strong>
                  </div>
                  <div>
                    <span className="rail-label">Questions asked</span>
                    <strong>{report.answeredQuestions}</strong>
                  </div>
                  <div>
                    <span className="rail-label">Runtime</span>
                    <strong>{payload?.provider || "ollama"} · {payload?.model || "-"}</strong>
                  </div>
                  <div>
                    <span className="rail-label">Stop reason</span>
                    <strong>{report.stopReason || "Not available"}</strong>
                  </div>
                </div>
              </section>

              {(report.why?.length ?? 0) > 0 ? (
                <section className="report-doc-section">
                  <h3>Why this score</h3>
                  <ul className="report-doc-bullets">
                    {report.why.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </section>
              ) : null}

              <section className="report-doc-section">
                <h3>What is already working</h3>
                <ul className="report-doc-bullets">
                  {(lensGroups.working.length ? lensGroups.working : report.coreLenses.slice(0, 1)).map((item) => (
                    <li key={item.key}>{formatLensBullet(item)}</li>
                  ))}
                </ul>
              </section>

              <section className="report-doc-section">
                <h3>What still needs work</h3>
                <ul className="report-doc-bullets">
                  {(lensGroups.needsWork.length ? lensGroups.needsWork : report.supportingLenses).map((item) => (
                    <li key={item.key}>{formatLensBullet(item)}</li>
                  ))}
                </ul>
              </section>

              <section className="report-doc-section">
                <h3>Top fixes</h3>
                <ol className="report-doc-bullets ordered">
                  {(report.suggestions ?? []).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ol>
              </section>

              <section className="report-doc-section">
                <h3>Missing evidence or open risks</h3>
                <ul className="report-doc-bullets">
                  {(report.missingEvidence ?? []).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </section>

              <section className="report-doc-section">
                <h3>Next experiments</h3>
                <ul className="report-doc-bullets">
                  {(report.nextExperiments ?? []).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </section>

              {(report.questions?.length ?? 0) > 0 ? (
                <details className="report-doc-details">
                  <summary>Question appendix</summary>
                  <div className="report-doc-stack">
                    {report.questions.map((item, index) => (
                      <section key={item.questionId} className="report-doc-item">
                        <div className="report-doc-item-head">
                          <strong>{index + 1}. {item.question}</strong>
                          <span className="rail-label">{item.category} · {item.score.toFixed(1)}</span>
                        </div>
                        <p>{item.why}</p>
                        {item.suggestions.length > 0 ? (
                          <ul className="report-doc-bullets compact">
                            {item.suggestions.map((suggestion) => (
                              <li key={suggestion}>{suggestion}</li>
                            ))}
                          </ul>
                        ) : null}
                      </section>
                    ))}
                  </div>
                </details>
              ) : null}
            </>
          )}
        </article>
      </main>
    </div>
  );
}
