from abc import ABC, abstractmethod

from src.data.schemas import Creator, FacebookPage


class FacebookSource(ABC):
    @abstractmethod
    def fetch_page(self, url: str) -> FacebookPage: ...


class TikTokSource(ABC):
    @abstractmethod
    def search(self, queries: list[str], hashtags: list[str], limit: int) -> list[Creator]:
        """Find videos for keywords and hashtags, grouped by their creator."""

    @abstractmethod
    def profiles(self, handles: list[str], limit: int) -> list[Creator]:
        """Fetch the latest `limit` videos for each handle."""
