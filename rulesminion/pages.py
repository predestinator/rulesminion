"""Fetch public hackathon pages and compress them into an agent-readable digest."""

from __future__ import annotations

import ipaddress
import json
import subprocess
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from rulesminion.timeutil import iso_to_ist_label, unix_to_ist_label

USER_AGENT = "Mozilla/5.0 (compatible; RulesMinion/0.1; local hackathon research agent)"
MAX_HTML_CHARS = 2_000_000
MAX_DIGEST_CHARS = 12_000
PRIORITY_TERMS = (
    "prize",
    "award",
    "pool",
    "deadline",
    "closes",
    "due",
    "eligib",
    "who can",
    "restrict",
    "india",
    "worldwide",
    "global",
    "online",
    "virtual",
    "submit",
    "submission",
    "checklist",
    "require",
    "readme",
    "demo",
    "video",
    "repository",
    "pull request",
    "openminion",
    "usd",
    "ist",
    "utc",
    "est",
    "pst",
)
NUXT_DROP = {"password", "internalContacts", "gtmContainerId"}


@dataclass
class FetchedPage:
    url: str
    final_url: str
    status_code: int
    title: str
    digest: str
    visible_text: str
    json_ld: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def canonical_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Not a full URL: {url}")
    path = parsed.path.rstrip("/") or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}{query}"


def assert_public_http_url(url: str) -> str:
    """Allow public http(s) hostnames; block obvious local/metadata targets.

    This environment's resolver maps public names to 198.18.0.1 (a fake-ip /
    proxy range). Checking resolved addresses would block every real website,
    so hostnames are allowed and only IP literals plus local names are rejected.
    """
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http(s) URLs are allowed")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("URL is missing a host")
    blocked_names = {
        "localhost",
        "metadata.google.internal",
        "metadata",
    }
    if host in blocked_names or host.endswith(".localhost") or host.endswith(".local") or host.endswith(".internal"):
        raise ValueError("Refusing to fetch a local or metadata address")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return url.strip()
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        raise ValueError("Refusing to fetch a private or reserved address")
    return url.strip()


def fetch_page(url: str, *, timeout: float = 30.0) -> FetchedPage:
    safe = assert_public_http_url(url)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        response = client.get(safe)
    html = response.text[:MAX_HTML_CHARS]
    page = parse_page(safe, html, final_url=str(response.url), status_code=response.status_code)
    if response.status_code >= 400:
        page.warnings.append(f"HTTP {response.status_code}")
    if looks_blocked(page):
        fallback = _curl_fetch(safe, timeout=timeout)
        if fallback is not None:
            html2, status2, final2 = fallback
            alt = parse_page(safe, html2, final_url=final2, status_code=status2)
            if not looks_blocked(alt):
                alt.warnings.append("httpx received a bot-check; fetched successfully via curl")
                return alt
    return page


def _curl_fetch(url: str, *, timeout: float) -> tuple[str, int, str] | None:
    """Some hosts challenge httpx but still serve curl. Keep this local and unauthenticated."""
    try:
        completed = subprocess.run(
            [
                "curl",
                "-sS",
                "-L",
                "--max-time",
                str(int(timeout)),
                "-A",
                USER_AGENT,
                "-H",
                "Accept-Language: en-US,en;q=0.9",
                "-w",
                "\n__RM_STATUS__:%{http_code}\n__RM_URL__:%{url_effective}",
                url,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    body = completed.stdout or ""
    status = 0
    final = url
    if "__RM_STATUS__:" in body:
        html, _, trailer = body.rpartition("__RM_STATUS__:")
        parts = trailer.splitlines()
        try:
            status = int(parts[0])
        except (TypeError, ValueError):
            status = 0
        for line in parts[1:]:
            if line.startswith("__RM_URL__:"):
                final = line.split(":", 1)[1]
        body = html
    if not body:
        return None
    return body[:MAX_HTML_CHARS], status or 200, final


def parse_page(
    url: str,
    html: str,
    *,
    final_url: str | None = None,
    status_code: int = 200,
) -> FetchedPage:
    soup = BeautifulSoup(html, "html.parser")
    title = _page_title(soup)
    json_ld = _json_ld(soup)
    structured = _structured_lines(soup, json_ld)
    visible = _visible_text(soup)
    digest = _build_digest(url=final_url or url, title=title, structured=structured, visible=visible)
    return FetchedPage(
        url=url,
        final_url=final_url or url,
        status_code=status_code,
        title=title,
        digest=digest,
        visible_text=visible,
        json_ld=json_ld,
    )


def _page_title(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.string:
        return " ".join(soup.title.string.split())
    heading = soup.find(["h1", "h2"])
    return heading.get_text(" ", strip=True) if heading else ""


def _visible_text(soup: BeautifulSoup) -> str:
    cloned = BeautifulSoup(str(soup), "html.parser")
    for tag in cloned(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = cloned.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def _json_ld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or ""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            found.extend(item for item in data if isinstance(item, dict))
        elif isinstance(data, dict):
            found.append(data)
    return found


def _structured_lines(soup: BeautifulSoup, json_ld: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in json_ld:
        kind = item.get("@type") or "Thing"
        lines.append(f"JSON-LD type: {kind}")
        for key in ("name", "startDate", "endDate", "url", "eventAttendanceMode", "eventStatus"):
            if item.get(key):
                value = str(item[key])
                extra = ""
                if key in {"startDate", "endDate"}:
                    ist = iso_to_ist_label(value)
                    if ist:
                        extra = f"  (IST: {ist})"
                lines.append(f"- {key}: {value}{extra}")
        organizer = item.get("organizer")
        if isinstance(organizer, dict) and organizer.get("name"):
            lines.append(f"- organizer: {organizer['name']}")
        description = item.get("description")
        if isinstance(description, str) and description.strip():
            lines.append("- description: " + " ".join(description.split())[:800])

    nuxt = soup.find("script", id="__NUXT_DATA__")
    if nuxt and nuxt.string:
        lines.extend(_nuxt_lines(nuxt.string))
    return lines


def _nuxt_lines(raw: str) -> list[str]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    blob = _find_hackathon_blob(payload)
    if not blob:
        return []
    data = {k: v for k, v in blob.items() if k not in NUXT_DROP}
    lines = ["DoraHacks embedded hackathon record:"]
    simple_keys = (
        "id",
        "title",
        "venueForm",
        "venueName",
        "hackersCount",
        "buidlsCount",
        "mandatoryGitRepoLink",
        "mandatoryVideoLink",
        "isEnabledSubmissionForm",
        "winnerAnnounced",
        "bonusPrice",
        "bonusToken",
    )
    for key in simple_keys:
        if key in data and data[key] not in (None, "", [], {}):
            lines.append(f"- {key}: {data[key]}")
    for key in ("timelineStart", "timelineEnd", "timelinePreRegister"):
        value = data.get(key)
        if isinstance(value, (int, float)) and value:
            lines.append(f"- {key}: {value} (IST: {unix_to_ist_label(value)})")
    description = data.get("description")
    if isinstance(description, str) and description.strip():
        lines.append("- description excerpt: " + " ".join(description.split())[:1200])
    return lines


def _find_hackathon_blob(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return _find_hackathon_blob(parsed)
    if isinstance(payload, dict):
        if payload.get("schema") == "HACKATHON" and isinstance(payload.get("d"), dict):
            return payload["d"]
        if "timelineEnd" in payload and "title" in payload and "hackersCount" in payload:
            return payload
        for value in payload.values():
            found = _find_hackathon_blob(value)
            if found:
                return found
    if isinstance(payload, list):
        for item in payload:
            found = _find_hackathon_blob(item)
            if found:
                return found
    return None


def _build_digest(*, url: str, title: str, structured: list[str], visible: str) -> str:
    header = [f"# {title or 'Untitled page'}", f"URL: {url}", ""]
    if structured:
        header.append("## Structured metadata (already converted to IST when possible)")
        header.extend(structured)
        header.append("")
    header.append("## Visible page text")
    used = sum(len(line) + 1 for line in header)
    remaining = max(800, MAX_DIGEST_CHARS - used)
    header.append(_prioritize_text(visible, remaining))
    digest = "\n".join(header)
    if len(digest) > MAX_DIGEST_CHARS:
        digest = digest[: MAX_DIGEST_CHARS - 20] + "\n[truncated]"
    return digest


def _prioritize_text(text: str, limit: int) -> str:
    paragraphs = [chunk.strip() for chunk in text.split("\n") if chunk.strip()]
    if not paragraphs:
        return ""

    def score(paragraph: str) -> int:
        lowered = paragraph.lower()
        return sum(term in lowered for term in PRIORITY_TERMS)

    ranked = sorted(enumerate(paragraphs), key=lambda item: (-score(item[1]), item[0]))
    chosen: list[tuple[int, str]] = []
    size = 0
    seen: set[int] = set()
    for index, paragraph in ranked:
        piece = paragraph if len(paragraph) < 1500 else paragraph[:1500]
        extra = len(piece) + 1
        if size + extra > limit and chosen:
            continue
        chosen.append((index, piece))
        seen.add(index)
        size += extra
        if size >= limit:
            break
    if size < limit:
        for index, paragraph in enumerate(paragraphs):
            if index in seen:
                continue
            piece = paragraph if len(paragraph) < 1500 else paragraph[:1500]
            extra = len(piece) + 1
            if size + extra > limit:
                break
            chosen.append((index, piece))
            size += extra
    chosen.sort(key=lambda item: item[0])
    return "\n".join(piece for _, piece in chosen)


def looks_blocked(page: FetchedPage) -> bool:
    """True when the response is a bot-check or interstitial, not the real page."""
    blob = f"{page.title}\n{page.visible_text}".lower()
    markers = (
        "just a moment",
        "human verification",
        "attention required",
        "cf-browser-verification",
        "verify you are human",
    )
    return page.status_code >= 400 or any(marker in blob for marker in markers)
