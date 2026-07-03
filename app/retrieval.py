"""
BM25-based retrieval index over the SHL catalog.
Loaded once at startup; all search operations are synchronous and fast (< 5ms on 400 items).
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from rank_bm25 import BM25Okapi

CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.json"
_TOKEN_RE = re.compile(r"[a-z0-9#+._]+")

# Synonyms injected at index time so queries like "OPQ" also hit "Occupational Personality"
SYNONYMS = {
    "opq": "occupational personality questionnaire opq32r personality",
    "opq32": "occupational personality questionnaire opq32r personality",
    "sjt": "situational judgement test behavioral",
    "aws": "amazon web services cloud development",
    "gcp": "google cloud platform",
    "ml": "machine learning data science",
    "ai": "artificial intelligence machine learning",
    "js": "javascript frontend web",
    "ts": "typescript javascript",
    "k8s": "kubernetes container orchestration",
    "ci": "jenkins devops continuous integration",
    "cd": "jenkins devops continuous deployment",
    "db": "database sql",
    "qa": "manual testing test automation quality assurance",
    "hr": "human resources people management",
}


def _tokenize(text: str) -> List[str]:
    tokens = _TOKEN_RE.findall(text.lower())
    expanded = []
    for t in tokens:
        expanded.append(t)
        if t in SYNONYMS:
            expanded.extend(_TOKEN_RE.findall(SYNONYMS[t]))
    return expanded


class CatalogIndex:
    """
    In-memory BM25 index with:
    - Weighted document text (name repeated 3× for higher title importance)
    - Synonym expansion at query and index time
    - Exact + substring name lookup for compare/refine requests
    - URL validation for post-LLM response checking
    """

    def __init__(self, path: Path = CATALOG_PATH):
        with open(path, "r", encoding="utf-8") as f:
            self.items: List[Dict[str, Any]] = json.load(f)
        if not self.items:
            raise RuntimeError(
                f"Catalog at {path} is empty. Add data/catalog.json before starting."
            )
        self._docs = [self._doc_text(it) for it in self.items]
        self._tokenized = [_tokenize(d) for d in self._docs]
        self.bm25 = BM25Okapi(self._tokenized)
        self.by_url = {it["url"]: it for it in self.items}
        self.by_lower_name = {it["name"].lower(): it for it in self.items}

    @staticmethod
    def _doc_text(item: Dict[str, Any]) -> str:
        name = item.get("name", "")
        desc = item.get("description", "")
        levels = " ".join(item.get("job_levels", []))
        types = " ".join(item.get("test_type", []))
        # Name repeated 3× so title matches rank highest
        return f"{name} {name} {name} {desc} {levels} {types}"

    def search(self, query: str, k: int = 20) -> List[Dict[str, Any]]:
        if not query.strip():
            return self.items[:k]
        tokens = _tokenize(query)
        scores = self.bm25.get_scores(tokens)
        ranked = sorted(range(len(self.items)), key=lambda i: scores[i], reverse=True)
        results = [self.items[i] for i in ranked[:k] if scores[i] > 0]
        return results if results else self.items[:k]

    def find_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Case-insensitive exact → substring match. Used for compare/refine grounding."""
        key = name.lower().strip()
        if key in self.by_lower_name:
            return self.by_lower_name[key]
        for item in self.items:
            item_lower = item["name"].lower()
            if key in item_lower or item_lower in key:
                return item
        return None

    def is_valid_url(self, url: str) -> bool:
        return url in self.by_url

    def format_for_prompt(self, candidates: List[Dict[str, Any]]) -> str:
        """Compact JSON for prompt injection — keeps token count low."""
        return json.dumps([
            {
                "name": c["name"],
                "url": c["url"],
                "test_type": c.get("test_type", []),
                "description": (c.get("description") or "")[:300],
                "job_levels": c.get("job_levels", []),
                "duration_minutes": c.get("duration_minutes"),
                "remote_testing": c.get("remote_testing", False),
            }
            for c in candidates
        ], ensure_ascii=False)
