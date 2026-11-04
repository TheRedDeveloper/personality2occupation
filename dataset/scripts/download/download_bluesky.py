"""
Bluesky archive inspector and public AT Protocol querying module.
"""

from pathlib import Path
from typing import Dict, Iterator, List, Optional
import json
import tarfile
import requests


BLUESKY_PUBLIC_API = "https://public.api.bsky.app/xrpc"


def check_local_zenodo_archive(archive_path: Path) -> bool:
    """Verifies that the downloaded Zenodo user_posts.tar.gz archive exists and is valid."""
    path = Path(archive_path)
    if not path.exists():
        return False
    size_gb = path.stat().st_size / (1024 ** 3)
    return size_gb > 1.0


def stream_zenodo_user_posts(
    archive_path: Path,
    max_users: Optional[int] = None,
    en_only: bool = True,
) -> Iterator[Dict]:
    """Streams user post archives from user_posts.tar.gz one user at a time.

    Yields dicts with:
      - `user_id`: str / int
      - `posts`: list of str
    """
    archive_path = Path(archive_path)
    if not archive_path.exists():
        raise FileNotFoundError(f"Zenodo archive not found at: {archive_path}")

    yielded_count = 0
    with tarfile.open(archive_path, "r:gz") as tar:
        for member in tar:
            if not member.isfile() or not member.name.endswith(".jsonl"):
                continue

            extracted = tar.extractfile(member)
            if extracted is None:
                continue

            user_posts: List[str] = []
            user_id: Optional[str] = None

            for line in extracted:
                try:
                    record = json.loads(line.decode("utf-8", errors="replace"))
                except Exception:
                    continue

                if user_id is None:
                    user_id = str(record.get("user_id", member.name))

                langs = record.get("langs") or []
                if en_only and langs and ("eng" not in langs and "en" not in langs):
                    continue

                text = record.get("text", "").strip()
                if text:
                    user_posts.append(text)

            if user_posts:
                yield {
                    "user_id": user_id,
                    "posts": user_posts,
                    "file_name": member.name,
                }
                yielded_count += 1
                if max_users is not None and yielded_count >= max_users:
                    break


def search_bsky_actors(query: str, limit: int = 25) -> List[Dict]:
    """Queries public AT Protocol searchActors endpoint for target occupation queries."""
    url = f"{BLUESKY_PUBLIC_API}/app.bsky.actor.searchActors"
    resp = requests.get(url, params={"q": query, "limit": limit}, timeout=15)
    resp.raise_for_status()
    return resp.json().get("actors", [])


def get_bsky_author_feed(actor_handle: str, limit: int = 50) -> List[str]:
    """Fetches recent public posts from an actor using the public AT Protocol feed endpoint."""
    url = f"{BLUESKY_PUBLIC_API}/app.bsky.feed.getAuthorFeed"
    resp = requests.get(url, params={"actor": actor_handle, "limit": limit}, timeout=15)
    if resp.status_code != 200:
        return []
    feed = resp.json().get("feed", [])
    posts = []
    for item in feed:
        record = item.get("post", {}).get("record", {})
        text = record.get("text", "").strip()
        if text:
            posts.append(text)
    return posts


if __name__ == "__main__":
    archive = Path("dataset/raw/bluesky/user_posts.tar.gz")
    if archive.exists():
        print(f"Archive found! ({round(archive.stat().st_size / (1024**3), 2)} GB)")
        for sample in stream_zenodo_user_posts(archive, max_users=2):
            print(f"User {sample['user_id']} has {len(sample['posts'])} posts. Sample post: {sample['posts'][0][:60]}")
