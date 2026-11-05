"""
Indexes all available Pushshift subreddit Parquet files from Hugging Face:
`anhchanghoangsg/reddit_pushshift_dataset_cleaned`
and caches the list to `dataset/cache/hf_reddit_parquet_files.json`.
"""

import json
from pathlib import Path
from typing import List
import requests


REPO_ID = "anhchanghoangsg/reddit_pushshift_dataset_cleaned"
DEFAULT_CACHE_PATH = Path("dataset/cache/hf_reddit_parquet_files.json")


def fetch_and_cache_all_subreddit_files(cache_path: Path = DEFAULT_CACHE_PATH) -> List[str]:
    """Retrieves all 58,000+ parquet paths from the Hugging Face dataset API and writes to disk."""
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[index_subreddits] Querying Hugging Face API for {REPO_ID}...")
    api_url = f"https://huggingface.co/api/datasets/{REPO_ID}"
    resp = requests.get(api_url, timeout=45)
    resp.raise_for_status()

    siblings = resp.json().get("siblings", [])
    parquet_files = [
        s.get("rfilename")
        for s in siblings
        if s.get("rfilename", "").endswith(".parquet")
    ]

    print(f"[index_subreddits] Discovered {len(parquet_files):,} Parquet files.")
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(parquet_files, f, indent=2)

    print(f"[index_subreddits] Cached file list to {cache_path}")
    return parquet_files


if __name__ == "__main__":
    fetch_and_cache_all_subreddit_files()
