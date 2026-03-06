import type { ThemeMode } from "./types";

type Props = {
  theme: ThemeMode;
  onChange: (theme: ThemeMode) => void;
};

const OPTIONS: Array<{ key: ThemeMode; label: string }> = [
  { key: "light", label: "Light" },
  { key: "dark", label: "Dark" },
  { key: "neon", label: "Neon" },
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
          {option.label}
        </button>
      ))}
    </div>
  );
}
