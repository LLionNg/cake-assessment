from urllib.parse import ParseResult, unquote, urlparse


def parse_url(url: str) -> ParseResult:
    """urlparse that also accepts links pasted without a scheme, such as facebook.com/brand."""
    return urlparse(url if "//" in url else f"https://{url}")


def same_path(current: str, requested: str) -> bool:
    """False when the site redirected, e.g. TikTok sends unknown keyword pages to its home."""
    return _path(current) == _path(requested)


def _path(url: str) -> str:
    return unquote(urlparse(url).path).rstrip("/")
