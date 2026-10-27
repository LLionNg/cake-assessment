import logging
from concurrent.futures import ThreadPoolExecutor

from src.core.config import Settings
from src.core.container import build_services
from src.data.schemas import CreatorAssessment, MatchReport
from src.data.website import fetch_website_text
from src.services.assessor import CreatorAssessor
from src.services.discovery import CreatorDiscovery
from src.services.export import export_run
from src.services.profiler import BrandProfiler
from src.services.scoring import build_match

log = logging.getLogger(__name__)


class KOLMatcher:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.services = build_services(settings)
        self.profiler = BrandProfiler(self.services.llm, settings.matching)
        self.discovery = CreatorDiscovery(self.services.tiktok, settings.matching)
        self.assessor = CreatorAssessor(self.services.llm, settings.matching.assess_batch_size)

    def run(
        self, facebook_url: str, website_url: str | None = None, top_n: int | None = None
    ) -> MatchReport:
        with ThreadPoolExecutor(max_workers=2) as pool:
            page_job = pool.submit(self.services.facebook.fetch_page, facebook_url)
            website_job = pool.submit(fetch_website_text, website_url)
            page, website_text = page_job.result(), website_job.result()

        brand = self.profiler.profile(page, website_text)
        log.info("Brand profile: %s", brand.brand_name)

        creators = self.discovery.discover(brand)
        log.info("Assessing %d Thai creators", len(creators))
        assessments = self.assessor.assess(brand, creators)

        matches = [
            build_match(
                c, assessments.get(c.handle) or _unassessed(c.handle), brand, self.settings.matching
            )
            for c in creators
        ]
        matches.sort(key=lambda m: m.score, reverse=True)
        if self.settings.embedding.export_dir:
            run_dir = export_run(self.settings.embedding.export_dir, page, brand, matches)
            log.info("Exported ranking datasheet to %s", run_dir)
        return MatchReport(
            brand=brand,
            matches=matches[: top_n or self.settings.matching.top_n],
            mode=self.services.mode,
        )


def _unassessed(handle: str) -> CreatorAssessment:
    return CreatorAssessment(handle=handle, relevance=0, audience_fit=0, reason="Not assessed")
