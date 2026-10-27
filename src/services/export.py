"""Writes each ranking as a datasheet so other rankers (e.g. embeddings) can be compared offline."""

import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.data.schemas import BrandProfile, Creator, FacebookPage, Match

MAX_CAPTIONS = 10
MAX_CAPTION_CHARS = 200


def brand_text(page: FacebookPage, brand: BrandProfile) -> str:
    parts = [
        brand.brand_name,
        brand.industry,
        brand.summary,
        "Products: " + ", ".join(brand.products),
        "Audience: " + brand.target_audience,
        "Style: " + brand.content_style,
        "Topics: " + ", ".join(brand.search_queries + brand.hashtags),
        page.intro,
        page.about,
    ]
    return "\n".join(p for p in parts if p.strip())


def creator_text(creator: Creator) -> str:
    captions = [v.caption[:MAX_CAPTION_CHARS] for v in creator.videos[:MAX_CAPTIONS]]
    return "\n".join(p for p in [creator.nickname, creator.bio, *captions] if p.strip())


def export_run(
    root: str | Path, page: FacebookPage, brand: BrandProfile, matches: list[Match]
) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", brand.brand_name.lower()).strip("-") or "brand"
    run_dir = Path(root) / f"{datetime.now():%Y%m%d-%H%M%S}-{slug}"
    run_dir.mkdir(parents=True, exist_ok=True)

    rows = [
        {
            "rank": rank,
            "handle": m.creator.handle,
            **m.to_row(),
            "engagement": round(m.engagement, 3),
            "tier_fit": m.tier_fit,
            "concat_desc": creator_text(m.creator),
        }
        for rank, m in enumerate(matches, 1)
    ]
    # utf-8-sig so Excel shows Thai text correctly.
    pd.DataFrame(rows).to_csv(run_dir / "creators.csv", index=False, encoding="utf-8-sig")
    brand_json = {
        "brand": brand.model_dump(),
        "facebook": page.model_dump(),
        "concat_desc": brand_text(page, brand),
    }
    (run_dir / "brand.json").write_text(
        json.dumps(brand_json, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return run_dir
