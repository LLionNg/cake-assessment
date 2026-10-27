import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.core.config import load_settings
from src.models.embedding import BGEM3Embedder
from src.utils.vectors import cosine_similarity

TOP_K = 5


def spearman(a: pd.Series, b: pd.Series) -> float:
    return float(np.corrcoef(a.rank().to_numpy(), b.rank().to_numpy())[0, 1])


def main(run_dir: Path, config: str = "config.yml") -> None:
    creators = pd.read_csv(run_dir / "creators.csv", encoding="utf-8-sig")
    brand = json.loads((run_dir / "brand.json").read_text(encoding="utf-8"))

    embedder = BGEM3Embedder(load_settings(config).embedding)
    vectors = embedder.encode([brand["concat_desc"], *creators["concat_desc"].fillna("")])
    np.savez(
        run_dir / "embeddings.npz",
        brand=vectors[0],
        creators=vectors[1:],
        handles=creators["handle"].to_numpy(dtype=str),
    )

    creators["cosine"] = cosine_similarity(vectors[0], vectors[1:]).round(4)
    creators["cosine_rank"] = creators["cosine"].rank(ascending=False, method="first").astype(int)
    creators.to_csv(run_dir / "creators_ranked.csv", index=False, encoding="utf-8-sig")

    by_cosine = set(creators.nsmallest(TOP_K, "cosine_rank")["handle"])
    by_app = set(creators.nsmallest(TOP_K, "rank")["handle"])
    print(f"{len(creators)} creators, brand: {brand['brand']['brand_name']}")
    print("Spearman rank correlation of cosine with:")
    for column in ("relevance", "audience_fit", "score"):
        print(f"  {column:13s} {spearman(creators['cosine'], creators[column]):+.2f}")
    print(f"Top {TOP_K} overlap with the app ranking: {len(by_cosine & by_app)}/{TOP_K}\n")
    columns = ["rank", "cosine_rank", "handle", "score", "relevance", "cosine"]
    print(creators.sort_values("cosine_rank")[columns].to_string(index=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(Path(sys.argv[1]), *sys.argv[2:])
