import re
from collections import Counter

THAI = re.compile(r"[\u0e00-\u0e7f]")
WORD = re.compile(r"[a-z]{4,}")
STOPWORDS = set(
    "with that this from your have will more about also into they their there what when"
    " which https www page home".split()
)


def has_thai(text: str) -> bool:
    return bool(THAI.search(text))


def thai_ratio(texts: list[str]) -> float:
    texts = [t for t in texts if t.strip()]
    if not texts:
        return 0.0
    return sum(has_thai(t) for t in texts) / len(texts)


def top_keywords(text: str, n: int) -> list[str]:
    words = [w for w in WORD.findall(text.lower()) if w not in STOPWORDS]
    return [w for w, _ in Counter(words).most_common(n)]
