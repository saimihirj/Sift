import type { ProviderOption, ResponseProfile } from "../../app/types";

type Props = {
  isOpen: boolean;
  title: string;
  providerOptions: ProviderOption[];
  provider: string;
  model: string;
  apiKey: string;
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
