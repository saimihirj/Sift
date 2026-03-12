"""Upload parsing and lightweight lexical retrieval."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

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


def _artifact_dir(session_id: str, stored_name: str) -> Path:
    path = _session_dir(session_id) / f"{stored_name}.artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path


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


def _slide_summary(text: str, limit: int = 240) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _render_pdf_page_images(path: Path, output_dir: Path) -> list[str]:
    renderer = shutil.which("pdftoppm")
    if not renderer:
        return []
    prefix = output_dir / "page"
    try:
        subprocess.run(
            [renderer, "-png", "-r", "110", str(path), str(prefix)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return []
    pages = sorted(output_dir.glob("page-*.png"), key=lambda item: int(re.search(r"-(\d+)\.png$", item.name).group(1)) if re.search(r"-(\d+)\.png$", item.name) else 0)
    return [str(page) for page in pages]


def _build_pdf_deck_artifact(path: Path, session_id: str, stored_name: str) -> dict:
    import pdfplumber

    asset_dir = _artifact_dir(session_id, stored_name)
    image_paths = _render_pdf_page_images(path, asset_dir)
    slides = []
    with pdfplumber.open(path) as pdf:
        for index, page in enumerate(pdf.pages):
            text = (page.extract_text() or "").strip()
            image_path = image_paths[index] if index < len(image_paths) else ""
            slides.append(
                {
                    "index": index + 1,
                    "label": f"Page {index + 1}",
                    "extractedText": text,
                    "summary": _slide_summary(text or f"Page {index + 1}"),
                    "imagePath": image_path,
                }
            )
    limitations = []
    if not any(slide.get("imagePath") for slide in slides):
        limitations.append("Page images were not rendered in this environment, so review falls back to extracted text.")
    return {
        "artifactType": "deck",
        "format": "pdf",
        "storedName": stored_name,
        "slideCount": len(slides),
        "hasRenderableSlides": any(slide.get("imagePath") for slide in slides),
        "limitations": limitations,
        "slides": slides,
    }


def _build_pptx_deck_artifact(path: Path, stored_name: str) -> dict:
    from pptx import Presentation

    prs = Presentation(path)
    slides = []
    for index, slide in enumerate(prs.slides):
        slide_text = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                slide_text.append(shape.text.strip())
        text = "\n".join(slide_text).strip()
        slides.append(
            {
                "index": index + 1,
                "label": f"Slide {index + 1}",
                "extractedText": text,
                "summary": _slide_summary(text or f"Slide {index + 1}"),
                "imagePath": "",
            }
        )
    return {
        "artifactType": "deck",
        "format": "pptx",
        "storedName": stored_name,
        "slideCount": len(slides),
        "hasRenderableSlides": False,
        "limitations": [
            "This environment extracted slide text from the PPTX but did not render slide images, so visual design claims should be treated as unverified.",
        ],
        "slides": slides,
    }


def _build_upload_artifact(path: Path, session_id: str, stored_name: str, doc_type: str) -> dict | None:
    ext = path.suffix.lower()
    if doc_type != "pitch deck":
        return None
    if ext == ".pdf":
        return _build_pdf_deck_artifact(path, session_id, stored_name)
    if ext == ".pptx":
        return _build_pptx_deck_artifact(path, stored_name)
    return None


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
    artifact = _build_upload_artifact(stored_path, session_id, stored_name, doc_type)
    artifact_path = None
    if artifact is not None:
        artifact_path = session_dir / f"{stored_name}.artifact.json"
        artifact_path.write_text(json.dumps(artifact, indent=2))

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
    if artifact_path is not None:
        entry["artifactFile"] = artifact_path.name
        entry["slideCount"] = int(artifact.get("slideCount", 0) or 0)
        entry["hasRenderableSlides"] = bool(artifact.get("hasRenderableSlides", False))
    manifest.append(entry)
    _save_manifest(session_id, manifest)
    return entry


def list_active_uploads(session_id: str) -> list[dict]:
    public_fields = ("name", "docType", "chunkCount", "chars", "uploadedAt", "slideCount", "hasRenderableSlides")
    return [
        {field: entry[field] for field in public_fields if field in entry}
        for entry in _load_manifest(session_id)
    ]


def load_deck_artifact(session_id: str, *, latest_only: bool = True) -> dict | None:
    manifest = _load_manifest(session_id)
    if not manifest:
        return None
    candidates = [entry for entry in manifest if entry.get("docType") == "pitch deck" and entry.get("artifactFile")]
    if not candidates:
        return None
    entries = [candidates[-1]] if latest_only else list(reversed(candidates))
    for entry in entries:
        path = _session_dir(session_id) / entry["artifactFile"]
        if not path.exists():
            continue
        try:
            artifact = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        artifact["name"] = entry.get("name", artifact.get("storedName", "deck"))
        artifact["uploadedAt"] = entry.get("uploadedAt", "")
        return artifact
    return None


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
