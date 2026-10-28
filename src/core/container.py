from dataclasses import dataclass

from src.core.config import Settings
from src.data.base import FacebookSource, TikTokSource
from src.data.mock import MockFacebook, MockTikTok
from src.models.base import LLM
from src.models.mock import MockLLM


@dataclass
class Services:
    llm: LLM
    facebook: FacebookSource
    tiktok: TikTokSource
    mode: str


def build_services(settings: Settings) -> Services:
    live = not settings.mock.enabled

    if live and settings.llm.has_credentials:
        from src.models.agent import PydanticAILLM

        llm, llm_mode = PydanticAILLM(settings.llm), settings.llm.provider
    else:
        llm, llm_mode = MockLLM(), "mock"

    if live and settings.scraper.enabled:
        from src.scrapers.facebook import FacebookScraper
        from src.scrapers.tiktok import TikTokScraper

        facebook, tiktok = FacebookScraper(settings.scraper), TikTokScraper(settings.scraper)
        data_mode = "scraper"
    elif live and settings.apify.api_token:
        from src.data.apify import ApifyFacebook, ApifyRunner, ApifyTikTok

        runner = ApifyRunner(settings.apify)
        facebook, tiktok, data_mode = ApifyFacebook(runner), ApifyTikTok(runner), "apify"
    else:
        facebook, tiktok = MockFacebook(settings.mock), MockTikTok(settings.mock)
        data_mode = "mock"

    return Services(llm, facebook, tiktok, mode=f"llm={llm_mode}, data={data_mode}")
