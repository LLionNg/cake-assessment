from typing import Literal

from pydantic import BaseModel, Field

Tier = Literal[1, 2, 3, 4, 5]


class FacebookPage(BaseModel):
    url: str
    name: str = ""
    intro: str = ""
    about: str = ""
    categories: list[str] = []
    followers: int = 0
    website: str = ""
    posts: list[str] = []


class BrandProfile(BaseModel):
    brand_name: str
    industry: str
    summary: str
    products: list[str]
    target_audience: str
    content_style: str
    search_queries: list[str] = Field(description="TikTok search keywords, Thai and English")
    hashtags: list[str] = Field(description="TikTok hashtags without the # sign")
    preferred_tiers: list[Tier]


class Video(BaseModel):
    url: str
    caption: str = ""
    plays: int = 0
    likes: int | None = Field(0, description="None when the source has no engagement data")
    comments: int = 0
    shares: int = 0
    created_at: str = ""
    location: str = ""


class Creator(BaseModel):
    handle: str
    nickname: str = ""
    bio: str = ""
    followers: int = 0
    total_likes: int = 0
    verified: bool = False
    avatar: str = ""
    videos: list[Video] = []

    @property
    def url(self) -> str:
        return f"https://www.tiktok.com/@{self.handle}"


class CreatorAssessment(BaseModel):
    handle: str
    relevance: float = Field(ge=0, le=1, description="Content fit with the brand")
    audience_fit: float = Field(ge=0, le=1, description="Estimated fit with the target audience")
    reason: str = Field(description="One or two sentences explaining the match")


class AssessmentBatch(BaseModel):
    assessments: list[CreatorAssessment]


class Metrics(BaseModel):
    engagement_rate: float
    median_views: int
    thai_ratio: float
    tier: Tier


class Match(BaseModel):
    creator: Creator
    metrics: Metrics
    relevance: float
    audience_fit: float
    engagement: float
    tier_fit: float
    score: float
    reason: str

    def to_row(self) -> dict:

        return {
            "score": round(self.score, 3),
            "profile": self.creator.url,
            "name": self.creator.nickname,
            "followers": self.creator.followers,
            "tier": self.metrics.tier,
            "engagement_rate": round(self.metrics.engagement_rate, 4),
            "median_views": self.metrics.median_views,
            "relevance": round(self.relevance, 2),
            "audience_fit": round(self.audience_fit, 2),
            "reason": self.reason,
        }


class MatchReport(BaseModel):
    brand: BrandProfile
    matches: list[Match]
    mode: str
