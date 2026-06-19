import { useEffect, useState } from "react";

const STEPS = [
  "Initializing neural pathways...",
  "Querying expert vectors...",
  "Extracting semantic meaning...",
  "Synthesizing response...",
];

export function TelemetryLoader() {
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setStepIndex((idx) => Math.min(idx + 1, STEPS.length - 1));
    }, 800);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="telemetry-loader" style={{
      fontFamily: "var(--font-mono)",
      fontSize: "12px",
      color: "var(--accent)",
      padding: "12px",
      background: "var(--surface-sunken)",
      border: "1px solid var(--border)",
      borderRadius: "8px",
      display: "flex",
      flexDirection: "column",
      gap: "4px",
      opacity: 0.8
    }}>
      {STEPS.slice(0, stepIndex + 1).map((step, i) => (
        <div key={i} style={{ display: "flex", justifyContent: "space-between" }}>
          <span>{`> ${step}`}</span>
          {i < stepIndex ? <span>[OK]</span> : <span className="blinking-cursor">_</span>}
        </div>
      ))}
      <style>
        {`
          @keyframes blink {
            0% { opacity: 1; }
            50% { opacity: 0; }
            100% { opacity: 1; }
          }
          .blinking-cursor {
            animation: blink 1s infinite;
          }
        `}
      </style>
    </div>
  );
}
