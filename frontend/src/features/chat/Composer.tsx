import { useRef, useState } from "react";

import { ALL_UPLOAD_EXTENSIONS, uploadAccept, uploadHint, validateUploadFile } from "../../lib/uploadValidation";

type Props = {
  value: string;
  onChange: (nextValue: string) => void;
  onSubmit: () => void;
  onInterrupt?: () => void;
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
  onInterrupt,
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

  /**
   * While streaming, typing in the textarea calls onInterrupt to abort the
   * in-flight response and pivot to new context immediately.
   */
  const handleChange = (nextValue: string) => {
    if (pending && nextValue !== value && onInterrupt) {
      onInterrupt();
    }
    onChange(nextValue);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (pending && onInterrupt) {
        // Enter while streaming: abort current response, submit the new message.
        onInterrupt();
        // Allow the abort to propagate synchronously before the next submit.
        setTimeout(onSubmit, 0);
      } else if (!pending) {
        onSubmit();
      }
    }
    if (event.key === "Escape" && pending && onInterrupt) {
      event.preventDefault();
      onInterrupt();
    }
  };

  const handleActionButton = () => {
    if (pending && onInterrupt) {
      onInterrupt();
    } else {
      onSubmit();
    }
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
          onChange={(event) => handleChange(event.target.value)}
          onKeyDown={handleKeyDown}
          rows={3}
        />
        <button
          type="button"
          className={pending ? "solid-button composer-send composer-stop" : "solid-button composer-send"}
          onClick={handleActionButton}
          title={pending ? "Stop generating (Esc)" : submitLabel}
          aria-label={pending ? "Stop generating" : submitLabel}
        >
          {pending ? "Stop" : submitLabel}
        </button>
      </div>
      <p className="composer-hint">Enter to send · Shift+Enter for new line · Esc to stop</p>
    </div>
  );
}
