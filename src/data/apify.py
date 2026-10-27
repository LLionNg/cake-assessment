import hashlib
import json
from decimal import Decimal

from apify_client import ApifyClient

from src.core.config import ApifySettings
from src.data.base import FacebookSource, TikTokSource
from src.data.schemas import Creator, FacebookPage, Video


class ApifyRunner:
    def __init__(self, settings: ApifySettings):
        self.settings = settings
        self.client = ApifyClient(settings.api_token)
        settings.cache_dir.mkdir(parents=True, exist_ok=True)

    def run(self, actor: str, run_input: dict) -> list[dict]:
        key = hashlib.sha1(f"{actor}{json.dumps(run_input, sort_keys=True)}".encode()).hexdigest()
        cache = self.settings.cache_dir / f"{key}.json"
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))

        run = self.client.actor(actor).call(
            run_input=run_input,
            max_total_charge_usd=Decimal(str(self.settings.max_charge_usd)),
        )
        if run is None or run.status != "SUCCEEDED":
            raise RuntimeError(f"Apify actor {actor} failed: {run and run.status}")
        items = self.client.dataset(run.default_dataset_id).list_items(clean=True).items
        cache.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        return items


class ApifyFacebook(FacebookSource):
    def __init__(self, runner: ApifyRunner):
        self.runner = runner

    def fetch_page(self, url: str) -> FacebookPage:
        items = self.runner.run(self.runner.settings.facebook_actor, {"startUrls": [{"url": url}]})
        if not items:
            return FacebookPage(url=url)
        item = items[0]
        about = item.get("about_me") or {}
        return FacebookPage(
            url=url,
            name=item.get("title") or "",
            intro=item.get("intro") or "",
            about=about.get("text", "") if isinstance(about, dict) else str(about),
            categories=item.get("categories") or [],
            followers=item.get("followers") or 0,
            website=item.get("website") or "",
        )


class ApifyTikTok(TikTokSource):
    def __init__(self, runner: ApifyRunner):
        self.runner = runner

    def search(self, queries: list[str], hashtags: list[str], limit: int) -> list[Creator]:
        return self._run(
            {
                "searchQueries": queries,
                "hashtags": hashtags,
                "searchSection": "/video",
                "resultsPerPage": limit,
            }
        )

    def profiles(self, handles: list[str], limit: int) -> list[Creator]:
        return self._run({"profiles": handles, "profileSorting": "latest", "resultsPerPage": limit})

    def _run(self, run_input: dict) -> list[Creator]:
        run_input["proxyCountryCode"] = self.runner.settings.proxy_country
        return creators_from_videos(self.runner.run(self.runner.settings.tiktok_actor, run_input))


def creators_from_videos(items: list[dict]) -> list[Creator]:
    creators: dict[str, Creator] = {}
    seen: set[str] = set()
    for item in items:
        author = item.get("authorMeta") or {}
        handle = author.get("name")
        url = item.get("webVideoUrl") or ""
        if not handle or url in seen:
            continue
        seen.add(url)
        creator = creators.setdefault(
            handle,
            Creator(
                handle=handle,
                nickname=author.get("nickName") or "",
                bio=author.get("signature") or "",
                followers=author.get("fans") or 0,
                total_likes=author.get("heart") or 0,
                verified=bool(author.get("verified")),
                avatar=author.get("avatar") or "",
            ),
        )
        creator.videos.append(
            Video(
                url=url,
                caption=item.get("text") or "",
                plays=item.get("playCount") or 0,
                likes=item.get("diggCount") or 0,
                comments=item.get("commentCount") or 0,
                shares=item.get("shareCount") or 0,
                created_at=item.get("createTimeISO") or "",
                location=item.get("locationCreated") or "",
            )
        )
    return list(creators.values())
