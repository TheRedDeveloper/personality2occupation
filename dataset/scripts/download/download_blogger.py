"""
Download helper for the Blog Authorship Corpus from Hugging Face.
Uses `paoramen/blog-authorship-corpus` which contains unique author IDs ('id')
for grouping all posts by unique author.
"""

from pathlib import Path
from typing import Optional, cast
import datasets


DATASET_NAME = "paoramen/blog-authorship-corpus"


def download_blogger(cache_dir: Optional[Path] = None, split: str = "train") -> datasets.Dataset:
    """Loads the complete Blog Authorship Corpus with author IDs.

    The Hugging Face datasets library caches files automatically in ~/.cache/huggingface/datasets
    or the specified cache_dir.
    """
    print(f"[download_blogger] Loading '{DATASET_NAME}' (split={split})...")
    ds = cast(
        datasets.Dataset,
        datasets.load_dataset(
            DATASET_NAME,
            split=split,
            cache_dir=str(cache_dir) if cache_dir else None,
        ),
    )
    print(f"[download_blogger] Loaded {len(ds):,} rows.")
    return ds


if __name__ == "__main__":
    download_blogger()
