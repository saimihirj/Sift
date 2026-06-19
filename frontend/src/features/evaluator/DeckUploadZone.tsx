/**
 * DeckUploadZone — Drag-and-drop pitch deck uploader with vision capability badge.
 *
 * Shows:
 *  - Dashed animated drop target
 *  - File preview (name, size, estimated page count)
 *  - DeckVisionBadge: "Vision ON" (image path) or "Text mode" (OCR path)
 *  - Upload progress bar
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { validateUploadFile, uploadAccept, uploadHint, DECK_UPLOAD_EXTENSIONS } from "../../lib/uploadValidation";

type DeckVisionStatus = "vision-on" | "vision-off" | "unknown";

type Props = {
  /** Whether the current model supports image vision (reads page screenshots). */
  visionSupported: boolean;
  /** Called when a valid file is selected. */
  onFileSelect: (file: File) => void;
  /** Called when the selected file is removed. */
  onFileClear: () => void;
  /** Upload progress 0-100. Undefined = not uploading. */
  uploadProgress?: number;
  /** Currently selected file (controlled). */
  selectedFile: File | null;
  /** Whether upload is in-flight. */
  uploading?: boolean;
  /** Allowed MIME hint label, e.g. "PDF, PPTX, PNG" */
  accept?: string;
  /** Forwarded error message from upload validation. */
  error?: string;
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Rough PDF page estimate: ~50 KB per page on average. */
function estimatePageCount(file: File): string {
  if (!file.name.toLowerCase().endsWith(".pdf")) return "";
  const estimate = Math.max(1, Math.round(file.size / (50 * 1024)));
  return `~${estimate} page${estimate === 1 ? "" : "s"}`;
}

function FileIcon({ ext }: { ext: string }) {
  return <div className="deck-file-icon">{ext.toUpperCase().slice(0, 4)}</div>;
}

/** Pill badge showing model vision capability. */
export function DeckVisionBadge({ visionSupported }: { visionSupported: boolean }) {
  return (
    <span className={`deck-vision-badge ${visionSupported ? "vision-on" : "vision-off"}`}>
      <span className="deck-vision-badge-dot" aria-hidden="true" />
      {visionSupported ? "Vision · Image path" : "Text mode · OCR path"}
    </span>
  );
}

/** SVG icon for the empty drop zone. */
function UploadIcon() {
  return (
    <svg
      className="deck-upload-icon"
      viewBox="0 0 40 40"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="6" y="10" width="28" height="22" rx="3" />
      <path d="M14 10V8a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v2" />
      <path d="M20 17v8" />
      <path d="M16 21l4-4 4 4" />
    </svg>
  );
}

export function DeckUploadZone({
  visionSupported,
  onFileSelect,
  onFileClear,
  uploadProgress,
  selectedFile,
  uploading = false,
  error,
}: Props) {
  const [dragActive, setDragActive] = useState(false);
  const [validationError, setValidationError] = useState<string>("");
  const inputRef = useRef<HTMLInputElement>(null);
  const dropRef = useRef<HTMLDivElement>(null);

  // Sync external error
  useEffect(() => {
    if (error) setValidationError(error);
  }, [error]);

  const handleFile = useCallback(
    (file: File) => {
      const err = validateUploadFile(file);
      if (err) {
        setValidationError(err);
        return;
      }
      setValidationError("");
      onFileSelect(file);
    },
    [onFileSelect],
  );

  const handleDragOver = (event: React.DragEvent) => {
    event.preventDefault();
    setDragActive(true);
  };

  const handleDragLeave = (event: React.DragEvent) => {
    if (!dropRef.current?.contains(event.relatedTarget as Node)) {
      setDragActive(false);
    }
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    setDragActive(false);
    const file = event.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) handleFile(file);
    // Reset input so same file can be re-selected
    event.target.value = "";
  };

  const fileExt = selectedFile?.name.split(".").pop() ?? "FILE";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
      {/* Vision badge */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span className="rail-label">Pitch deck</span>
        <DeckVisionBadge visionSupported={visionSupported} />
      </div>

      {/* Drop zone or file preview */}
      {selectedFile ? (
        <div className="deck-file-preview">
          <FileIcon ext={fileExt} />
          <div className="deck-file-info">
            <span className="deck-file-name">{selectedFile.name}</span>
            <span className="deck-file-meta">
              {formatFileSize(selectedFile.size)}
              {estimatePageCount(selectedFile) ? ` · ${estimatePageCount(selectedFile)}` : ""}
              {" · "}
              {visionSupported ? "pages will be read as images" : "text will be extracted"}
            </span>
          </div>
          {!uploading && (
            <button
              type="button"
              className="deck-file-remove"
              onClick={() => {
                onFileClear();
                setValidationError("");
              }}
              aria-label="Remove selected file"
            >
              ×
            </button>
          )}
        </div>
      ) : (
        <div
          ref={dropRef}
          className={`deck-upload-zone${dragActive ? " drag-active" : ""}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          role="button"
          tabIndex={0}
          aria-label="Upload pitch deck — click or drag and drop"
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") inputRef.current?.click(); }}
        >
          <input
            ref={inputRef}
            type="file"
            className="deck-upload-input"
            accept={uploadAccept(DECK_UPLOAD_EXTENSIONS)}
            onChange={handleInputChange}
            tabIndex={-1}
            aria-hidden="true"
          />
          <UploadIcon />
          <p className="deck-upload-title">
            {dragActive ? "Drop your deck here" : "Upload your pitch deck"}
          </p>
          <p className="deck-upload-hint">
            {uploadHint(DECK_UPLOAD_EXTENSIONS)}
            {" · "}
            {visionSupported
              ? "Model reads page images directly"
              : "Model reads extracted text"}
          </p>
        </div>
      )}

      {/* Progress bar */}
      {uploading && uploadProgress !== undefined && (
        <div className="deck-upload-progress" role="progressbar" aria-valuenow={uploadProgress} aria-valuemin={0} aria-valuemax={100}>
          <div className="deck-upload-progress-bar" style={{ width: `${uploadProgress}%` }} />
        </div>
      )}

      {/* Validation error */}
      {validationError && (
        <div className="setup-alert" role="alert">{validationError}</div>
      )}
    </div>
  );
}
