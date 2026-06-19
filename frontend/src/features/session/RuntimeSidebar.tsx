import { useState } from "react";
import type { ProviderOption, ResponseProfile, RuntimeUsageSummary } from "../../app/types";
import { SiftBrainPanel } from "./SiftBrainPanel";

function isLocalProviderKey(key: string): boolean {
  return key === "ollama" || key === "local_openai" || key === "sift_brain";
}

type DecisionTrace = {
  queryType: string;
  provider: string;
  kbHits: number;
  complexity: string;
  usedKB: boolean;
};

type Props = {
  isOpen: boolean;
  title: string;
  providerOptions: ProviderOption[];
  provider: string;
  model: string;
  apiKey: string;
  runtimeUsage?: RuntimeUsageSummary;
  responseProfile: ResponseProfile;
  onResponseProfileChange?: (profile: ResponseProfile) => void;
  applying: boolean;
  onClose: () => void;
  onProviderChange: (provider: string) => void;
  onModelChange: (model: string) => void;
  onApiKeyChange: (value: string) => void;
  onUseDefaultModel: (profile: ResponseProfile) => void;
  onApply: () => void;
  /** True while the model is streaming a response — shows abort button. */
  streaming?: boolean;
  /** Called when user presses the abort/stop button. */
  onAbort?: () => void;
  /** Time-to-first-token in ms for the last completed response. */
  ttft?: number;
  /** Tokens per second for the last completed response. */
  tps?: number;
  /** Decision trace from the last turn (populated by router.py). */
  decisionTrace?: DecisionTrace;
};

function ttftClass(ms: number): string {
  if (ms < 500) return "ok";
  if (ms < 1500) return "warn";
  return "slow";
}

function formatTtft(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

export function RuntimeSidebar({
  isOpen,
  title,
  providerOptions,
  provider,
  model,
  apiKey,
  runtimeUsage,
  responseProfile,
  onResponseProfileChange,
  applying,
  onClose,
  onProviderChange,
  onModelChange,
  onApiKeyChange,
  onUseDefaultModel,
  onApply,
  streaming = false,
  onAbort,
  ttft,
  tps,
  decisionTrace,
}: Props) {
  const [brainExpanded, setBrainExpanded] = useState(false);

  const selectedProvider = providerOptions.find((item) => item.key === provider) ?? providerOptions[0] ?? null;
  const requiresApiKey = Boolean(selectedProvider?.requiresApiKey);
  const requiresClientApiKey = Boolean(selectedProvider?.requiresApiKey && !selectedProvider.serverConfigured);
  const profileLabel = responseProfile === "speed" ? "Fast" : "Sharper";
  const modelValue = model.trim();
  const isCustomModel = Boolean(
    selectedProvider
      && modelValue
      && modelValue !== selectedProvider.defaultSpeedModel
      && modelValue !== selectedProvider.defaultBalancedModel,
  );
  const formatTokens = (value: number) => `${Math.max(0, Math.round(value || 0)).toLocaleString()} tok`;
  const lastUsage = runtimeUsage?.last;
  const sessionUsage = runtimeUsage?.session;
  const accessLabel = selectedProvider
    ? selectedProvider.requiresApiKey
      ? selectedProvider.serverConfigured
        ? "Server key ready"
        : "Needs session key"
      : "Local key-free"
    : "Runtime";

  return (
    <div className={isOpen ? "floating-panel is-open align-right" : "floating-panel align-right"} aria-hidden={!isOpen}>
      <button type="button" className={isOpen ? "floating-backdrop is-open" : "floating-backdrop"} onClick={onClose} aria-label="Close runtime" />
      <aside className={isOpen ? "floating-card runtime-card is-open" : "floating-card runtime-card"}>
        <div className="floating-head">
          <div>
            <span className="rail-label">Model</span>
            <strong>{title}</strong>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            {/* Abort button — only shown while streaming */}
            {streaming && onAbort && (
              <button type="button" className="abort-stream-btn" onClick={onAbort} aria-label="Stop generation">
                Stop
              </button>
            )}
            <button type="button" className="ghost-button compact" onClick={onClose}>
              Close
            </button>
          </div>
        </div>

        {/* Streaming stats row */}
        {(ttft !== undefined || tps !== undefined) && !streaming && (
          <div className="stream-stats">
            {ttft !== undefined && (
              <div className="stream-stat">
                <span>TTFT</span>
                <span className={`stream-stat-value ${ttftClass(ttft)}`}>{formatTtft(ttft)}</span>
              </div>
            )}
            {ttft !== undefined && tps !== undefined && (
              <span className="stream-stat-sep">·</span>
            )}
            {tps !== undefined && (
              <div className="stream-stat">
                <span>Throughput</span>
                <span className="stream-stat-value ok">{tps.toFixed(1)} tok/s</span>
              </div>
            )}
          </div>
        )}

        {onResponseProfileChange ? (
          <div className="identity-field">
            <span className="rail-label">Mode</span>
            <div className="segmented runtime-segmented">
              {(["speed", "balanced"] as ResponseProfile[]).map((profile) => (
                <button
                  key={profile}
                  type="button"
                  className={responseProfile === profile ? "segment active" : "segment"}
                  onClick={() => onResponseProfileChange(profile)}
                >
                  {profile === "speed" ? "Fast" : "Sharper"}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        <div className="identity-field">
          <span className="rail-label">Provider</span>
          <div className="runtime-provider-grid">
            {providerOptions.map((item) => (
              <button
                key={item.key}
                type="button"
                className={provider === item.key ? "chip-card active" : "chip-card"}
                onClick={() => onProviderChange(item.key)}
              >
                <span>{item.label}</span>
                <small>{item.requiresApiKey ? (item.serverConfigured ? "Server key" : "Bring key") : (isLocalProviderKey(item.key) ? "Local" : "Server")}</small>
              </button>
            ))}
          </div>
        </div>

        {selectedProvider ? (
          <div className="runtime-recommendation-card compact-runtime-card">
            <div>
              <span className="rail-label">{accessLabel}</span>
              <strong>{selectedProvider.label}</strong>
            </div>
            <p>{selectedProvider.publicReadiness || selectedProvider.bestFor || "Ready for this session."}</p>
          </div>
        ) : null}

        <label className="identity-field">
          <span className="rail-label">Model</span>
          <input
            value={model}
            onChange={(event) => onModelChange(event.target.value)}
            placeholder={selectedProvider?.defaultSpeedModel || "Enter a model id"}
          />
          {isCustomModel ? <small className="muted-copy">Custom model</small> : null}
        </label>

        <div className="runtime-chip-row">
          <button type="button" className="ghost-button compact" onClick={() => onUseDefaultModel("speed")}>
            Fast
          </button>
          <button type="button" className="ghost-button compact" onClick={() => onUseDefaultModel("balanced")}>
            Sharper
          </button>
        </div>

        {selectedProvider?.modelPresets?.length ? (
          <div className="model-preset-grid compact-model-preset-grid">
            {selectedProvider.modelPresets.map((preset) => (
              <button
                key={`${selectedProvider.key}-${preset.value}`}
                type="button"
                className={modelValue === preset.value ? "model-preset-chip active" : "model-preset-chip"}
                onClick={() => onModelChange(preset.value)}
              >
                <span>{preset.label}</span>
                {preset.note ? <small>{preset.note}</small> : null}
              </button>
            ))}
          </div>
        ) : null}

        {requiresApiKey ? (
          <label className="identity-field">
            <span className="rail-label">{selectedProvider?.serverConfigured ? "Session API key override" : "Session API key"}</span>
            <input
              type="password"
              value={apiKey}
              onChange={(event) => onApiKeyChange(event.target.value)}
              placeholder={selectedProvider?.serverConfigured ? "Optional override for this browser session" : `Required for ${selectedProvider?.label || provider}`}
            />
            {selectedProvider?.serverConfigured ? <small className="muted-copy">Server key ready.</small> : null}
            {requiresClientApiKey ? <small className="muted-copy">Required for this session.</small> : null}
          </label>
        ) : null}

        {runtimeUsage ? (
          <div className="drawer-card">
            <span className="rail-label">Token usage</span>
            <div className="report-doc-summary runtime-usage-summary">
              <div>
                <span className="rail-label">Last response</span>
                <strong>{formatTokens(lastUsage?.totalTokens ?? 0)}</strong>
                <small className="muted-copy">
                  {formatTokens(lastUsage?.promptTokens ?? 0)} in · {formatTokens(lastUsage?.completionTokens ?? 0)} out
                  {lastUsage?.estimated ? " · estimated" : ""}
                </small>
              </div>
              <div>
                <span className="rail-label">Session total</span>
                <strong>{formatTokens(sessionUsage?.totalTokens ?? 0)}</strong>
                <small className="muted-copy">
                  {formatTokens(sessionUsage?.promptTokens ?? 0)} in · {formatTokens(sessionUsage?.completionTokens ?? 0)} out
                  {sessionUsage?.estimated ? " · mixed exact/estimated" : ""}
                </small>
              </div>
            </div>
          </div>
        ) : null}

        <p className="muted-copy">
          {requiresApiKey
            ? (selectedProvider?.serverConfigured ? "Server key is used unless you override it." : "Your key stays in this browser session.")
            : `${profileLabel} local mode.`}
        </p>

        {/* ── Sift Brain Panel ─────────────────────────────────────────── */}
        <SiftBrainPanel
          ttft={ttft}
          tps={tps}
          decisionTrace={decisionTrace}
          expanded={brainExpanded}
          onToggle={() => setBrainExpanded((v) => !v)}
        />

        <div className="floating-actions">
          <button type="button" className="ghost-button" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="solid-button" onClick={onApply} disabled={applying}>
            {applying ? "Applying..." : "Apply runtime"}
          </button>
        </div>
      </aside>
    </div>
  );
}
