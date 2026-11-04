"""
Pass 2: LLM Verification & Text Bounding.
Pipes screened candidates from cache or in-memory through Ollama (granite4.1:3b),
enforces text length bounding (1,500 - 3,000 words, minimum 100 words),
and formats records for `user_occupations_text.parquet`.
"""

from pathlib import Path
from typing import Dict, Iterator, List, Optional
import json
from dataset.scripts.ingest.ollama_extractor import OllamaOccupationExtractor as OllamaExtractor


MIN_WORDS = 100
MAX_WORDS = 3000


def bound_text(texts: List[str], min_words: int = MIN_WORDS, max_words: int = MAX_WORDS) -> Optional[str]:
    """Concatenates user texts, filters low-effort fragments, and bounds to [min_words, max_words].

    Returns concatenated string if total word count >= min_words, else None.
    """
    accumulated_words = 0
    selected_chunks: List[str] = []

    for t in texts:
        if not isinstance(t, str):
            continue
        cleaned = t.strip()
        words = cleaned.split()
        # Skip trivial single-word responses (e.g. "yes", "lol")
        if len(words) < 3:
            continue

        selected_chunks.append(cleaned)
        accumulated_words += len(words)
        if accumulated_words >= max_words:
            break

    if accumulated_words < min_words:
        return None

    full_text = " ".join(selected_chunks)
    # Strict upper bound trimming if slightly exceeded
    words = full_text.split()
    if len(words) > max_words:
        full_text = " ".join(words[:max_words])

    return full_text


class ExtractionPass:
    """Second-pass LLM extraction and text bounding."""

    def __init__(self, extractor: Optional[OllamaExtractor] = None):
        self.extractor = extractor or OllamaExtractor(model="granite4.1:3b")

    def process_candidates(
        self,
        candidates: Iterator[Dict],
        output_parquet_path: Optional[Path] = None,
        max_verified: Optional[int] = None,
    ) -> List[Dict]:
        """Runs LLM occupation extraction on context snippets.

        For each candidate with confirmed occupation(s):
          1. Checks bounds for all_texts (>= 100 words, bounded to 3000 words).
          2. Formats record for `user_occupations_text.parquet`.
        """
        import pandas as pd

        verified_records: List[Dict] = []

        for cand in candidates:
            user_id = cand.get("user_id")
            source = cand.get("source", "unknown")
            snippets = cand.get("context_snippets", [])
            texts = cand.get("texts", [])

            # First verify text volume to avoid wasting LLM inference on users with < 100 words
            bounded_text = bound_text(texts)
            if bounded_text is None:
                continue

            # Query Ollama on snippets
            verified_occupations = set()
            for snippet in snippets:
                extracted = self.extractor.extract(snippet)
                for occ in extracted:
                    verified_occupations.add(occ)

            if verified_occupations:
                occ_list = sorted(list(verified_occupations))
                word_count = len(bounded_text.split())
                rec = {
                    "user_id": str(user_id),
                    "occupations": occ_list,
                    "text": bounded_text,
                    "word_count": word_count,
                    "source": source,
                }
                verified_records.append(rec)

                if max_verified is not None and len(verified_records) >= max_verified:
                    break

        if output_parquet_path and verified_records:
            df = pd.DataFrame(verified_records)
            output_parquet_path = Path(output_parquet_path)
            output_parquet_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(output_parquet_path, index=False)
            print(f"[ExtractionPass] Saved {len(df)} verified user profiles to {output_parquet_path}")

        return verified_records
