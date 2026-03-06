"""Offline VC firm knowledge ingestion and runtime retrieval."""

from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from urllib.parse import urljoin, urlparse
from zipfile import ZipFile

import requests
from bs4 import BeautifulSoup

import rag
from state import ConversationState


VC_INPUT_DIR = Path("knowledge_inbox")
INVESTOR_SHEET = VC_INPUT_DIR / "Investor.xlsx"
PORTFOLIO_SHEET = VC_INPUT_DIR / "Investor Firm.xlsx"
VC_DATA_DIR = Path("data") / "vc_firms"
VC_CACHE_DIR = VC_DATA_DIR / "cache"
VC_MANIFEST = VC_DATA_DIR / "manifest.json"

XLSX_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
USER_AGENT = "Signal/0.2 VC Knowledge Builder"

DISCOVERY_KEYWORDS = (
    "about",
    "team",
    "portfolio",
    "companies",
    "founder",
    "founders",
    "thesis",
    "investment",
    "investing",
    "sector",
    "focus",
)

VC_QUERY_CUES = (
    "vc",
    "venture",
    "investor",
    "investors",
    "fundraise",
    "fundraising",
    "raise",
    "check size",
    "firms",
    "firm",
    "who should we pitch",
    "which investors",
    "which firms",
    "target funds",
    "target investors",
    "thesis",
    "portfolio",
    "term sheet",
    "sequoia",
    "accel",
    "benchmark",
    "greylock",
    "lightspeed",
    "a16z",
    "andreessen",
    "tiger global",
    "nea",
    "y combinator",
    "yc",
    "500 global",
)


def _normalize_text(value: str) -> str:
    return " ".join((value or "").strip().split())


def _normalize_firm_key(name: str) -> str:
    return _normalize_text(name).casefold()


def _normalize_website(url: str) -> str:
    raw = _normalize_text(url)
    if not raw:
        return ""
    if raw.startswith(("http://", "https://")):
        return raw
    return f"https://{raw}"


def _domain(url: str) -> str:
    parsed = urlparse(_normalize_website(url))
    return parsed.netloc.lower().removeprefix("www.")


def _col_letters(cell_ref: str) -> str:
    match = re.match(r"([A-Z]+)\d+", cell_ref or "")
    return match.group(1) if match else ""


def _load_shared_strings(zf: ZipFile) -> list[str]:
    shared_strings: list[str] = []
    with zf.open("xl/sharedStrings.xml") as handle:
        for _, elem in ET.iterparse(handle, events=("end",)):
            if elem.tag == f"{XLSX_NS}si":
                shared_strings.append("".join(node.text or "" for node in elem.iter(f"{XLSX_NS}t")))
                elem.clear()
    return shared_strings


def iter_xlsx_rows(path: Path) -> Iterator[dict[str, str]]:
    """Yield sheet rows as dictionaries keyed by header name."""
    with ZipFile(path) as zf:
        shared_strings = _load_shared_strings(zf)
        with zf.open("xl/worksheets/sheet1.xml") as handle:
            headers: dict[str, str] | None = None
            current_row: dict[str, str] | None = None
            for event, elem in ET.iterparse(handle, events=("start", "end")):
                if event == "start" and elem.tag == f"{XLSX_NS}row":
                    current_row = {}
                    continue

                if event == "end" and elem.tag == f"{XLSX_NS}c" and current_row is not None:
                    ref = elem.attrib.get("r", "")
                    col = _col_letters(ref)
                    value = ""
                    value_tag = elem.find(f"{XLSX_NS}v")
                    if value_tag is not None and value_tag.text is not None:
                        value = value_tag.text
                        if elem.attrib.get("t") == "s":
                            idx = int(value)
                            value = shared_strings[idx] if idx < len(shared_strings) else value
                    inline_string = elem.find(f"{XLSX_NS}is")
                    if inline_string is not None:
                        value = "".join(node.text or "" for node in inline_string.iter(f"{XLSX_NS}t"))
                    current_row[col] = _normalize_text(value)
                    elem.clear()
                    continue

                if event == "end" and elem.tag == f"{XLSX_NS}row":
                    if current_row:
                        if headers is None:
                            headers = {column: name or column for column, name in current_row.items()}
                        else:
                            yield {
                                header: current_row.get(column, "")
                                for column, header in headers.items()
                            }
                    current_row = None
                    elem.clear()


def load_firm_websites() -> dict[str, dict]:
    if not INVESTOR_SHEET.exists():
        raise FileNotFoundError(f"Missing sheet: {INVESTOR_SHEET}")
    firms: dict[str, dict] = {}
    for row in iter_xlsx_rows(INVESTOR_SHEET):
        name = _normalize_text(row.get("FirmName", ""))
        website = _normalize_website(row.get("Website", ""))
        if not name or not website:
            continue
        firms[_normalize_firm_key(name)] = {"name": name, "website": website}
    return firms


def load_portfolio_stats() -> dict[str, dict]:
    if not PORTFOLIO_SHEET.exists():
        raise FileNotFoundError(f"Missing sheet: {PORTFOLIO_SHEET}")
    stats: dict[str, dict] = {}
    seen_companies: dict[str, set[str]] = defaultdict(set)
    seen_domains: dict[str, set[str]] = defaultdict(set)

    for row in iter_xlsx_rows(PORTFOLIO_SHEET):
        firm = _normalize_text(row.get("InvestorsBuyersFirms", ""))
        if not firm:
            continue
        key = _normalize_firm_key(firm)
        entry = stats.setdefault(
            key,
            {
                "name": firm,
                "portfolioCount": 0,
                "portfolioCompanies": [],
                "portfolioDomains": [],
            },
        )
        entry["portfolioCount"] += 1

        company = _normalize_text(row.get("PortfolioCompany", ""))
        if company and company.casefold() not in seen_companies[key] and len(entry["portfolioCompanies"]) < 8:
            seen_companies[key].add(company.casefold())
            entry["portfolioCompanies"].append(company)

        website = _normalize_website(row.get("PortfolioCompanyWebsite", ""))
        domain = _domain(website)
        if domain and domain not in seen_domains[key] and len(entry["portfolioDomains"]) < 8:
            seen_domains[key].add(domain)
            entry["portfolioDomains"].append(domain)

    return stats


def build_ranked_firm_list(
    *,
    max_firms: int = 250,
    firm_filter: str = "",
    include_zero_portfolio: bool = False,
) -> list[dict]:
    websites = load_firm_websites()
    portfolio_stats = load_portfolio_stats()
    filter_text = _normalize_firm_key(firm_filter)

    firms: list[dict] = []
    for key, website_row in websites.items():
        if filter_text and filter_text not in key:
            continue
        portfolio_row = portfolio_stats.get(key, {})
        portfolio_count = int(portfolio_row.get("portfolioCount", 0) or 0)
        if portfolio_count == 0 and not include_zero_portfolio and not filter_text:
            continue
        firms.append(
            {
                "id": key,
                "name": website_row["name"],
                "website": website_row["website"],
                "portfolioCount": portfolio_count,
                "portfolioCompanies": portfolio_row.get("portfolioCompanies", []),
                "portfolioDomains": portfolio_row.get("portfolioDomains", []),
            }
        )

    firms.sort(key=lambda item: (-item["portfolioCount"], item["name"].casefold()))
    if max_firms > 0:
        return firms[:max_firms]
    return firms


def _extract_page_summary(url: str, html: str, *, max_chars: int = 2600) -> tuple[dict, list[tuple[str, str]]]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    description_tag = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    description = _normalize_text(description_tag.get("content", "")) if description_tag else ""

    headings = []
    for tag_name in ("h1", "h2", "h3"):
        for heading in soup.find_all(tag_name):
            text = _normalize_text(heading.get_text(" ", strip=True))
            if text and text not in headings:
                headings.append(text)
            if len(headings) >= 6:
                break
        if len(headings) >= 6:
            break

    body_text = soup.get_text("\n", strip=True)
    lines = [_normalize_text(line) for line in body_text.splitlines()]
    excerpt = "\n".join(line for line in lines if line)[:max_chars]

    candidates: list[tuple[str, str]] = []
    base_domain = _domain(url)
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "")
        label = _normalize_text(anchor.get_text(" ", strip=True))
        absolute = urljoin(url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if _domain(absolute) != base_domain:
            continue
        if any(keyword in absolute.lower() or keyword in label.casefold() for keyword in DISCOVERY_KEYWORDS):
            candidates.append((absolute, label or parsed.path))

    summary = {
        "url": url,
        "title": title,
        "description": description,
        "headings": headings,
        "text": excerpt,
    }
    return summary, candidates


def _page_label(url: str, label: str, index: int) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if label:
        return label[:48]
    if path:
        return path.replace("/", " > ")[:48]
    return "homepage" if index == 0 else f"page {index + 1}"


def crawl_firm_website(
    firm: dict,
    *,
    max_pages: int = 4,
    max_chars_per_page: int = 2600,
    force_refresh: bool = False,
    pause_seconds: float = 0.0,
) -> dict:
    VC_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = VC_CACHE_DIR / f"{firm['id']}.json"
    if cache_path.exists() and not force_refresh:
        return json.loads(cache_path.read_text())

    pages: list[dict] = []
    warnings: list[str] = []
    seen_urls: set[str] = set()

    with requests.Session() as session:
        session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})

        def fetch(url: str) -> tuple[dict | None, list[tuple[str, str]]]:
            try:
                response = session.get(url, timeout=12, allow_redirects=True)
                response.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"{url}: {exc!s}")
                return None, []
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                warnings.append(f"{response.url}: non-html content")
                return None, []
            summary, candidates = _extract_page_summary(str(response.url), response.text, max_chars=max_chars_per_page)
            return summary, candidates

        home_summary, candidates = fetch(firm["website"])
        if home_summary:
            pages.append({**home_summary, "label": _page_label(home_summary["url"], "", 0)})
            seen_urls.add(home_summary["url"])

        for candidate_url, candidate_label in candidates:
            if len(pages) >= max_pages:
                break
            if candidate_url in seen_urls:
                continue
            seen_urls.add(candidate_url)
            if pause_seconds > 0:
                time.sleep(pause_seconds)
            summary, _ = fetch(candidate_url)
            if summary:
                pages.append({**summary, "label": _page_label(summary["url"], candidate_label, len(pages))})

    result = {
        "name": firm["name"],
        "website": firm["website"],
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "pages": pages,
        "warnings": warnings[:6],
    }
    cache_path.write_text(json.dumps(result, indent=2))
    return result


def build_firm_document(firm: dict, crawl_result: dict) -> str:
    lines = [
        f"Firm: {firm['name']}",
        f"Website: {firm['website']}",
        f"Mapped portfolio companies in spreadsheet: {firm['portfolioCount']}",
    ]
    if firm["portfolioCompanies"]:
        lines.append("Sample portfolio companies: " + ", ".join(firm["portfolioCompanies"]))
    if firm["portfolioDomains"]:
        lines.append("Sample portfolio domains: " + ", ".join(firm["portfolioDomains"]))
    if crawl_result.get("warnings"):
        lines.append("Crawl warnings: " + " | ".join(crawl_result["warnings"]))

    for page in crawl_result.get("pages", []):
        lines.append(f"\n[{page['label']}]")
        if page.get("title"):
            lines.append(f"Title: {page['title']}")
        if page.get("description"):
            lines.append(f"Description: {page['description']}")
        if page.get("headings"):
            lines.append("Headings: " + " | ".join(page["headings"]))
        if page.get("text"):
            lines.append(page["text"])

    return "\n".join(lines).strip()


def refresh_vc_firm_cluster(
    *,
    max_firms: int = 250,
    max_pages: int = 4,
    max_chars_per_page: int = 2600,
    force_refresh: bool = False,
    firm_filter: str = "",
    include_zero_portfolio: bool = False,
    pause_seconds: float = 0.0,
) -> dict:
    firms = build_ranked_firm_list(
        max_firms=max_firms,
        firm_filter=firm_filter,
        include_zero_portfolio=include_zero_portfolio,
    )
    documents = []
    crawled = 0
    warnings = 0

    for firm in firms:
        crawl_result = crawl_firm_website(
            firm,
            max_pages=max_pages,
            max_chars_per_page=max_chars_per_page,
            force_refresh=force_refresh,
            pause_seconds=pause_seconds,
        )
        crawled += 1
        warnings += len(crawl_result.get("warnings", []))
        documents.append(
            {
                "id": firm["id"],
                "source": firm["name"],
                "website": firm["website"],
                "portfolio_count": firm["portfolioCount"],
                "doc_type": "vc_firm_profile",
                "date_added": datetime.now(timezone.utc).isoformat(),
                "text": build_firm_document(firm, crawl_result),
            }
        )

    indexed = rag.ingest_vc_firm_documents(documents)
    VC_DATA_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "builtAt": datetime.now(timezone.utc).isoformat(),
        "firmCount": len(firms),
        "indexed": indexed,
        "maxPages": max_pages,
        "maxCharsPerPage": max_chars_per_page,
        "forceRefresh": force_refresh,
        "filter": firm_filter,
        "warnings": warnings,
    }
    VC_MANIFEST.write_text(json.dumps(manifest, indent=2))
    return manifest


def _should_use_vc_context(query: str) -> bool:
    lowered = _normalize_firm_key(query)
    return any(cue in lowered for cue in VC_QUERY_CUES)


def _compact_excerpt(text: str, max_chars: int) -> str:
    lines = []
    total = 0
    for line in text.splitlines():
        cleaned = _normalize_text(line)
        if not cleaned:
            continue
        if cleaned.startswith("["):
            break
        if total + len(cleaned) + 1 > max_chars:
            break
        lines.append(cleaned)
        total += len(cleaned) + 1
    if not lines:
        return _normalize_text(text)[:max_chars]
    return "\n".join(lines)


def retrieve_vc_firm_context(
    state: ConversationState,
    query: str,
    *,
    top_k: int = 2,
    max_chars: int = 760,
) -> dict:
    if not _should_use_vc_context(query):
        return {"text": "", "sources": [], "promptChars": 0}

    search_query = "\n".join(
        part
        for part in (
            query,
            f"Sector: {state.sector}" if state.sector and state.sector != "unknown" else "",
            f"Stage: {state.stage}" if state.stage and state.stage != "unknown" else "",
        )
        if part
    )
    hits = rag.retrieve_vc_firm_documents(search_query, top_k=top_k)
    if not hits:
        return {"text": "", "sources": [], "promptChars": 0}

    parts = []
    sources = []
    total = 0
    for hit in hits:
        excerpt = _compact_excerpt(hit["text"], 340)
        part = f"[{hit['source']}]\n{excerpt}"
        if parts and total + len(part) + 2 > max_chars:
            continue
        parts.append(part)
        total += len(part) + 2
        sources.append(
            {
                "source": hit["source"],
                "title": "VC firm profile",
                "url": hit.get("website", ""),
            }
        )

    if not parts:
        return {"text": "", "sources": [], "promptChars": 0}

    text = "VC firm context:\n" + "\n\n".join(parts)
    return {"text": text, "sources": sources, "promptChars": len(text)}
