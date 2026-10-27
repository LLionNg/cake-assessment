import json

import numpy as np
import pandas as pd
import pytest

from src.core.config import Settings
from src.data.schemas import Creator, FacebookPage, Video
from src.services.export import brand_text, creator_text
from src.services.matcher import KOLMatcher
from src.utils.vectors import cosine_similarity


def test_cosine_similarity():
    query = np.array([1.0, 0.0])
    matrix = np.array([[2.0, 0.0], [0.0, 3.0], [-1.0, 0.0], [1.0, 1.0]])

    assert cosine_similarity(query, matrix) == pytest.approx([1.0, 0.0, -1.0, 2**-0.5])


def test_creator_text_skips_empty_parts():
    creator = Creator(handle="x", bio="  ", videos=[Video(url="a", caption="cafe"), Video(url="b")])
    assert creator_text(creator) == "cafe"


def test_matcher_exports_datasheet(tmp_path):
    settings = Settings.model_validate({"embedding": {"export_dir": str(tmp_path)}})
    report = KOLMatcher(settings).run("https://www.facebook.com/example", top_n=3)

    run_dir = next(tmp_path.iterdir())
    creators = pd.read_csv(run_dir / "creators.csv", encoding="utf-8-sig")
    brand = json.loads((run_dir / "brand.json").read_text(encoding="utf-8"))

    assert len(creators) > len(report.matches)
    assert list(creators["rank"]) == list(range(1, len(creators) + 1))
    assert creators["concat_desc"].str.len().min() > 0
    page = FacebookPage.model_validate(brand["facebook"])
    assert brand["concat_desc"] == brand_text(page, report.brand)
