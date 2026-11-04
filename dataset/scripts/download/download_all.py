"""
Master CLI to orchestrate dataset preparation and downloads across all sources:
  - Blogger (Hugging Face)
  - Reddit (Pushshift Cleaned Subreddits Parquet)
  - Bluesky (Zenodo archive inspection & public AT Protocol test)
"""

import argparse
from pathlib import Path
from dataset.scripts.download.download_blogger import download_blogger
from dataset.scripts.download.download_reddit import download_subreddit_parquet, DEFAULT_TARGET_SUBREDDITS
from dataset.scripts.download.download_bluesky import check_local_zenodo_archive


def main():
    parser = argparse.ArgumentParser(description="Download & verify raw datasets for personality2occupation")
    parser.add_argument(
        "--source",
        choices=["all", "blogger", "reddit", "bluesky"],
        default="all",
        help="Which data source to fetch or verify",
    )
    parser.add_argument(
        "--reddit-subreddits",
        nargs="+",
        default=DEFAULT_TARGET_SUBREDDITS,
        help="List of subreddit names to download",
    )
    parser.add_argument(
        "--dest-reddit",
        type=Path,
        default=Path("dataset/raw/reddit"),
        help="Destination directory for Reddit Parquet files",
    )
    parser.add_argument(
        "--bluesky-archive",
        type=Path,
        default=Path("dataset/raw/bluesky/user_posts.tar.gz"),
        help="Path to Zenodo Bluesky user_posts.tar.gz",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Personality2Occupation Raw Dataset Verification / Downloader")
    print("=" * 60)

    if args.source in ("all", "blogger"):
        print("\n--- [1/3] Blog Authorship Corpus ---")
        ds = download_blogger()
        print(f"Blogger ready with {len(ds):,} rows.")

    if args.source in ("all", "bluesky"):
        print("\n--- [2/3] Bluesky Archive ---")
        if check_local_zenodo_archive(args.bluesky_archive):
            sz = round(args.bluesky_archive.stat().st_size / (1024 ** 3), 2)
            print(f"Bluesky archive present at {args.bluesky_archive} ({sz} GB).")
        else:
            print(f"[WARNING] Bluesky archive not found at {args.bluesky_archive}.")

    if args.source in ("all", "reddit"):
        print("\n--- [3/3] Reddit Target Subreddits ---")
        print(f"Downloading {len(args.reddit_subreddits)} subreddits to {args.dest_reddit}...")
        for sub in args.reddit_subreddits:
            download_subreddit_parquet(sub, args.dest_reddit)

    print("\nDataset preparation check complete.")


if __name__ == "__main__":
    main()
