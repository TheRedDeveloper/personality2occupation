"""
Download helper for the Blog Authorship Corpus from Hugging Face.
Ensures local caching without re-downloading if already present.
"""

from pathlib import Path
from typing import Optional
import datasets


DATASET_NAME = "barilan/blog_authorship_corpus"


def download_blogger(cache_dir: Optional[Path] = None, split: str = "train") -> datasets.Dataset:
    """Loads the Blog Authorship Corpus from Hugging Face.

    The Hugging Face datasets library caches files automatically in ~/.cache/huggingface/datasets
    or the specified cache_dir.
    """
    print(f"[download_blogger] Loading '{DATASET_NAME}' (split={split})...")
    ds = datasets.load_dataset(
        DATASET_NAME,
        split=split,
        trust_remote_code=True,
        cache_dir=str(cache_dir) if cache_dir else None,
    )
    print(f"[download_blogger] Loaded {len(ds):,} rows.")
    return ds


if __name__ == "__main__":
    download_blogger()
