"""
Downloader and reader for the Reddit Pushshift Subreddit Cleaned dataset
hosted on Hugging Face: `anhchanghoangsg/reddit_pushshift_dataset_cleaned`.

Provides high-speed direct Parquet reading for target trade and clinical subreddits.
"""

from pathlib import Path
from typing import List, Optional
import pandas as pd
import requests


REPO_ID = "anhchanghoangsg/reddit_pushshift_dataset_cleaned"
BASE_URL = f"https://huggingface.co/datasets/{REPO_ID}/resolve/main"

# Target subreddits capturing underrepresented trades, medical/clinical, and specialised professions
DEFAULT_TARGET_SUBREDDITS = [
    # Trades
    "electricians",
    "AskElectricians",
    "Plumbing",
    "HVAC",
    "hvacadvice",
    # Clinical & Medical
    "Dentistry",
    "medicine",
    "FamilyMedicine",
    "emergencymedicine",
    "nursing",
    "TravelNursing",
    # Professional & Specialized
    "sysadmin",
    "legaladvice",
]


def list_available_subreddit_files() -> List[str]:
    """Queries Hugging Face API to retrieve all available parquet filenames."""
    api_url = f"https://huggingface.co/api/datasets/{REPO_ID}"
    resp = requests.get(api_url, timeout=30)
    resp.raise_for_status()
    siblings = resp.json().get("siblings", [])
    return [s.get("rfilename") for s in siblings if s.get("rfilename", "").endswith(".parquet")]


def get_subreddit_file_url(subreddit: str, kind: str = "comments") -> Optional[str]:
    """Finds the remote Hugging Face parquet URL for a given subreddit name.

    `kind` is typically 'comments' or 'submissions'.
    """
    sub_lower = subreddit.lower()
    suffix = f"_{kind}_cleaned.parquet".lower()

    # Query API or scan available files
    files = list_available_subreddit_files()
    for f in files:
        fname = f.split("/")[-1].lower()
        if fname == f"{sub_lower}{suffix}":
            return f"{BASE_URL}/{f}"
    return None


def download_subreddit_parquet(
    subreddit: str,
    output_dir: Path,
    kind: str = "comments",
) -> Optional[Path]:
    """Downloads a specific subreddit's Parquet file to output_dir if not already present."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / f"{subreddit}_{kind}_cleaned.parquet"
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[download_reddit] {dest.name} already exists locally ({round(dest.stat().st_size / (1024*1024), 2)} MB).")
        return dest

    url = get_subreddit_file_url(subreddit, kind=kind)
    if not url:
        print(f"[download_reddit] Subreddit '{subreddit}' ({kind}) not found in HF repo.")
        return None

    print(f"[download_reddit] Downloading {url} -> {dest}...")
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
    print(f"[download_reddit] Saved {dest.name} ({round(dest.stat().st_size / (1024*1024), 2)} MB).")
    return dest


def load_subreddit_dataframe(
    subreddit: str,
    local_dir: Optional[Path] = None,
    kind: str = "comments",
    columns: Optional[List[str]] = None,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """Reads a subreddit Parquet file into a Pandas DataFrame either locally or directly via HTTP."""
    if local_dir:
        local_path = Path(local_dir) / f"{subreddit}_{kind}_cleaned.parquet"
        if local_path.exists():
            df = pd.read_parquet(local_path, columns=columns)
            return df.head(limit) if limit else df

    url = get_subreddit_file_url(subreddit, kind=kind)
    if not url:
        raise ValueError(f"Subreddit {subreddit} not found in {REPO_ID}")

    df = pd.read_parquet(url, columns=columns)
    return df.head(limit) if limit else df


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Download subreddit Parquet from Hugging Face")
    parser.add_argument("--subreddits", nargs="+", default=["electricians", "Dentistry", "HVAC"])
    parser.add_argument("--dest", type=Path, default=Path("dataset/raw/reddit"))
    args = parser.parse_args()

    for sub in args.subreddits:
        download_subreddit_parquet(sub, args.dest)
