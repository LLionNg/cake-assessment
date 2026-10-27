from src.core.config import MatchingSettings
from src.data.base import TikTokSource
from src.data.schemas import BrandProfile, Creator
from src.services.scoring import thai_signal


class CreatorDiscovery:
    """Search TikTok with the brand keywords, shortlist creators, then pull their recent videos."""

    def __init__(self, tiktok: TikTokSource, settings: MatchingSettings):
        self.tiktok = tiktok
        self.settings = settings

    def discover(self, brand: BrandProfile) -> list[Creator]:
        s = self.settings
        found = self.tiktok.search(brand.search_queries, brand.hashtags, s.videos_per_query)
        shortlist = [c for c in found if s.min_followers <= c.followers <= s.max_followers]
        shortlist.sort(key=lambda c: sum(v.plays for v in c.videos), reverse=True)
        shortlist = shortlist[: s.max_candidates]
        if not shortlist:
            return []

        enriched = {
            c.handle: c
            for c in self.tiktok.profiles([c.handle for c in shortlist], s.videos_per_creator)
        }
        creators = [enriched.get(c.handle, c) for c in shortlist]
        return [c for c in creators if thai_signal(c) >= s.min_thai_ratio]
