from statistics import median

from src.core.config import MatchingSettings
from src.data.schemas import BrandProfile, Creator, CreatorAssessment, Match, Metrics, Tier, Video
from src.utils.text import has_thai

TIER_LIMITS: list[tuple[int, Tier]] = [
    (10_000, 5),
    (100_000, 4),
    (500_000, 3),
    (1_000_000, 2),
]


def tier_of(followers: int) -> Tier:
    """Tier 1 is the largest reach (1M+ followers), tier 5 the smallest (under 10k)."""
    return next((tier for limit, tier in TIER_LIMITS if followers < limit), 1)


def engagement_rate(videos: list[Video]) -> float:
    rates = [
        (v.likes + v.comments + v.shares) / v.plays
        for v in videos
        if v.plays > 0 and v.likes is not None
    ]
    return median(rates) if rates else 0.0


def thai_signal(creator: Creator) -> float:
    """Share of bio and videos that show a Thai signal: Thai script or a TH upload location."""
    signals = [has_thai(creator.bio)] if creator.bio.strip() else []
    signals += [has_thai(v.caption) or v.location.upper() == "TH" for v in creator.videos]
    return sum(signals) / len(signals) if signals else 0.0


def metrics_of(creator: Creator) -> Metrics:
    views = [v.plays for v in creator.videos]
    return Metrics(
        engagement_rate=engagement_rate(creator.videos),
        median_views=int(median(views)) if views else 0,
        thai_ratio=thai_signal(creator),
        tier=tier_of(creator.followers),
    )


def build_match(
    creator: Creator,
    assessment: CreatorAssessment,
    brand: BrandProfile,
    settings: MatchingSettings,
) -> Match:
    metrics = metrics_of(creator)
    engagement = min(metrics.engagement_rate / settings.engagement_benchmark, 1.0)
    tier_fit = 1.0 if metrics.tier in brand.preferred_tiers else 0.3
    w = settings.weights
    score = (
        w.relevance * assessment.relevance
        + w.audience_fit * assessment.audience_fit
        + w.engagement * engagement
        + w.tier_fit * tier_fit
    ) / (w.relevance + w.audience_fit + w.engagement + w.tier_fit)
    return Match(
        creator=creator,
        metrics=metrics,
        relevance=assessment.relevance,
        audience_fit=assessment.audience_fit,
        engagement=engagement,
        tier_fit=tier_fit,
        score=score,
        reason=assessment.reason,
    )
