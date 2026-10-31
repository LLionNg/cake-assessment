import logging

import httpx
import trafilatura

from src.utils.urls import parse_url

log = logging.getLogger(__name__)

MAX_CHARS = 16000
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; KOLMatcher/0.1)"}


def fetch_website_text(url: str | None) -> str:
    if not url:
        return ""
    try:
        response = httpx.get(
            parse_url(url.strip()).geturl(), headers=HEADERS, follow_redirects=True, timeout=15
        )
        response.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("Website fetch failed for %s: %s", url, e)
        return ""
    return (trafilatura.extract(response.text) or "")[:MAX_CHARS]
