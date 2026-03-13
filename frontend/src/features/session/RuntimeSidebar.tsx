import type { ProviderOption, ResponseProfile, RuntimeUsageSummary } from "../../app/types";

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
};

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
}: Props) {
  const selectedProvider = providerOptions.find((item) => item.key === provider) ?? providerOptions[0] ?? null;
  const requiresApiKey = Boolean(selectedProvider?.requiresApiKey);
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

  return (
    <div className={isOpen ? "floating-panel is-open align-right" : "floating-panel align-right"} aria-hidden={!isOpen}>
      <button type="button" className={isOpen ? "floating-backdrop is-open" : "floating-backdrop"} onClick={onClose} aria-label="Close runtime" />
      <aside className={isOpen ? "floating-card runtime-card is-open" : "floating-card runtime-card"}>
        <div className="floating-head">
          <div>
            <span className="rail-label">Runtime</span>
            <strong>{title}</strong>
          </div>
          <button type="button" className="ghost-button compact" onClick={onClose}>
            Close
          </button>
        </div>

        {onResponseProfileChange ? (
          <div className="identity-field">
            <span className="rail-label">Quality mode</span>
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
                <small>{item.requiresApiKey ? "API key" : "Local"}</small>
              </button>
            ))}
          </div>
        </div>

        <label className="identity-field">
          <span className="rail-label">Model</span>
          <input
            value={model}
            onChange={(event) => onModelChange(event.target.value)}
            placeholder={selectedProvider?.defaultSpeedModel || "Enter a model id"}
          />
          {isCustomModel ? <small className="muted-copy">Custom model</small> : null}
          {selectedProvider?.recommendedDeckModel ? (
            <small className="muted-copy">Deck review recommendation: {selectedProvider.recommendedDeckModel}</small>
          ) : null}
        </label>

        <div className="runtime-chip-row">
          <button type="button" className="ghost-button compact" onClick={() => onUseDefaultModel("speed")}>
            Use Fast default
          </button>
          <button type="button" className="ghost-button compact" onClick={() => onUseDefaultModel("balanced")}>
            Use Sharper default
          </button>
        </div>

        {requiresApiKey ? (
          <label className="identity-field">
            <span className="rail-label">Session API key</span>
            <input
              type="password"
              value={apiKey}
              onChange={(event) => onApiKeyChange(event.target.value)}
              placeholder={`Required for ${selectedProvider?.label || provider}`}
            />
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
            ? "The key stays only in this browser session. Provider and model are saved for the session."
            : `Current quality mode is ${profileLabel}. Local Ollama remains key-free.`}
        </p>

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
