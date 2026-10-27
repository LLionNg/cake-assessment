import pytest

from src.core.config import MatchingSettings, Settings, load_settings
from src.core.container import build_services
from src.data.schemas import BrandProfile, FacebookPage
from src.services.matcher import KOLMatcher
from src.services.profiler import BrandProfiler


def test_mock_pipeline_ranks_relevant_thai_creators():
    report = KOLMatcher(Settings()).run("https://www.facebook.com/example", top_n=5)

    assert report.mode == "llm=mock, data=mock"
    handles = [m.creator.handle for m in report.matches]
    assert len(handles) == 5
    assert all(m.creator.url.startswith("https://www.tiktok.com/@") for m in report.matches)
    assert handles[0] in {"mock_doi_coffee_lover", "mock_slow_bar_bkk", "mock_home_barista_th"}
    assert "mock_seoul_coffee_en" not in handles
    assert "mock_tiny_brew" not in handles
    scores = [m.score for m in report.matches]
    assert scores == sorted(scores, reverse=True)


def test_mock_enabled_overrides_api_keys():
    keys = {"llm": {"anthropic": {"api_key": "k"}}, "apify": {"api_token": "t"}}
    settings = Settings.model_validate({**keys, "mock": {"enabled": True}})
    assert build_services(settings).mode == "llm=mock, data=mock"


@pytest.mark.parametrize(
    ("provider", "credentials"),
    [
        ("openai", {"openai": {"api_key": "k"}}),
        ("anthropic", {"anthropic": {"api_key": "k"}}),
    ],
)
def test_llm_uses_the_chosen_provider(provider, credentials):
    settings = Settings.model_validate({"llm": {"provider": provider, **credentials}})
    assert build_services(settings).mode == f"llm={provider}, data=mock"


def test_llm_without_credentials_for_chosen_provider_is_mock():
    llm = {"provider": "openai", "anthropic": {"api_key": "k"}}
    settings = Settings.model_validate({"llm": llm})
    assert build_services(settings).mode == "llm=mock, data=mock"


def test_config_example_fixture_paths_exist():
    mock = load_settings("config.example.yml").mock
    assert mock.facebook_page.is_file()
    assert mock.tiktok_creators.is_file()


def test_config_example_has_no_credentials():
    llm = load_settings("config.example.yml").llm
    assert llm.openai.api_key == llm.anthropic.api_key == llm.google_vertex.credentials_file == ""
    assert load_settings("config.example.yml").apify.api_token == ""


def test_scraper_never_builds_apify(monkeypatch):
    import src.data.apify as apify

    def fail(*args, **kwargs):
        raise AssertionError("Apify must not be used when the scraper is on")

    monkeypatch.setattr(apify, "ApifyRunner", fail)
    settings = Settings.model_validate({"apify": {"api_token": "t"}, "scraper": {"enabled": True}})
    assert build_services(settings).mode == "llm=mock, data=scraper"


class EchoLLM:
    def parse(self, system, payload, schema):
        self.system = system
        terms = [f"t{i}" for i in range(15)]
        return BrandProfile(
            brand_name="b",
            industry="i",
            summary="s",
            products=[],
            target_audience="a",
            content_style="c",
            search_queries=terms,
            hashtags=terms,
            preferred_tiers=[4],
        )


def test_profiler_uses_and_caps_configured_counts():
    llm = EchoLLM()
    settings = MatchingSettings(search_queries=3, hashtags=2)

    brand = BrandProfiler(llm, settings).profile(FacebookPage(url="u"), "")

    assert "- search_queries: 3 short" in llm.system
    assert "- hashtags: 2 popular" in llm.system
    assert len(brand.search_queries) == 3
    assert len(brand.hashtags) == 2
