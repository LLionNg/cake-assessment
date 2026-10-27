from src.data.schemas import BrandProfile, FacebookPage
from src.models.base import LLM
from src.prompts.prompts import BRAND_PROFILE


class BrandProfiler:
    def __init__(self, llm: LLM):
        self.llm = llm

    def profile(self, page: FacebookPage, website_text: str) -> BrandProfile:
        payload = {"facebook": page.model_dump(), "website": website_text}
        return self.llm.parse(BRAND_PROFILE, payload, BrandProfile)
