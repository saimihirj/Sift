"""Upload parsing and lightweight lexical retrieval."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import UploadFile


DATA_DIR = Path(os.environ.get("VK_DATA_DIR", "data"))
UPLOADS_DIR = DATA_DIR / "session_uploads"
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
TOKEN_PATTERN = re.compile(r"[a-z0-9]{3,}")


def _session_dir(session_id: str) -> Path:
    path = UPLOADS_DIR / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _manifest_path(session_id: str) -> Path:
    return _session_dir(session_id) / "manifest.json"


def _load_manifest(session_id: str) -> list[dict]:
    path = _manifest_path(session_id)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return []


def _save_manifest(session_id: str, manifest: list[dict]) -> None:
    _manifest_path(session_id).write_text(json.dumps(manifest, indent=2))


def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", name or "upload")
    return cleaned.strip("-") or "upload"


def _parse_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _parse_docx(path: Path) -> str:
    from docx import Document

    doc = Document(path)
    return "\n\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())


def _parse_pdf(path: Path) -> str:
    import pdfplumber

    pages = []
    with pdfplumber.open(path) as pdf:
        for index, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text and text.strip():
                pages.append(f"[Page {index + 1}]\n{text.strip()}")
    return "\n\n".join(pages)


def _parse_pptx(path: Path) -> str:
    from pptx import Presentation

    slides = []
    prs = Presentation(path)
    for index, slide in enumerate(prs.slides):
        slide_text = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                slide_text.append(shape.text.strip())
        if slide_text:
            slides.append(f"[Slide {index + 1}]\n" + "\n".join(slide_text))
    return "\n\n".join(slides)


def parse_uploaded_path(path: Path) -> tuple[str, str]:
    ext = path.suffix.lower()
    if ext == ".txt":
        return _parse_txt(path), "notes"
    if ext == ".docx":
        return _parse_docx(path), "document"
    if ext == ".pdf":
        return _parse_pdf(path), "pitch deck"
    if ext == ".pptx":
        return _parse_pptx(path), "pitch deck"
    return "", "file"


def _chunk_text(text: str, source: str, doc_type: str) -> list[dict]:
    chunks = []
    text = text.strip()
    cursor = 0
    index = 0
    while cursor < len(text):
        chunk = text[cursor: cursor + CHUNK_SIZE].strip()
        if chunk:
            chunks.append(
                {
                    "id": f"{source}:{index}",
                    "source": source,
                    "doc_type": doc_type,
                    "text": chunk,
                }
            )
        index += 1
        cursor += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


async def ingest_upload(session_id: str, upload: UploadFile) -> dict:
    content = await upload.read()
    filename = _sanitize_filename(upload.filename or "upload")
    session_dir = _session_dir(session_id)
    stored_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{filename}"
    stored_path = session_dir / stored_name
    stored_path.write_bytes(content)

    text, doc_type = parse_uploaded_path(stored_path)
    chunks = _chunk_text(text, filename, doc_type)
    chunks_path = session_dir / f"{stored_name}.chunks.json"
    chunks_path.write_text(json.dumps(chunks, indent=2))

    manifest = _load_manifest(session_id)
    entry = {
        "name": filename,
        "stored_name": stored_name,
        "docType": doc_type,
        "chunkCount": len(chunks),
        "chars": len(text),
        "uploadedAt": datetime.now(timezone.utc).isoformat(),
        "chunksFile": chunks_path.name,
    }
    manifest.append(entry)
    _save_manifest(session_id, manifest)
    return entry


def list_active_uploads(session_id: str) -> list[dict]:
    public_fields = ("name", "docType", "chunkCount", "chars", "uploadedAt")
    return [
        {field: entry[field] for field in public_fields if field in entry}
        for entry in _load_manifest(session_id)
    ]


def _tokenize(text: str) -> set[str]:
    return set(TOKEN_PATTERN.findall((text or "").lower()))


def retrieve_upload_context(
    session_id: str,
    query: str,
    top_k: int = 2,
    max_chars: int = 1200,
) -> list[dict]:
    manifest = _load_manifest(session_id)
    if not manifest:
        return []

    query_terms = _tokenize(query)
    candidates = []
    for entry in manifest:
        chunks_file = _session_dir(session_id) / entry["chunksFile"]
        if not chunks_file.exists():
            continue
        try:
            chunks = json.loads(chunks_file.read_text())
        except json.JSONDecodeError:
            continue
        for chunk in chunks:
            text = chunk.get("text", "")
            lower = text.lower()
            chunk_terms = _tokenize(text)
            overlap = len(query_terms & chunk_terms) if query_terms else 0
            phrase_bonus = 1 if any(term in lower for term in query_terms) else 0
            candidates.append(
                {
                    **chunk,
                    "score": overlap + phrase_bonus,
                    "uploadedAt": entry["uploadedAt"],
                }
            )

    candidates.sort(
        key=lambda item: (item["score"], item["uploadedAt"], -len(item["text"])),
        reverse=True,
    )
    selected = []
    total_chars = 0
    for chunk in candidates[: max(top_k * 4, top_k)]:
        snippet = chunk["text"].strip()
        if not snippet:
            continue
        if total_chars + len(snippet) > max_chars and selected:
            break
        selected.append(
            {
                "source": chunk["source"],
                "docType": chunk["doc_type"],
                "text": snippet[: min(len(snippet), 550)],
            }
        )
        total_chars += len(snippet)
        if len(selected) >= top_k:
            break

    if not selected and manifest:
        latest = manifest[-1]
        chunks_file = _session_dir(session_id) / latest["chunksFile"]
        if chunks_file.exists():
            chunks = json.loads(chunks_file.read_text())
            selected = [
                {
                    "source": latest["name"],
                    "docType": latest["docType"],
                    "text": chunk["text"][:550],
                }
                for chunk in chunks[:top_k]
            ]
    return selected
