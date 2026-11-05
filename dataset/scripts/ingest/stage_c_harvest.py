"""
Stage C: Multi-Threaded Arctic Shift Cross-Subreddit Personality Harvest.
Reads confirmed professionals from `dataset/cache/verified_professionals.jsonl`.
Pulls full multi-subreddit comment histories via concurrent Arctic Shift REST queries.
Bounds cumulative text to [1,500 - 3,000] words (min 100 words).
Immediately flushes completed user profiles to `dataset/cache/user_occupations_text_checkpoint.jsonl`
and updates `dataset/user_occupations_text.parquet`.
Pure Network I/O & Text Bounding (multithreaded, zero GPU bottleneck).
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import time
from typing import Dict, List, Optional, Set
import pandas as pd
from dataset.scripts.ingest.arctic_shift_client import ArcticShiftClient
from dataset.scripts.ingest.pass2_extract import bound_text
from dataset.scripts.ingest.checkpoint_manager import IngestCheckpointManager


DEFAULT_VERIFIED_INPUT = Path("dataset/cache/verified_professionals.jsonl")
DEFAULT_TARGET_PARQUET = Path("dataset/user_occupations_text.parquet")


class PersonalityHarvestStage:
    """Stage C: High-throughput concurrent network pull for true cross-subreddit personality."""

    def __init__(
        self,
        verified_input: Path = DEFAULT_VERIFIED_INPUT,
        checkpoint_mgr: Optional[IngestCheckpointManager] = None,
        arctic_client: Optional[ArcticShiftClient] = None,
        target_parquet: Path = DEFAULT_TARGET_PARQUET,
    ):
        self.verified_input = Path(verified_input)
        self.checkpoint_mgr = checkpoint_mgr or IngestCheckpointManager()
        self.arctic_client = arctic_client or ArcticShiftClient()
        self.target_parquet = Path(target_parquet)

    def load_pending_authors(self) -> List[Dict]:
        """Loads verified professionals that have not yet had their text checkpointed."""
        if not self.verified_input.exists():
            return []

        pending = []
        with open(self.verified_input, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                user_id = rec.get("user_id")
                if not self.checkpoint_mgr.is_author_seen(user_id):
                    pending.append(rec)
        return pending

    def run(self, max_workers: int = 4, limit: Optional[int] = None) -> int:
        """Executes multi-threaded text retrieval and flushes immediately to disk."""
        pending = self.load_pending_authors()
        if limit:
            pending = pending[:limit]

        print("\n=======================================================")
        print(f"Stage C: Multi-Threaded Arctic Shift Cross-Subreddit Harvest")
        print(f"Pending Verified Professionals: {len(pending):,}")
        print(f"Parallel Workers: {max_workers}")
        print("=======================================================")

        if not pending:
            print("[Stage C] No pending verified authors to process. Exporting current parquet...")
            self.checkpoint_mgr.export_to_parquet(self.target_parquet)
            return 0

        def fetch_user_data(author_record: Dict) -> Optional[Dict]:
            author = author_record["user_id"]
            occs = author_record["occupations"]
            clean_occs = [o for o in occs if o.lower() not in {"job", "work", "other job", "profession", "occupation", "career", "employee", "worker"}]
            if not clean_occs:
                return None
            source = author_record.get("source", "reddit")

            text_chunks = self.arctic_client.get_user_full_text(author, max_words=3000)
            bounded = bound_text(text_chunks)
            if bounded is None:
                return None

            return {
                "user_id": author,
                "occupations": clean_occs,
                "text": bounded,
                "word_count": len(bounded.split()),
                "source": source,
            }

        committed_count = 0
        t0 = time.time()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_author = {executor.submit(fetch_user_data, rec): rec["user_id"] for rec in pending}
            for future in as_completed(future_to_author):
                author_id = future_to_author[future]
                try:
                    profile = future.result()
                    if profile:
                        self.checkpoint_mgr.append_record(profile)
                        committed_count += 1
                        if committed_count % 25 == 0 or committed_count == len(pending):
                            elapsed = round(time.time() - t0, 1)
                            rate = round(committed_count / max(1, elapsed), 1)
                            print(f"[Stage C] Committed {committed_count:,}/{len(pending):,} profiles ({rate} profiles/sec)...")
                except Exception as e:
                    print(f"[Stage C] Error retrieving user u/{author_id}: {e}")

        # Update parquet export
        print(f"\n[Stage C] Syncing final parquet to {self.target_parquet}...")
        self.checkpoint_mgr.export_to_parquet(self.target_parquet)
        print(f"[Stage C] Complete! Successfully checkpointed and exported {committed_count:,} new profiles.")
        return committed_count


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Stage C Arctic Shift Personality Harvest")
    parser.add_argument("--workers", type=int, default=6, help="Concurrent HTTP workers (default: 6)")
    parser.add_argument("--limit", type=int, default=None, help="Max authors to process")
    args = parser.parse_args()

    stage_c = PersonalityHarvestStage()
    stage_c.run(max_workers=args.workers, limit=args.limit)
