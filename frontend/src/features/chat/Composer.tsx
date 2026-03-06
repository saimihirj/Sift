import { useRef } from "react";

type Props = {
  value: string;
  onChange: (nextValue: string) => void;
  onSubmit: () => void;
  pending: boolean;
  selectedFile: File | null;
  onFileSelected: (file: File | null) => void;
};

export function Composer({
  value,
  onChange,
  onSubmit,
  pending,
  selectedFile,
  onFileSelected,
}: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  return (
    <div className="composer-shell">
      <div className="attachment-row">
        <div className="attachment-meta">
          <span className="rail-label">Context</span>
          <small>PDF, PPTX, DOCX, TXT</small>
        </div>
        <div className="attachment-actions">
          <button type="button" className="ghost-button compact" onClick={() => inputRef.current?.click()}>
            {selectedFile ? "Change file" : "Upload notes or deck"}
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
          placeholder="Describe the problem, answer the last question, or add context..."
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if ((event.metaKey || event.ctrlKey) && event.key === "Enter" && !pending) {
              event.preventDefault();
              onSubmit();
            }
          }}
          rows={3}
          disabled={pending}
        />
        <button type="button" className="solid-button composer-send" onClick={onSubmit} disabled={pending}>
          {pending ? "Thinking..." : "Send"}
        </button>
      </div>
    </div>
  );
}
