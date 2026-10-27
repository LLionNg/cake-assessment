import pytest

from src.core.config import ScraperSettings
from src.data.schemas import Creator, Video
from src.scrapers.browser import ScraperError
from src.scrapers.facebook import is_post, page_url, parse_page
from src.scrapers.tiktok import (
    TikTokScraper,
    creator_from_embed,
    creators_from_items,
    handle_of,
)
from src.services.scoring import engagement_rate
from src.utils.urls import parse_url, same_path

FB = "https://www.facebook.com"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.facebook.com/akhaamacoffee", f"{FB}/akhaamacoffee"),
        ("m.facebook.com/akhaamacoffee/about/?ref=x", f"{FB}/akhaamacoffee"),
        ("https://web.facebook.com/akhaamacoffee/posts/123", f"{FB}/akhaamacoffee"),
        ("https://www.facebook.com/profile.php?id=111", f"{FB}/profile.php?id=111"),
        (
            "https://www.facebook.com/permalink.php?story_fbid=pfbid0&id=222",
            f"{FB}/profile.php?id=222",
        ),
        ("https://www.facebook.com/pages/Some-Brand/333", f"{FB}/profile.php?id=333"),
        ("https://www.facebook.com/people/Some-Name/444/", f"{FB}/profile.php?id=444"),
        ("https://www.facebook.com/share/p/abc/", None),
        ("https://fb.me/somebrand", None),
    ],
)
def test_page_url(url, expected):
    assert page_url(url) == expected


def test_page_url_rejects_other_sites():
    with pytest.raises(ScraperError):
        page_url("https://www.instagram.com/somebrand")


def test_is_post():
    assert is_post("https://www.facebook.com/brand/posts/123")
    assert is_post("https://www.facebook.com/permalink.php?story_fbid=1&id=2")
    assert is_post("https://www.facebook.com/reel/123")
    assert not is_post("https://www.facebook.com/brand")


def test_parse_page():
    meta = {
        "og:title": "Some Cafe | Chiang Mai",
        "og:description": "Some Cafe. 48,834 followers - 26 talking about this. Slow bar",
    }
    body = "Log in\nIntro\nSlow bar and roastery\nsomecafe.co.th\nPage \u00b7 Coffee shop\nPhotos"

    page = parse_page(f"{FB}/somecafe", meta, body, [])

    assert page.name == "Some Cafe"
    assert page.followers == 48834
    assert page.intro == "Slow bar"
    assert page.about == "Slow bar and roastery\nsomecafe.co.th"
    assert page.categories == ["Coffee shop"]
    assert page.website == "https://somecafe.co.th"


def test_parse_page_without_meta_is_an_error():
    with pytest.raises(ScraperError):
        parse_page(f"{FB}/x", {}, "Log in", [])


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("@kol.name", "kol.name"),
        ("kol_name", "kol_name"),
        ("https://www.tiktok.com/@kol/video/123", "kol"),
        ("m.tiktok.com/@kol?lang=th", "kol"),
        ("https://www.tiktok.com/embed/@kol", "kol"),
        ("https://vt.tiktok.com/ZS123/", None),
    ],
)
def test_handle_of(value, expected):
    assert handle_of(value) == expected


def item(video_id, handle="kol", plays=100, likes=10):
    return {
        "id": video_id,
        "desc": "caption",
        "createTime": 1700000000,
        "locationCreated": "TH",
        "author": {"uniqueId": handle, "nickname": "K", "signature": "bio"},
        "authorStats": {"followerCount": 5000, "heartCount": 9000},
        "stats": {"playCount": plays, "diggCount": likes, "commentCount": 0, "shareCount": "5"},
    }


def test_creators_from_items_groups_and_dedupes():
    creators = creators_from_items([item("1"), item("1"), item("2"), {"author": {}}])

    assert len(creators) == 1
    assert creators[0].followers == 5000
    assert [v.url for v in creators[0].videos] == [
        "https://www.tiktok.com/@kol/video/1",
        "https://www.tiktok.com/@kol/video/2",
    ]
    assert creators[0].videos[0].shares == 5


def test_creator_from_embed_has_no_engagement():
    data = {
        "userInfo": {"uniqueId": "kol", "followerCount": 7000, "heartCount": 1, "signature": "b"},
        "videoList": [
            {"id": "1", "desc": "a", "playCount": 300},
            {"id": "2", "privateItem": True},
            {"id": "3", "playCount": 200},
        ],
    }

    creator = creator_from_embed(data, limit=5)

    assert creator.followers == 7000
    assert [v.plays for v in creator.videos] == [300, 200]
    assert all(v.likes is None for v in creator.videos)
    assert engagement_rate(creator.videos) == 0.0


def test_tiktok_scraper_keeps_search_engagement(monkeypatch):
    scraper = TikTokScraper(ScraperSettings())
    embed = [
        Video(url="https://www.tiktok.com/@kol/video/1", plays=100, likes=None),
        Video(url="https://www.tiktok.com/@kol/video/9", plays=900, likes=None),
    ]
    monkeypatch.setattr(
        scraper, "_discover", lambda k, n: creators_from_items([item("1", likes=20)])
    )
    monkeypatch.setattr(
        scraper, "_embeds", lambda h, n: [Creator(handle="kol", bio="new", videos=embed)]
    )

    scraper.search(["q"], [], 5)
    creator = scraper.profiles(["kol"], 5)[0]

    assert creator.bio == "new"
    assert [v.plays for v in creator.videos] == [100, 900]
    assert engagement_rate(creator.videos) == pytest.approx(0.25)


@pytest.mark.parametrize(
    ("current", "requested", "same"),
    [
        (
            "https://www.tiktok.com/discover/caf%C3%A9-cnx",
            "https://www.tiktok.com/discover/caf\u00e9-cnx",
            True,
        ),
        ("https://www.tiktok.com/discover/coffee/", "https://www.tiktok.com/discover/coffee", True),
        ("https://www.tiktok.com/", "https://www.tiktok.com/discover/zzqq-phrase", False),
    ],
)
def test_same_path_spots_redirects(current, requested, same):
    assert same_path(current, requested) is same


def test_parse_url_accepts_links_without_scheme():
    assert parse_url("facebook.com/brand/about").netloc == "facebook.com"
    assert parse_url("https://m.facebook.com/brand").path == "/brand"
