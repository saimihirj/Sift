import { useState } from "react";
import { BrowserRouter, Route, Routes, useNavigate } from "react-router-dom";
import type { EvaluatorReport, SiftSession } from "./sift.types";
import { InputScreen } from "../features/onboarding/LandingScreen";
import { ScorecardScreen } from "../features/evaluator/ScorecardScreen";
import { CopilotScreen } from "../features/chat/CopilotScreen";

function Nav({ onStartOver }: { onStartOver?: () => void }) {
  return (
    <nav className="sift-nav" aria-label="Sift navigation">
      <span className="sift-wordmark">Sift</span>
      {onStartOver && (
        <div className="nav-actions">
          <button
            type="button"
            className="nav-link"
            onClick={onStartOver}
            aria-label="Start a new evaluation"
          >
            New evaluation
          </button>
        </div>
      )}
    </nav>
  );
}

function AppRoutes() {
  const navigate = useNavigate();
  const [session, setSession] = useState<SiftSession | null>(null);
  const [report, setReport] = useState<EvaluatorReport | null>(null);

  function handleReportReady(newSession: SiftSession, newReport: EvaluatorReport) {
    setSession(newSession);
    setReport(newReport);
    navigate("/scorecard");
  }

  function handleFixIt() {
    navigate("/copilot");
  }

  function handleStartOver() {
    setSession(null);
    setReport(null);
    navigate("/");
  }

  return (
    <>
      <Routes>
        <Route
          path="/"
          element={
            <>
              <Nav />
              <InputScreen onReportReady={handleReportReady} />
            </>
          }
        />
        <Route
          path="/scorecard"
          element={
            session && report ? (
              <>
                <Nav onStartOver={handleStartOver} />
                <ScorecardScreen
                  session={session}
                  report={report}
                  onFixIt={handleFixIt}
                  onStartOver={handleStartOver}
                />
              </>
            ) : (
              <>
                <Nav />
                <InputScreen onReportReady={handleReportReady} />
              </>
            )
          }
        />
        <Route
          path="/copilot"
          element={
            session ? (
              <>
                <Nav onStartOver={handleStartOver} />
                <CopilotScreen session={session} onStartOver={handleStartOver} />
              </>
            ) : (
              <>
                <Nav />
                <InputScreen onReportReady={handleReportReady} />
              </>
            )
          }
        />
        <Route
          path="*"
          element={
            <>
              <Nav />
              <InputScreen onReportReady={handleReportReady} />
            </>
          }
        />
      </Routes>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
