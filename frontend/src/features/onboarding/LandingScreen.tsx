import { useRef, useState } from "react";
import type { EvaluatorReport, SiftSession } from "../../app/sift.types";
import { startSession, uploadFile, runEvaluator } from "../../lib/api/client";

interface InputScreenProps {
  onReportReady: (session: SiftSession, report: EvaluatorReport) => void;
}

type InputMode = "deck" | "url" | "idea";

function UploadIcon() {
  return (
    <svg
      className="dropzone-icon"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
    >
      <path d="M10 13V7M7 10l3-3 3 3" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4 14.5A3.5 3.5 0 0 1 4 7.5h.5A5 5 0 0 1 14.5 6H15a3 3 0 0 1 0 6H4z" strokeLinecap="round" />
    </svg>
  );
}

export function InputScreen({ onReportReady }: InputScreenProps) {
  const [activeMode, setActiveMode] = useState<InputMode>("deck");
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [urlValue, setUrlValue] = useState("");
  const [ideaValue, setIdeaValue] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) {
      setFile(dropped);
      setActiveMode("deck");
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = e.target.files?.[0];
    if (picked) {
      setFile(picked);
      setActiveMode("deck");
    }
  }

  function canEvaluate(): boolean {
    if (loading) return false;
    if (activeMode === "deck") return file !== null;
    if (activeMode === "url") return urlValue.trim().length > 0;
    if (activeMode === "idea") return ideaValue.trim().length > 10;
    return false;
  }

  async function handleEvaluate() {
    if (!canEvaluate()) return;
    setError("");
    setLoading(true);

    try {
      const sessionPayload = await startSession({
        provider: "groq",
        model: "",
        founderType: "founder",
        stage: "idea",
        sessionType: "evaluator",
        evaluatorMode: "deck_review",
      });

      const sessionId = sessionPayload.sessionId;
      let sourceName = "your startup";

      if (activeMode === "deck" && file) {
        await uploadFile(sessionId, file, apiKey || undefined);
        sourceName = file.name;
      } else if (activeMode === "url" && urlValue.trim()) {
        await uploadFile(
          sessionId,
          new File([urlValue.trim()], "url-context.txt", { type: "text/plain" }),
          apiKey || undefined,
        );
        sourceName = urlValue.trim().replace(/^https?:\/\//, "").split("/")[0];
      } else if (activeMode === "idea" && ideaValue.trim()) {
        await uploadFile(
          sessionId,
          new File([ideaValue.trim()], "idea.txt", { type: "text/plain" }),
          apiKey || undefined,
        );
        sourceName = "your idea";
      }

      const rawReport = await runEvaluator(sessionId, apiKey || undefined);

      const report: EvaluatorReport = {
        readinessScore:
          typeof rawReport.readinessScore === "number"
            ? rawReport.readinessScore
            : 0,
        issues: Array.isArray(rawReport.issues)
          ? rawReport.issues.map((i) => ({
              severity: (["critical", "warning", "note"].includes(i.severity) ? i.severity : "warning") as "critical" | "warning" | "note",
              title: i.title ?? "",
              explanation: i.explanation ?? "",
              reference: i.reference,
            }))
          : [],
        sessionId,
        sourceName,
      };

      const session: SiftSession = {
        sessionId,
        provider: "groq",
        model: "",
        apiKey: apiKey || undefined,
        sourceName,
        report,
      };

      onReportReady(session, report);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page input-page">
      <div className="input-container">
        <div className="input-label">Upload a deck</div>

        <div
          id="deck-dropzone"
          className={`dropzone${dragOver ? " drag-over" : ""}${file && activeMode === "deck" ? " has-file" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); setActiveMode("deck"); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          aria-label="Upload your pitch deck"
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") fileInputRef.current?.click(); }}
        >
          <UploadIcon />
          <span className="dropzone-text">
            {file && activeMode === "deck" ? file.name : "Drop your deck here"}
          </span>
          <span className="dropzone-subtext">PDF or PPTX</span>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.pptx"
            onChange={handleFileChange}
            aria-hidden="true"
            tabIndex={-1}
          />
        </div>

        <div className="input-divider">or</div>

        <div className="input-label">Paste a URL</div>
        <input
          id="url-input"
          type="url"
          className="text-input"
          placeholder="https://yourwebsite.com or github.com/you/repo"
          value={urlValue}
          onChange={(e) => { setUrlValue(e.target.value); if (e.target.value) setActiveMode("url"); }}
          aria-label="Website or GitHub URL"
        />

        <div className="input-divider">or</div>

        <div className="input-label">Describe your idea</div>
        <textarea
          id="idea-textarea"
          className="textarea-input"
          placeholder="We are building a platform that helps..."
          value={ideaValue}
          onChange={(e) => { setIdeaValue(e.target.value); if (e.target.value) setActiveMode("idea"); }}
          aria-label="Describe your startup idea"
        />

        {showApiKey ? (
          <>
            <div className="input-label" style={{ marginTop: 4 }}>Your API key (optional)</div>
            <input
              id="api-key-input"
              type="password"
              className="text-input"
              placeholder="sk-..."
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              aria-label="API key"
            />
          </>
        ) : (
          <button
            type="button"
            className="nav-link"
            style={{ textAlign: "left", fontSize: 12, marginTop: 2 }}
            onClick={() => setShowApiKey(true)}
          >
            Use your own API key
          </button>
        )}

        {error && (
          <div className="error-bar" role="alert">
            {error}
          </div>
        )}

        <button
          id="evaluate-btn"
          type="button"
          className={`btn-primary${loading ? " loading" : ""}`}
          onClick={handleEvaluate}
          disabled={!canEvaluate()}
          aria-busy={loading}
        >
          {loading ? "Evaluating..." : "Evaluate"}
        </button>
      </div>
    </main>
  );
}
