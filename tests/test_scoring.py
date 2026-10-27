import pytest

from src.core.config import MatchingSettings
from src.data.apify import creators_from_videos
from src.data.schemas import BrandProfile, Creator, CreatorAssessment, Video
from src.services.scoring import build_match, engagement_rate, thai_signal, tier_of


@pytest.mark.parametrize(
    ("followers", "tier"),
    [
        (0, 5),
        (9_999, 5),
        (10_000, 4),
        (499_999, 3),
        (999_999, 2),
        (1_000_000, 1),
        (10**7, 1),
    ],
)
def test_tier_of(followers, tier):
    assert tier_of(followers) == tier


def test_engagement_rate_is_median_and_skips_zero_plays():
    videos = [
        Video(url="a", plays=100, likes=10),
        Video(url="b", plays=100, likes=5, comments=5, shares=10),
        Video(url="c", plays=100, likes=50),
        Video(url="d", plays=0, likes=99),
    ]
    assert engagement_rate(videos) == pytest.approx(0.2)
    assert engagement_rate([]) == 0.0


def test_thai_signal_uses_script_and_location():
    creator = Creator(
        handle="x",
        bio="\u0e01\u0e32\u0e41\u0e1f",
        videos=[Video(url="a", caption="hello", location="TH"), Video(url="b", caption="hello")],
    )
    assert thai_signal(creator) == pytest.approx(2 / 3)


def test_build_match_weights_and_tier_fit():
    brand = BrandProfile(
        brand_name="b",
        industry="i",
        summary="s",
        products=[],
        target_audience="t",
        content_style="c",
        search_queries=[],
        hashtags=[],
        preferred_tiers=[4],
    )
    creator = Creator(handle="x", followers=50_000, videos=[Video(url="a", plays=100, likes=8)])
    assessment = CreatorAssessment(handle="x", relevance=1.0, audience_fit=0.5, reason="r")

    match = build_match(creator, assessment, brand, MatchingSettings())

    assert match.engagement == pytest.approx(1.0)
    assert match.tier_fit == 1.0
    assert match.score == pytest.approx(0.4 * 1 + 0.25 * 0.5 + 0.25 * 1 + 0.1 * 1)


def test_creators_from_videos_groups_and_dedupes():
    item = {
        "authorMeta": {"name": "kol", "fans": 1000},
        "webVideoUrl": "https://www.tiktok.com/@kol/video/1",
        "playCount": 10,
    }
    other = {**item, "webVideoUrl": "https://www.tiktok.com/@kol/video/2"}

    creators = creators_from_videos([item, item, other, {"authorMeta": {}}])

    assert len(creators) == 1
    assert creators[0].url == "https://www.tiktok.com/@kol"
    assert len(creators[0].videos) == 2
