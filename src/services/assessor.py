from concurrent.futures import ThreadPoolExecutor

from src.data.schemas import AssessmentBatch, BrandProfile, Creator, CreatorAssessment
from src.models.base import LLM
from src.prompts.prompts import CREATOR_ASSESSMENT

MAX_CAPTIONS = 8
MAX_CAPTION_CHARS = 200


class CreatorAssessor:
    def __init__(self, llm: LLM, batch_size: int):
        self.llm = llm
        self.batch_size = batch_size

    def assess(self, brand: BrandProfile, creators: list[Creator]) -> dict[str, CreatorAssessment]:
        batches = [
            creators[i : i + self.batch_size] for i in range(0, len(creators), self.batch_size)
        ]
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = pool.map(lambda batch: self._assess_batch(brand, batch), batches)
        return {a.handle: a for batch in results for a in batch.assessments}

    def _assess_batch(self, brand: BrandProfile, creators: list[Creator]) -> AssessmentBatch:
        payload = {
            "brand": brand.model_dump(),
            "creators": [
                {
                    "handle": c.handle,
                    "nickname": c.nickname,
                    "bio": c.bio,
                    "followers": c.followers,
                    "captions": [v.caption[:MAX_CAPTION_CHARS] for v in c.videos[:MAX_CAPTIONS]],
                }
                for c in creators
            ],
        }
        return self.llm.parse(CREATOR_ASSESSMENT, payload, AssessmentBatch)
