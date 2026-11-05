"""
Dedicated Bluesky Ingestion Pipeline (4-Step End-to-End):
Step 1: Search users by occupation terms -> `dataset/cache/bluesky_users.jsonl`
Step 2: Extract & format bios -> `dataset/cache/bluesky_bios.jsonl`
Step 3: Multi-threaded Ollama GPU verification ("My bio: {bio}") -> `dataset/cache/verified_bluesky.jsonl`
Step 4: Feed harvest via getAuthorFeed up to 1,500 - 3,000 words -> `user_occupations_text_checkpoint.jsonl`

All steps support `--continue` for complete resume capability.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import json
from pathlib import Path
import time
from typing import Dict, List, Optional, Set
import requests
from tqdm import tqdm

from dataset.scripts.download.download_bluesky_users import search_bluesky_users
from dataset.scripts.download.download_bluesky_bios import extract_and_download_bios
from dataset.scripts.ingest.pass2_extract import bound_text
from dataset.scripts.ingest.ollama_extractor import OllamaOccupationExtractor
from dataset.scripts.ingest.checkpoint_manager import IngestCheckpointManager
from dataset.scripts.ingest.lexicon import build_or_load_lexicon


DEFAULT_USERS = Path("dataset/cache/bluesky_users.jsonl")
DEFAULT_BIOS = Path("dataset/cache/bluesky_bios.jsonl")
DEFAULT_VERIFIED_BLUESKY = Path("dataset/cache/verified_bluesky.jsonl")
BLUESKY_AUTHOR_FEED_API = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"


class BlueskyIngestPipeline:
    def __init__(
        self,
        users_path: Path = DEFAULT_USERS,
        bios_path: Path = DEFAULT_BIOS,
        verified_path: Path = DEFAULT_VERIFIED_BLUESKY,
        model_name: str = "granite4.1:3b",
    ):
        self.users_path = Path(users_path)
        self.bios_path = Path(bios_path)
        self.verified_path = Path(verified_path)
        self.model_name = model_name
        self.mgr = IngestCheckpointManager()
        self.lex = build_or_load_lexicon()

    def step_1_search_users(self, max_terms: Optional[int] = None, resumable: bool = True) -> int:
        return search_bluesky_users(output_path=self.users_path, max_terms=max_terms, resumable=resumable)

    def step_2_format_bios(self, resumable: bool = True) -> int:
        return extract_and_download_bios(users_input=self.users_path, bios_output=self.bios_path, resumable=resumable)

    def step_3_verify_bios(
        self,
        max_workers: int = 4,
        resumable: bool = True,
        max_candidates: Optional[int] = None,
    ) -> int:
        """Parallel Ollama GPU evaluation of candidate bios with 'My bio: ' prefix."""
        if not self.bios_path.exists():
            print(f"[Bluesky Step 3] Bios file not found at: {self.bios_path}")
            return 0

        self.verified_path.parent.mkdir(parents=True, exist_ok=True)
        already_verified: Set[str] = set()
        if resumable and self.verified_path.exists():
            with open(self.verified_path, "r", encoding="utf-8") as f:
                for line in f:
                    u = json.loads(line).get("user_id")
                    if u:
                        already_verified.add(u)
            print(f"[Bluesky Step 3] Loaded {len(already_verified):,} already verified authors.")

        evaluated_uids: Set[str] = set()
        evaluated_path = self.verified_path.parent / "bluesky_evaluated_uids.txt"
        if resumable and evaluated_path.exists():
            with open(evaluated_path, "r", encoding="utf-8") as f:
                for line in f:
                    u = line.strip()
                    if u:
                        evaluated_uids.add(u)
            print(f"[Bluesky Step 3] Loaded {len(evaluated_uids):,} already evaluated authors.")
        else:
            evaluated_uids.update(already_verified)

        candidates = []
        with open(self.bios_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                uid = rec.get("user_id") or rec.get("handle")
                if uid and uid not in evaluated_uids and not self.mgr.is_author_seen(uid):
                    candidates.append(rec)
                    if max_candidates and len(candidates) >= max_candidates:
                        break

        print("\n" + "=" * 70)
        print("Bluesky Step 3: Parallelized Ollama Bio Verification")
        print(f"Model: {self.model_name} | Workers: {max_workers}")
        print(f"Pending Bios to Evaluate: {len(candidates):,}")
        print("=" * 70)

        if not candidates:
            print("[Bluesky Step 3] No bios pending verification.")
            return 0

        writer = open(self.verified_path, "a", encoding="utf-8")
        eval_writer = open(evaluated_path, "a", encoding="utf-8")
        verified_count = 0

        def eval_bio(cand: Dict) -> tuple[Optional[Dict], str]:
            extractor = OllamaOccupationExtractor(model=self.model_name)
            bio = cand.get("bio", "")
            occs = extractor.extract(f"My bio: {bio}")
            uid = cand.get("handle") or cand.get("user_id") or ""
            if occs:
                return {
                    "user_id": uid,
                    "handle": cand.get("handle"),
                    "did": cand.get("did"),
                    "occupations": sorted(list(set(occs))),
                    "bio": bio,
                    "source": "bluesky",
                }, uid
            return None, uid

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(eval_bio, c): c for c in candidates}
                pbar = tqdm(
                    total=len(candidates),
                    desc=f"Verifying Bios ({max_workers} threads)",
                    smoothing=0,
                    mininterval=1.0,
                )
                pbar.set_postfix({"verified": 0}, refresh=True)
                for future in as_completed(futures):
                    res, uid = future.result()
                    pbar.update(1)
                    if uid:
                        eval_writer.write(uid + "\n")
                    if res:
                        writer.write(json.dumps(res, ensure_ascii=False) + "\n")
                        writer.flush()
                        verified_count += 1
                        pbar.set_postfix({"verified": verified_count}, refresh=False)
                pbar.close()
        finally:
            writer.close()
            eval_writer.close()

        print(f"[Bluesky Step 3] Complete! Verified {verified_count:,} professional bios.")
        return verified_count

    def step_4_harvest_feeds(
        self,
        max_workers: int = 4,
        resumable: bool = True,
        max_users: Optional[int] = None,
    ) -> int:
        """Pulls author feeds via getAuthorFeed up to 1,500 - 3,000 words and commits to checkpoint."""
        if not self.verified_path.exists():
            print(f"[Bluesky Step 4] Verified file not found at: {self.verified_path}")
            return 0

        pending_users: List[Dict] = []
        with open(self.verified_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                uid = rec.get("user_id") or rec.get("handle")
                if uid and (not resumable or not self.mgr.is_author_seen(uid)):
                    pending_users.append(rec)
                    if max_users and len(pending_users) >= max_users:
                        break

        print("\n" + "=" * 70)
        print("Bluesky Step 4: Author Feed Harvest & Checkpoint Commit")
        print(f"Target Verified Authors: {len(pending_users):,}")
        print("=" * 70)

        if not pending_users:
            print("[Bluesky Step 4] All verified authors are already checkpointed.")
            return 0

        committed_count = 0

        def fetch_user_posts(user_info: Dict) -> Optional[Dict]:
            handle = user_info.get("handle") or user_info.get("user_id")
            posts = []
            cursor = None
            total_words = 0

            # Paginate feed up to 5 pages (up to 500 posts or ~3,000 words)
            for _ in range(5):
                params = {"actor": handle, "limit": 100}
                if cursor:
                    params["cursor"] = cursor

                try:
                    resp = requests.get(BLUESKY_AUTHOR_FEED_API, params=params, timeout=15)
                    if resp.status_code != 200:
                        break

                    data = resp.json()
                    feed = data.get("feed", [])
                    if not feed:
                        break

                    for item in feed:
                        rec = item.get("post", {}).get("record", {})
                        t = (rec.get("text") or "").strip()
                        if t:
                            posts.append(t)
                            total_words += len(t.split())

                    cursor = data.get("cursor")
                    if not cursor or total_words >= 3000:
                        break
                    time.sleep(0.05)
                except Exception:
                    break

            if not posts:
                return None

            bounded = bound_text(posts)
            if not bounded:
                return None

            clean_occs = [o for o in user_info.get("occupations", []) if o.lower() not in {"job", "work", "other job", "profession", "occupation", "career", "employee", "worker"}]
            if not clean_occs:
                return None

            return {
                "user_id": handle,
                "occupations": clean_occs,
                "text": bounded,
                "word_count": len(bounded.split()),
                "source": "bluesky",
            }

        pbar = tqdm(total=len(pending_users), desc="Harvesting Bluesky Feeds")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_user_posts, u): u for u in pending_users}
            for future in as_completed(futures):
                profile = future.result()
                pbar.update(1)
                if profile:
                    self.mgr.append_record(profile)
                    committed_count += 1
                    pbar.set_postfix({"committed": committed_count})
        pbar.close()

        if committed_count > 0:
            target_parquet = Path("dataset/user_occupations_text.parquet")
            self.mgr.export_to_parquet(target_parquet)
            print(f"[Bluesky Step 4] Updated final parquet at {target_parquet} with latest records.")

        print(f"[Bluesky Step 4] Complete! Harvested and checkpointed {committed_count:,} author profiles.")
        return committed_count

    def run_all(
        self,
        max_terms: Optional[int] = None,
        max_workers: int = 4,
        resumable: bool = True,
    ):
        self.step_1_search_users(max_terms=max_terms, resumable=resumable)
        self.step_2_format_bios(resumable=resumable)
        self.step_3_verify_bios(max_workers=max_workers, resumable=resumable)
        self.step_4_harvest_feeds(max_workers=max_workers, resumable=resumable)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bluesky Ingestion Pipeline")
    parser.add_argument("--step", choices=["1", "2", "3", "4", "all"], default="all", help="Pipeline step to run")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent threads (default: 4)")
    parser.add_argument("--max-terms", type=int, default=None, help="Max search terms for step 1")
    parser.add_argument("--continue", dest="cont", action="store_true", default=True, help="Resume from disk caches")
    args = parser.parse_args()

    pipeline = BlueskyIngestPipeline()
    if args.step == "1":
        pipeline.step_1_search_users(max_terms=args.max_terms, resumable=args.cont)
    elif args.step == "2":
        pipeline.step_2_format_bios(resumable=args.cont)
    elif args.step == "3":
        pipeline.step_3_verify_bios(max_workers=args.workers, resumable=args.cont)
    elif args.step == "4":
        pipeline.step_4_harvest_feeds(max_workers=args.workers, resumable=args.cont)
    else:
        pipeline.run_all(max_terms=args.max_terms, max_workers=args.workers, resumable=args.cont)
