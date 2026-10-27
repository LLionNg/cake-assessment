from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

FIXTURES = Path(__file__).parents[2] / "fixtures"

Provider = Literal["openai", "anthropic", "google-vertex"]


class OpenAISettings(BaseModel):
    api_key: str = ""
    model: str = "gpt-5.4-mini"


class AnthropicSettings(BaseModel):
    api_key: str = ""
    model: str = "claude-haiku-5-5"


class VertexSettings(BaseModel):
    credentials_file: str = ""
    project_id: str = ""
    location: str = "global"
    model: str = "gemini-2.5-flash-lite"


class LLMSettings(BaseModel):
    provider: Provider = "anthropic"
    effort: str = "medium"
    max_tokens: int = 16000
    timeout_s: float = 600
    openai: OpenAISettings = OpenAISettings()
    anthropic: AnthropicSettings = AnthropicSettings()
    google_vertex: VertexSettings = VertexSettings()

    @property
    def has_credentials(self) -> bool:
        return bool(
            {
                "openai": self.openai.api_key,
                "anthropic": self.anthropic.api_key,
                "google-vertex": self.google_vertex.credentials_file,
            }[self.provider]
        )

    @property
    def model(self) -> str:
        return {
            "openai": self.openai.model,
            "anthropic": self.anthropic.model,
            "google-vertex": self.google_vertex.model,
        }[self.provider]


class ApifySettings(BaseModel):
    api_token: str = ""
    tiktok_actor: str = "clockworks/tiktok-scraper"
    facebook_actor: str = "apify/facebook-pages-scraper"
    proxy_country: str = "TH"
    max_charge_usd: float = 5.0
    cache_dir: Path = Path(".cache")


class ScraperSettings(BaseModel):
    enabled: bool = False
    headless: bool = True
    timeout_s: float = 30
    delay_s: float = 1.5


class MockSettings(BaseModel):
    enabled: bool = False
    facebook_page: Path = FIXTURES / "facebook_page.json"
    tiktok_creators: Path = FIXTURES / "tiktok_creators.json"


class Weights(BaseModel):
    relevance: float = 0.4
    audience_fit: float = 0.25
    engagement: float = 0.25
    tier_fit: float = 0.1


class MatchingSettings(BaseModel):
    videos_per_query: int = 5
    videos_per_creator: int = 4
    max_candidates: int = 15
    top_n: int = 10
    min_followers: int = 3000
    max_followers: int = 5_000_000
    min_thai_ratio: float = 0.3
    engagement_benchmark: float = 0.08
    assess_batch_size: int = 10
    weights: Weights = Weights()


class Settings(BaseModel):
    log_level: str = "INFO"
    llm: LLMSettings = LLMSettings()
    apify: ApifySettings = ApifySettings()
    scraper: ScraperSettings = ScraperSettings()
    mock: MockSettings = MockSettings()
    matching: MatchingSettings = MatchingSettings()


def load_settings(path: str | Path = "config.yml") -> Settings:
    path = Path(path)
    if not path.exists():
        return Settings()
    return Settings.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
