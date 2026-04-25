import { useRef } from "react";

type Props = {
  value: string;
  onChange: (nextValue: string) => void;
  onSubmit: () => void;
  pending: boolean;
  selectedFile: File | null;
  onFileSelected: (file: File | null) => void;
  placeholder?: string;
  attachmentHint?: string;
  uploadLabel?: string;
  submitLabel?: string;
};

export function Composer({
  value,
  onChange,
  onSubmit,
  pending,
  selectedFile,
  onFileSelected,
  placeholder = "Type your answer or add context...",
  attachmentHint = "Notes or deck",
  uploadLabel = "Upload notes or deck",
  submitLabel = "Send",
}: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  return (
    <div className="composer-shell">
      <div className="attachment-row">
        <div className="attachment-meta">
          <span className="rail-label">Context</span>
          <small>{attachmentHint}</small>
        </div>
        <div className="attachment-actions">
          <button type="button" className="ghost-button compact" onClick={() => inputRef.current?.click()}>
            {selectedFile ? "Change file" : uploadLabel}
          </button>
          {selectedFile && <span className="attachment-pill">{selectedFile.name}</span>}
          {selectedFile && (
            <button type="button" className="ghost-button compact" onClick={() => onFileSelected(null)}>
              Remove
            </button>
          )}
        </div>
        <input
          ref={inputRef}
          type="file"
          hidden
          accept=".pdf,.pptx,.docx,.txt"
          onChange={(event) => onFileSelected(event.target.files?.[0] ?? null)}
        />
      </div>
      <div className="composer-row">
        <textarea
          value={value}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !pending) {
              event.preventDefault();
              onSubmit();
            }
          }}
          rows={3}
          disabled={pending}
        />
        <button type="button" className="solid-button composer-send" onClick={onSubmit} disabled={pending}>
          {pending ? "Thinking..." : submitLabel}
        </button>
      </div>
      <p className="composer-hint">Enter to send / Shift+Enter for new line</p>
    </div>
  );
}
