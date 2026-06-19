/**
 * SiftBrainPanel — Live intelligence layer status panel.
 *
 * Shows:
 *  - Neural engine status badge (active / standby / unconfigured)
 *  - Knowledge graph stats (domain count, total cards, index status)
 *  - Per-domain freshness (last updated, card count)
 *  - Decision trace from last session turn (query type, provider route, KB hits)
 *  - Token throughput (tokens/sec) and TTFT from last response
 *  - Adapter registry entry if a fine-tuned model is loaded
 */

import { useEffect, useState } from "react";

type BrainStatus = {
  engineStatus: "active" | "standby" | "unconfigured";
  totalCards: number;
  totalDomains: number;
  indexedCards: number;
  adapterName?: string;
  adapterBaseModel?: string;
  adapterScore?: number;
  domains: Array<{
    key: string;
    cardCount: number;
    lastUpdated?: string;
  }>;
};

type DecisionTrace = {
  queryType: string;
  provider: string;
  kbHits: number;
  complexity: string;
  usedKB: boolean;
};

type Props = {
  /** TTFT in milliseconds for last response. */
  ttft?: number;
  /** Tokens per second for last response. */
  tps?: number;
  /** Decision trace from last chat turn. Passed by parent. */
  decisionTrace?: DecisionTrace;
  /** Whether this panel is expanded (controlled by RuntimeSidebar). */
  expanded?: boolean;
  onToggle?: () => void;
};

const BRAIN_API = "/api/brain/status";

function ttftClass(ms: number): string {
  if (ms < 500) return "ok";
  if (ms < 1500) return "warn";
  return "slow";
}

function formatTtft(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function formatAgo(iso: string): string {
  try {
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 120) return "just now";
    if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
    return `${Math.round(diff / 86400)}d ago`;
  } catch {
    return "—";
  }
}

export function SiftBrainPanel({ ttft, tps, decisionTrace, expanded = true, onToggle }: Props) {
  const [status, setStatus] = useState<BrainStatus | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!expanded) return;
    setLoading(true);
    fetch(BRAIN_API)
      .then((r) => r.json())
      .then((data: BrainStatus) => setStatus(data))
      .catch(() => {
        setStatus({
          engineStatus: "unconfigured",
          totalCards: 0,
          totalDomains: 0,
          indexedCards: 0,
          domains: [],
        });
      })
      .finally(() => setLoading(false));
  }, [expanded]);

  const badgeClass =
    status?.engineStatus === "active"
      ? "active"
      : status?.engineStatus === "standby"
        ? "standby"
        : "unconfigured";

  const badgeLabel =
    status?.engineStatus === "active"
      ? "Neural engine · Active"
      : status?.engineStatus === "standby"
        ? "Standby"
        : "Not configured";

  return (
    <div className="runtime-brain-section">
      {/* Toggle header */}
      <button
        type="button"
        className="runtime-brain-toggle"
        onClick={onToggle}
        aria-expanded={expanded}
      >
        <span>Sift Brain</span>
        <span className={`runtime-brain-toggle-chevron${expanded ? " open" : ""}`}>▲</span>
      </button>

      {expanded && (
        <div className="sift-brain-panel" style={{ marginTop: "10px" }}>
          {/* Header row */}
          <div className="sift-brain-panel-header">
            <span className="sift-brain-panel-title">Neural Engine</span>
            <span className={`neural-engine-badge ${badgeClass}`}>
              <span className="neural-engine-dot" aria-hidden="true" />
              {loading ? "…" : badgeLabel}
            </span>
          </div>

          {/* Stats grid */}
          {status && (
            <div className="brain-stats-grid">
              <div className="brain-stat-card">
                <span className="brain-stat-label">KB Cards</span>
                <span className={`brain-stat-value${status.totalCards > 0 ? " brain-active" : ""}`}>
                  {status.totalCards.toLocaleString()}
                </span>
                <span className="brain-stat-sub">{status.indexedCards.toLocaleString()} indexed</span>
              </div>
              <div className="brain-stat-card">
                <span className="brain-stat-label">Domains</span>
                <span className="brain-stat-value">{status.totalDomains}</span>
                <span className="brain-stat-sub">knowledge areas</span>
              </div>
            </div>
          )}

          {/* Throughput */}
          {(ttft !== undefined || tps !== undefined) && (
            <div className="brain-stats-grid">
              {ttft !== undefined && (
                <div className="brain-stat-card">
                  <span className="brain-stat-label">TTFT</span>
                  <span className={`brain-stat-value runtime-ttft-value ${ttftClass(ttft)}`}>
                    {formatTtft(ttft)}
                  </span>
                  <span className="brain-stat-sub">first token</span>
                </div>
              )}
              {tps !== undefined && (
                <div className="brain-stat-card">
                  <span className="brain-stat-label">Throughput</span>
                  <span className="brain-stat-value brain-active">{tps.toFixed(1)}</span>
                  <span className="brain-stat-sub">tok / sec</span>
                </div>
              )}
            </div>
          )}

          {/* Decision trace */}
          {decisionTrace && (
            <div className="brain-decision-trace">
              <span className="brain-trace-title">Last decision trace</span>
              <div className="brain-trace-row">
                <span className="brain-trace-key">Query type</span>
                <span className="brain-trace-value">{decisionTrace.queryType}</span>
              </div>
              <div className="brain-trace-row">
                <span className="brain-trace-key">Provider</span>
                <span className="brain-trace-value">{decisionTrace.provider}</span>
              </div>
              <div className="brain-trace-row">
                <span className="brain-trace-key">KB hits</span>
                <span className={`brain-trace-value${decisionTrace.kbHits > 0 ? " hit" : ""}`}>
                  {decisionTrace.kbHits}
                </span>
              </div>
              <div className="brain-trace-row">
                <span className="brain-trace-key">Complexity</span>
                <span className="brain-trace-value">{decisionTrace.complexity}</span>
              </div>
            </div>
          )}

          {/* Domain freshness */}
          {status && status.domains.length > 0 && (
            <div>
              <span className="brain-trace-title">Knowledge domains</span>
              <div className="brain-domain-list" style={{ marginTop: "6px" }}>
                {status.domains.map((d) => (
                  <div key={d.key} className="brain-domain-row">
                    <span className="brain-domain-name">{d.key.replace(/_/g, " ")}</span>
                    <span className="brain-domain-count">{d.cardCount}</span>
                    {d.lastUpdated && (
                      <span className="brain-domain-fresh">{formatAgo(d.lastUpdated)}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Adapter badge */}
          {status?.adapterName && (
            <div className="brain-adapter-badge">
              <div>
                <div className="brain-adapter-label">{status.adapterName}</div>
                <div className="brain-adapter-meta">
                  {status.adapterBaseModel ?? "unknown base"}
                  {status.adapterScore !== undefined ? ` · score ${status.adapterScore.toFixed(2)}` : ""}
                </div>
              </div>
              <span className="neural-engine-badge active">
                <span className="neural-engine-dot" aria-hidden="true" />
                Loaded
              </span>
            </div>
          )}

          {/* Setup hint when unconfigured */}
          {status?.engineStatus === "unconfigured" && (
            <p className="muted-copy" style={{ fontSize: "0.74rem", margin: 0 }}>
              Run <code style={{ fontSize: "0.7rem" }}>npm run brain:train</code> then{" "}
              <code style={{ fontSize: "0.7rem" }}>npm run brain:serve</code> to activate the neural engine.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
