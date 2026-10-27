import json
import time
from datetime import UTC, datetime

from src.core.config import ScraperSettings
from src.data.base import TikTokSource
from src.data.schemas import Creator, Video
from src.scrapers.browser import Browser
from src.utils.urls import parse_url

BASE = "https://www.tiktok.com"
DISCOVER_API = "/api/seo/kap/video_list"
EMBED_STATE = "__FRONTITY_CONNECT_STATE__"
EMBED_RETRIES = 2
OVERLOADED = "overload-protect"


def handle_of(value: str) -> str | None:
    """@name, name, or any tiktok.com/@name/... URL. None for short links like vm.tiktok.com."""
    value = value.strip()
    if "tiktok.com" not in value and "/" not in value:
        return value.lstrip("@") or None
    path = parse_url(value).path
    part = next((p for p in path.split("/") if p.startswith("@")), None)
    return part[1:] if part else None


def web_video(item: dict) -> Video:
    stats = item.get("stats") or {}

    def count(key: str) -> int:
        return int(stats.get(key) or 0)

    created = item.get("createTime")
    return Video(
        url=f"{BASE}/@{item['author']['uniqueId']}/video/{item['id']}",
        caption=item.get("desc") or "",
        plays=count("playCount"),
        likes=count("diggCount"),
        comments=count("commentCount"),
        shares=count("shareCount"),
        created_at=datetime.fromtimestamp(int(created), UTC).isoformat() if created else "",
        location=item.get("locationCreated") or "",
    )


def creators_from_items(items: list[dict]) -> list[Creator]:
    """Group TikTok web items (discover pages, video pages) by author."""
    creators: dict[str, Creator] = {}
    for item in items:
        author = item.get("author") or {}
        handle = author.get("uniqueId")
        if not handle or not item.get("id"):
            continue
        stats = item.get("authorStats") or {}
        creator = creators.setdefault(
            handle,
            Creator(
                handle=handle,
                nickname=author.get("nickname") or "",
                bio=author.get("signature") or "",
                followers=int(stats.get("followerCount") or 0),
                total_likes=int(stats.get("heartCount") or stats.get("heart") or 0),
                verified=bool(author.get("verified")),
                avatar=author.get("avatarThumb") or "",
            ),
        )
        video = web_video(item)
        if all(v.url != video.url for v in creator.videos):
            creator.videos.append(video)
    return list(creators.values())


def creator_from_embed(data: dict, limit: int) -> Creator:
    """Profile embed: bio, stats and recent videos with views but no likes."""
    user = data["userInfo"]
    handle = user["uniqueId"]
    return Creator(
        handle=handle,
        nickname=user.get("nickname") or "",
        bio=user.get("signature") or "",
        followers=int(user.get("followerCount") or 0),
        total_likes=int(user.get("heartCount") or 0),
        verified=bool(user.get("verified")),
        avatar=user.get("avatarThumbUrl") or "",
        videos=[
            Video(
                url=f"{BASE}/@{handle}/video/{v['id']}",
                caption=v.get("desc") or "",
                plays=int(v.get("playCount") or 0),
                likes=None,
            )
            for v in (data.get("videoList") or [])
            if not v.get("privateItem")
        ][:limit],
    )


class TikTokScraper(TikTokSource):
    def __init__(self, settings: ScraperSettings):
        self.settings = settings
        self.found: dict[str, Creator] = {}

    def search(self, queries: list[str], hashtags: list[str], limit: int) -> list[Creator]:
        creators = self._discover(queries + hashtags, limit)
        self.found = {c.handle: c for c in creators}
        return creators

    def profiles(self, handles: list[str], limit: int) -> list[Creator]:
        creators = self._embeds(handles, limit)
        for creator in creators:
            known = self.found.get(creator.handle)
            if known:
                urls = {v.url for v in known.videos}
                creator.videos = known.videos + [v for v in creator.videos if v.url not in urls]
        return creators

    def _discover(self, keywords: list[str], limit: int) -> list[Creator]:
        items: list[dict] = []
        with Browser(self.settings, locale="th-TH") as browser:
            for keyword in dict.fromkeys(k.strip() for k in keywords if k.strip()):
                data = browser.open(f"{BASE}/discover/{keyword.replace(' ', '-')}", DISCOVER_API)
                items += ((data or {}).get("videoList") or [])[:limit]
        return creators_from_items(items)

    def _embeds(self, handles: list[str], limit: int) -> list[Creator]:
        creators = []
        with Browser(self.settings, locale="th-TH") as browser:
            for value in handles:
                handle = handle_of(value) or self._resolve(browser, value)
                if not handle:
                    continue
                state = self._embed_state(browser, handle)
                pages = (state or {}).get("source", {}).get("data", {})
                data = next((v for k, v in pages.items() if k.startswith("/embed/@")), None)
                if data and data.get("userInfo"):
                    creators.append(creator_from_embed(data, limit))
        return creators

    def video(self, url: str) -> Creator | None:
        """One video with full stats, returned as its author with that single video."""
        with Browser(self.settings, locale="th-TH") as browser:
            browser.open(url)
            state = self._json(browser, "__UNIVERSAL_DATA_FOR_REHYDRATION__") or {}
        detail = state.get("__DEFAULT_SCOPE__", {}).get("webapp.video-detail", {})
        item = detail.get("itemInfo", {}).get("itemStruct")
        creators = creators_from_items([item] if item else [])
        return creators[0] if creators else None

    def _embed_state(self, browser: Browser, handle: str) -> dict | None:
        """TikTok rate limits embeds with an "overload-protect" page, so back off and retry."""
        for attempt in range(EMBED_RETRIES + 1):
            browser.open(f"{BASE}/embed/@{handle}")
            browser.wait_for_any(f"#{EMBED_STATE}", texts=(OVERLOADED,), timeout_s=3)
            state = self._json(browser, EMBED_STATE)
            if state:
                return state
            time.sleep(self.settings.delay_s * 2 ** (attempt + 1))
        return None

    @staticmethod
    def _resolve(browser: Browser, url: str) -> str | None:
        browser.open(url)
        return handle_of(browser.page.url)

    @staticmethod
    def _json(browser: Browser, script_id: str) -> dict | None:
        script = browser.page.locator(f"#{script_id}")
        if not script.count():
            return None
        return json.loads(script.text_content() or "null")
