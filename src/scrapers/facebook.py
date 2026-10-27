import re
from urllib.parse import parse_qs, urlparse

from src.core.config import ScraperSettings
from src.data.base import FacebookSource
from src.data.schemas import FacebookPage
from src.scrapers.browser import Browser, ScraperError
from src.utils.urls import parse_url

BASE = "https://www.facebook.com"
HOSTS = ("facebook.com", "fb.com", "fb.me", "fb.watch")
POST_PARTS = {"posts", "videos", "photos", "photo", "photo.php", "reel", "watch", "share"}
POST_PAGES = {"permalink.php", "story.php"}
NOT_PAGES = POST_PARTS | POST_PAGES | {"groups", "events", "hashtag", "login"}
SOCIAL = (
    "facebook.com",
    "fb.com",
    "instagram.com",
    "tiktok.com",
    "youtube.com",
    "line.me",
    "x.com",
)
STATS = re.compile(r"([\d,]+) (?:followers|likes)")
SHORT_COUNT = re.compile(r"([\d.]+)([KM]?) followers")
POST_MESSAGE = "[data-ad-preview='message'], [data-ad-comet-preview='message']"
WEBSITE = re.compile(
    r"(?<![@\w.])(?:https?://)?(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}(?:/\S*)?", re.I
)
CATEGORY = re.compile(r"^Page\s*\u00b7\s*(.+)$", re.M)


def _parse(url: str):
    parsed = parse_url(url)
    host = parsed.netloc.lower().split(":")[0]
    if not any(host == h or host.endswith("." + h) for h in HOSTS):
        raise ScraperError(f"Not a Facebook URL: {url}")
    return host, [p for p in parsed.path.split("/") if p], parse_qs(parsed.query)


def page_url(url: str) -> str | None:
    host, parts, query = _parse(url)
    if not parts or host in ("fb.me", "fb.watch"):
        return None
    first = parts[0]
    if first in ("profile.php", *POST_PAGES) and query.get("id"):
        return f"{BASE}/profile.php?id={query['id'][0]}"
    if first in ("pages", "people") and len(parts) >= 2:
        return f"{BASE}/profile.php?id={parts[-1]}" if parts[-1].isdigit() else f"{BASE}/{parts[1]}"
    if first == "pg" and len(parts) >= 2:
        return f"{BASE}/{parts[1]}"
    if first in NOT_PAGES or first == "profile.php":
        return None
    return f"{BASE}/{first}"


def is_post(url: str) -> bool:
    _, parts, query = _parse(url)
    return bool(
        POST_PARTS & set(parts) or (parts and parts[0] in POST_PAGES) or "story_fbid" in query
    )


def parse_count(text: str) -> int:
    match = SHORT_COUNT.search(text)
    if not match:
        return 0
    number, unit = match.groups()
    return int(float(number) * {"K": 1_000, "M": 1_000_000}.get(unit, 1))


def parse_page(url: str, meta: dict[str, str], body: str, links: list[str]) -> FacebookPage:
    title = meta.get("og:title", "")
    if not title:
        raise ScraperError(f"Facebook returned no page data for {url} (login wall or removed page)")
    description = meta.get("og:description") or meta.get("description") or ""
    stats = STATS.search(description)
    if stats:
        rest = description[stats.end() :]
        intro = rest[rest.find(". ") + 2 :] if ". " in rest else ""
        followers = int(stats.group(1).replace(",", ""))
    else:
        intro, followers = description, parse_count(body)

    lines = [line.strip() for line in body.splitlines() if line.strip()]
    about = ""
    if "Intro" in lines:
        start = lines.index("Intro") + 1
        end = next((i for i in range(start, len(lines)) if CATEGORY.match(lines[i])), start)
        about = "\n".join(lines[start:end])

    category = CATEGORY.search(body)
    found = links + WEBSITE.findall(f"{intro} {about}")
    website = next((w for w in found if not any(s in w for s in SOCIAL)), "")
    if website and "//" not in website:
        website = f"https://{website}"
    return FacebookPage(
        url=url,
        name=title.split(" | ")[0].strip(),
        intro=intro.strip(),
        about=about,
        categories=[c.strip() for c in category.group(1).split(",")] if category else [],
        followers=followers,
        website=website,
    )


class FacebookScraper(FacebookSource):
    def __init__(self, settings: ScraperSettings):
        self.settings = settings

    def fetch_page(self, url: str) -> FacebookPage:
        with Browser(self.settings) as browser:
            target, posts = page_url(url), []
            if target is None or is_post(url):
                browser.open(url)
                final = browser.page.url
                if is_post(url) or is_post(final):
                    posts = [self._post_text(browser)]
                target = target or page_url(final)
                if target is None:
                    raise ScraperError(f"Could not find the Facebook page behind {url}")

            browser.open(target)
            # Logged out, Facebook sometimes shows "This page isn't available" instead of the
            # Intro block. The meta tags are still there, so stop waiting as soon as it appears.
            browser.wait_for_any(texts=("Intro", "isn't available"))
            page = parse_page(
                target, browser.meta(), browser.page.inner_text("body"), self._links(browser)
            )
        page.posts = [p for p in posts if p]
        return page

    @staticmethod
    def _post_text(browser: Browser) -> str:
        if browser.wait_for(POST_MESSAGE):
            return browser.page.locator(POST_MESSAGE).first.inner_text().strip()
        return browser.meta().get("og:description", "")

    @staticmethod
    def _links(browser: Browser) -> list[str]:
        hrefs = browser.page.eval_on_selector_all(
            "a[href*='l.facebook.com/l.php']", "els => els.map(e => e.href)"
        )
        return [parse_qs(urlparse(h).query).get("u", [""])[0] for h in hrefs]
