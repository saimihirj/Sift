import type { ThemeMode } from "./types";

type Props = {
  theme: ThemeMode;
  onChange: (theme: ThemeMode) => void;
};

const OPTIONS: Array<{ key: ThemeMode; label: string; note: string }> = [
  { key: "light", label: "Paper", note: "Warm black and white" },
  { key: "dark", label: "Midnight", note: "Soft dark focus" },
  { key: "dusk", label: "Dusk", note: "Muted evening contrast" },
  { key: "neon", label: "Neon", note: "Sharper electric glow" },
];

export function ThemePicker({ theme, onChange }: Props) {
  return (
    <div className="theme-picker" role="tablist" aria-label="Theme selection">
      {OPTIONS.map((option) => (
        <button
          key={option.key}
          type="button"
          role="tab"
          aria-selected={theme === option.key}
          className={theme === option.key ? "theme-option active" : "theme-option"}
          onClick={() => onChange(option.key)}
        >
          <span className="theme-option-label">{option.label}</span>
          <small className="theme-option-note">{option.note}</small>
        </button>
      ))}
    </div>
  );
}
