"""
Arctic Shift API client for retrieving cross-subreddit user comment histories.
Fetches full multi-subreddit text for verified authors up to target word budgets.
"""

from typing import Dict, List, Optional
import requests


ARCTIC_SHIFT_BASE = "https://arctic-shift.photon-reddit.com/api"
DEFAULT_USER_AGENT = "personality2occupation-research/1.0"


class ArcticShiftClient:
    """Client for pulling user comments and posts across all subreddits."""

    def __init__(self, user_agent: str = DEFAULT_USER_AGENT, timeout: int = 25):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self.timeout = timeout

    def fetch_user_comments(
        self,
        author: str,
        limit: int = 100,
        fields: str = "body,subreddit,created_utc",
    ) -> List[Dict]:
        """Fetches up to `limit` comments for the author across all subreddits."""
        url = f"{ARCTIC_SHIFT_BASE}/comments/search"
        params = {
            "author": author,
            "limit": limit,
            "fields": fields,
            "sort": "desc",
        }
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json().get("data", [])
        except Exception as e:
            print(f"[ArcticShiftClient] Error fetching comments for {author}: {e}")
        return []

    def fetch_user_posts(
        self,
        author: str,
        limit: int = 50,
        fields: str = "title,selftext,subreddit,created_utc",
    ) -> List[Dict]:
        """Fetches up to `limit` thread submissions for the author."""
        url = f"{ARCTIC_SHIFT_BASE}/posts/search"
        params = {
            "author": author,
            "limit": limit,
            "fields": fields,
            "sort": "desc",
        }
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json().get("data", [])
        except Exception as e:
            print(f"[ArcticShiftClient] Error fetching posts for {author}: {e}")
        return []

    def get_user_full_text(self, author: str, max_words: int = 3000) -> List[str]:
        """Fetches author comments and post submissions and returns clean text chunks."""
        text_chunks: List[str] = []
        words = 0

        # Comments first
        comments = self.fetch_user_comments(author, limit=100)
        for c in comments:
            body = (c.get("body") or "").strip()
            if body and body not in ("[deleted]", "[removed]"):
                text_chunks.append(body)
                words += len(body.split())
                if words >= max_words:
                    return text_chunks

        # Supplement with posts if under budget
        if words < max_words:
            posts = self.fetch_user_posts(author, limit=50)
            for p in posts:
                title = (p.get("title") or "").strip()
                selftext = (p.get("selftext") or "").strip()
                combined = f"{title}. {selftext}".strip()
                if combined and combined not in ("[deleted]", "[removed]"):
                    text_chunks.append(combined)
                    words += len(combined.split())
                    if words >= max_words:
                        break

        return text_chunks


if __name__ == "__main__":
    client = ArcticShiftClient()
    texts = client.get_user_full_text("bobtimuspryme")
    print(f"Fetched {len(texts)} text chunks. Total words: {sum(len(t.split()) for t in texts)}")
