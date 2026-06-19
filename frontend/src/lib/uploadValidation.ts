export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;

export const ALL_UPLOAD_EXTENSIONS = [".pdf", ".pptx", ".docx", ".txt"] as const;
export const DECK_UPLOAD_EXTENSIONS = [".pdf", ".pptx"] as const;

type UploadExtension = typeof ALL_UPLOAD_EXTENSIONS[number];

function extensionFor(file: File): string {
  const dotIndex = file.name.lastIndexOf(".");
  return dotIndex >= 0 ? file.name.slice(dotIndex).toLowerCase() : "";
}

export function uploadAccept(extensions: readonly string[] = ALL_UPLOAD_EXTENSIONS): string {
  return extensions.join(",");
}

export function uploadHint(extensions: readonly string[] = ALL_UPLOAD_EXTENSIONS): string {
  const names = extensions.map((item) => item.replace(".", "").toUpperCase()).join(", ");
  return `${names} up to ${MAX_UPLOAD_BYTES / (1024 * 1024)}MB`;
}

export function validateUploadFile(file: File, extensions: readonly string[] = ALL_UPLOAD_EXTENSIONS): string {
  const ext = extensionFor(file);
  if (!extensions.includes(ext as UploadExtension)) {
    return `Unsupported file type. Upload ${uploadHint(extensions)}.`;
  }
  if (file.size <= 0) {
    return "That file is empty. Upload a readable file.";
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return `File is too large. Current beta limit is ${MAX_UPLOAD_BYTES / (1024 * 1024)}MB per upload.`;
  }
  return "";
}
