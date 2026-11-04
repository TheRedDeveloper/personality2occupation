"""
Pass 1: Screening candidate texts using OccupationLexicon.
Extracts context windows around matching occupation keywords and saves candidate matches
to cache (`dataset/cache/candidates_<source>.jsonl`).
"""

from pathlib import Path
from typing import Dict, Iterator, List, Optional
import json
import re
from dataset.scripts.ingest.lexicon import OccupationLexicon, build_or_load_lexicon


def extract_context_window(text: str, keyword: str, max_chars: int = 500) -> str:
    """Extracts a bounded text window around the matched keyword.

    Provides sufficient local context for Ollama to evaluate whether the keyword
    denotes a self-reported occupation or conversational noise.
    """
    pattern = re.compile(rf"\b{re.escape(keyword)}\b", re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return text[:max_chars]

    start_idx = max(0, match.start() - (max_chars // 2))
    end_idx = min(len(text), match.end() + (max_chars // 2))

    # Expand to word boundaries if possible
    if start_idx > 0:
        prev_space = text.rfind(" ", 0, start_idx)
        if prev_space != -1 and (start_idx - prev_space) < 30:
            start_idx = prev_space + 1
    if end_idx < len(text):
        next_space = text.find(" ", end_idx)
        if next_space != -1 and (next_space - end_idx) < 30:
            end_idx = next_space

    return text[start_idx:end_idx].strip()


class ScreeningPass:
    """First-pass high-throughput keyword screening over raw user comments/posts."""

    def __init__(self, lexicon: Optional[OccupationLexicon] = None):
        if lexicon is None:
            self.lexicon = build_or_load_lexicon()
        else:
            self.lexicon = lexicon

    def screen_user_records(
        self,
        records: Iterator[Dict],
        output_cache_path: Optional[Path] = None,
        max_candidates: Optional[int] = None,
    ) -> List[Dict]:
        """Screens user text batches.

        Each input record must contain:
          - `user_id`: str
          - `source`: str
          - `texts`: list of str (or single `text`: str)

        Returns a list of candidate dictionaries and optionally writes them to JSONL:
          - `user_id`
          - `source`
          - `matched_keywords`
          - `context_snippets`
          - `all_texts`: original full text chunks for downstream bounding
        """
        candidates: List[Dict] = []
        writer = None
        if output_cache_path:
            output_cache_path = Path(output_cache_path)
            output_cache_path.parent.mkdir(parents=True, exist_ok=True)
            writer = open(output_cache_path, "w", encoding="utf-8")

        try:
            for rec in records:
                user_id = rec.get("user_id")
                source = rec.get("source", "unknown")
                raw_texts = rec.get("texts") or ([rec.get("text")] if rec.get("text") else [])

                matched_keywords_set = set()
                context_snippets: List[str] = []

                for t in raw_texts:
                    if not isinstance(t, str) or not t.strip():
                        continue
                    # Fast trie screening
                    matches = self.lexicon.match(t)
                    if matches:
                        for m in matches:
                            matched_keywords_set.add(m)
                            # Keep up to 3 distinct snippet contexts per user
                            if len(context_snippets) < 3:
                                snippet = extract_context_window(t, m)
                                if snippet not in context_snippets:
                                    context_snippets.append(snippet)

                if matched_keywords_set and context_snippets:
                    candidate = {
                        "user_id": user_id,
                        "source": source,
                        "matched_keywords": sorted(list(matched_keywords_set)),
                        "context_snippets": context_snippets,
                        "texts": raw_texts,
                    }
                    candidates.append(candidate)
                    if writer:
                        writer.write(json.dumps(candidate, ensure_ascii=False) + "\n")
                        writer.flush()

                    if max_candidates is not None and len(candidates) >= max_candidates:
                        break
        finally:
            if writer:
                writer.close()

        return candidates
