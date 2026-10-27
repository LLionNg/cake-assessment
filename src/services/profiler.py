from src.core.config import MatchingSettings
from src.data.schemas import BrandProfile, FacebookPage
from src.models.base import LLM
from src.prompts.prompts import BRAND_PROFILE


class BrandProfiler:
    def __init__(self, llm: LLM, settings: MatchingSettings):
        self.llm = llm
        self.settings = settings
        self.system = BRAND_PROFILE.format(
            search_queries=settings.search_queries, hashtags=settings.hashtags
        )

    def profile(self, page: FacebookPage, website_text: str) -> BrandProfile:
        payload = {"facebook": page.model_dump(), "website": website_text}
        brand = self.llm.parse(self.system, payload, BrandProfile)
        # The counts are a hard cap on searches, even if the model writes extra terms.
        brand.search_queries = brand.search_queries[: self.settings.search_queries]
        brand.hashtags = brand.hashtags[: self.settings.hashtags]
        return brand
