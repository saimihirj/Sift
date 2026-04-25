"""Single-page website fetching for evaluator sessions."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


def normalize_website_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    if raw.startswith(("http://", "https://")):
        return raw
    return f"https://{raw}"


async def fetch_website_context(url: str, max_chars: int = 3200) -> dict:
    normalized = normalize_website_url(url)
    if not normalized:
        return {"ok": False, "url": "", "warning": "No website URL provided."}

    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"ok": False, "url": normalized, "warning": "Website URL is not valid."}

    timeout = httpx.Timeout(12.0, connect=4.0, read=12.0)
    headers = {
        "User-Agent": "Sift/0.2 (founder evaluator)",
        "Accept": "text/html,application/xhtml+xml",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
            response = await client.get(normalized)
            response.raise_for_status()
    except Exception as exc:
        return {"ok": False, "url": normalized, "warning": f"Website could not be fetched: {exc!s}"}

    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        return {"ok": False, "url": normalized, "warning": "Website did not return HTML content."}

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    description_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    description = (description_tag.get("content", "") if description_tag else "").strip()

    headings = []
    for tag_name in ("h1", "h2", "h3"):
        for heading in soup.find_all(tag_name):
            text = heading.get_text(" ", strip=True)
            if text and text not in headings:
                headings.append(text)
            if len(headings) >= 8:
                break
        if len(headings) >= 8:
            break

    body_text = soup.get_text("\n", strip=True)
    body_text = "\n".join(line.strip() for line in body_text.splitlines() if line.strip())
    excerpt = body_text[:max_chars]

    summary_parts = []
    if title:
        summary_parts.append(f"Title: {title}")
    if description:
        summary_parts.append(f"Description: {description}")
    if headings:
        summary_parts.append("Headings:\n" + "\n".join(f"- {item}" for item in headings))
    if excerpt:
        summary_parts.append("Visible copy:\n" + excerpt)

    return {
        "ok": True,
        "url": normalized,
        "title": title,
        "description": description,
        "headings": headings,
        "text": "\n\n".join(summary_parts),
        "warning": "",
    }
