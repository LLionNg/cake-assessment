from src.data.schemas import AssessmentBatch, BrandProfile, CreatorAssessment, FacebookPage
from src.models.base import LLM, T
from src.utils.text import thai_ratio, top_keywords


class MockLLM(LLM):
    """Keyword heuristics standing in for the LLM when no provider credentials are set."""

    def parse(self, system: str, payload: dict, schema: type[T]) -> T:
        if schema is BrandProfile:
            return self._profile(payload)
        if schema is AssessmentBatch:
            return self._assess(payload)
        raise TypeError(f"MockLLM cannot produce {schema.__name__}")

    def _profile(self, payload: dict) -> BrandProfile:
        page = FacebookPage.model_validate(payload["facebook"])
        text = " ".join([page.intro, page.about, payload.get("website", "")])
        keywords = top_keywords(text, 6)
        if page.followers < 50_000:
            tiers = [4, 5]
        elif page.followers < 500_000:
            tiers = [3, 4]
        else:
            tiers = [2, 3]
        return BrandProfile(
            brand_name=page.name or page.url,
            industry=page.categories[0] if page.categories else "Unknown",
            summary=page.intro or page.about,
            products=keywords[:3],
            target_audience="Thai consumers interested in " + ", ".join(keywords[:3]),
            content_style="Casual, lifestyle",
            search_queries=keywords,
            hashtags=[k.replace(" ", "") for k in keywords],
            preferred_tiers=tiers,
        )

    def _assess(self, payload: dict) -> AssessmentBatch:
        brand = BrandProfile.model_validate(payload["brand"])
        terms = {t.lower() for t in brand.search_queries + brand.hashtags + brand.products}
        assessments = []
        for c in payload["creators"]:
            texts = [c["bio"], *c["captions"]]
            blob = " ".join(texts).lower()
            hits = sorted(t for t in terms if t in blob)
            assessments.append(
                CreatorAssessment(
                    handle=c["handle"],
                    relevance=min(1.0, len(hits) / 3),
                    audience_fit=thai_ratio(texts),
                    reason=f"Mock keyword match: {', '.join(hits) or 'none'}",
                )
            )
        return AssessmentBatch(assessments=assessments)
