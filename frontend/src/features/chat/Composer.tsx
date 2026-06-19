import { useRef, useState } from "react";

import { ALL_UPLOAD_EXTENSIONS, uploadAccept, uploadHint, validateUploadFile } from "../../lib/uploadValidation";

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
  const [uploadError, setUploadError] = useState("");

  const handleFileSelected = (file: File | null) => {
    setUploadError("");
    if (!file) {
      onFileSelected(null);
      return;
    }
    const error = validateUploadFile(file, ALL_UPLOAD_EXTENSIONS);
    if (error) {
      setUploadError(error);
      onFileSelected(null);
      return;
    }
    onFileSelected(file);
  };

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
            <button type="button" className="ghost-button compact" onClick={() => handleFileSelected(null)}>
              Remove
            </button>
          )}
        </div>
        <input
          ref={inputRef}
          type="file"
          hidden
          accept={uploadAccept()}
          onChange={(event) => {
            handleFileSelected(event.target.files?.[0] ?? null);
            event.currentTarget.value = "";
          }}
        />
      </div>
      <small className={uploadError ? "upload-helper error" : "upload-helper"}>{uploadError || uploadHint()}</small>
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
