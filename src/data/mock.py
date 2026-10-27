import json
from pathlib import Path

from src.core.config import MockSettings
from src.data.base import FacebookSource, TikTokSource
from src.data.schemas import Creator, FacebookPage


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class MockFacebook(FacebookSource):
    def __init__(self, settings: MockSettings):
        self.page = _load(settings.facebook_page)

    def fetch_page(self, url: str) -> FacebookPage:
        return FacebookPage.model_validate({**self.page, "url": url})


class MockTikTok(TikTokSource):
    def __init__(self, settings: MockSettings):
        self.creators = [Creator.model_validate(c) for c in _load(settings.tiktok_creators)]

    def search(self, queries: list[str], hashtags: list[str], limit: int) -> list[Creator]:
        return [c.model_copy(update={"videos": c.videos[:3]}) for c in self.creators]

    def profiles(self, handles: list[str], limit: int) -> list[Creator]:
        wanted = set(handles)
        return [
            c.model_copy(update={"videos": c.videos[:limit]})
            for c in self.creators
            if c.handle in wanted
        ]
