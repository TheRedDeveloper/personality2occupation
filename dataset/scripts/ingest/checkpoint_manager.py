"""
Checkpoint and state manager for continuous, resumable data ingestion.
Maintains:
  - `dataset/cache/user_occupations_text_checkpoint.jsonl`: Immediate disk writes of verified records.
  - `dataset/cache/ingest_state.json`: Processed subreddits and seen authors.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Set
import pandas as pd


DEFAULT_CHECKPOINT_PATH = Path("dataset/cache/user_occupations_text_checkpoint.jsonl")
DEFAULT_STATE_PATH = Path("dataset/cache/ingest_state.json")


class IngestCheckpointManager:
    """Manages append-only JSONL checkpointing and resumable state tracking."""

    def __init__(
        self,
        checkpoint_path: Path = DEFAULT_CHECKPOINT_PATH,
        state_path: Path = DEFAULT_STATE_PATH,
    ):
        self.checkpoint_path = Path(checkpoint_path)
        self.state_path = Path(state_path)
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self.seen_authors: Set[str] = set()
        self.completed_subreddits: Set[str] = set()
        self.verified_authors_metadata: Dict[str, Dict] = {}
        self._load_state()

    def _load_state(self):
        """Loads state from disk if available."""
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.completed_subreddits = set(data.get("completed_subreddits", []))
                    self.verified_authors_metadata = data.get("verified_authors_metadata", {})
                    self.seen_authors.update(self.verified_authors_metadata.keys())
            except Exception as e:
                print(f"[CheckpointManager] Error reading state file: {e}")

        # Also load from checkpoint JSONL to populate seen_authors
        if self.checkpoint_path.exists():
            try:
                with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            rec = json.loads(line)
                            uid = rec.get("user_id")
                            if uid:
                                self.seen_authors.add(uid)
            except Exception as e:
                print(f"[CheckpointManager] Error reading checkpoint file: {e}")

        print(f"[CheckpointManager] Loaded state: {len(self.seen_authors):,} seen authors, {len(self.completed_subreddits):,} completed subreddits.")

    def is_author_seen(self, author_id: str) -> bool:
        """Returns True if the author was already processed."""
        return author_id in self.seen_authors

    def is_subreddit_completed(self, subreddit_name: str) -> bool:
        """Returns True if the subreddit has been completed."""
        return subreddit_name in self.completed_subreddits

    def append_record(self, record: Dict):
        """Immediately writes and flushes a verified record to disk."""
        user_id = record.get("user_id")
        if user_id:
            self.seen_authors.add(user_id)

        with open(self.checkpoint_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()

    def mark_subreddit_completed(self, subreddit_name: str):
        """Marks a subreddit as fully finished and updates state on disk."""
        self.completed_subreddits.add(subreddit_name)
        self.save_state()

    def save_state(self):
        """Saves current state to JSON."""
        state = {
            "completed_subreddits": sorted(list(self.completed_subreddits)),
            "seen_authors_count": len(self.seen_authors),
            "verified_authors_metadata": self.verified_authors_metadata,
        }
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def export_to_parquet(self, parquet_path: Path) -> pd.DataFrame:
        """Compiles the checkpoint JSONL file into the final target Parquet file."""
        parquet_path = Path(parquet_path)
        parquet_path.parent.mkdir(parents=True, exist_ok=True)

        records = []
        if self.checkpoint_path.exists():
            with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))

        if not records:
            print("[CheckpointManager] No records in checkpoint to export.")
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df = df.drop_duplicates(subset=["user_id", "source"])
        df.to_parquet(parquet_path, index=False)
        print(f"[CheckpointManager] Exported {len(df):,} records to {parquet_path}")
        return df


if __name__ == "__main__":
    mgr = IngestCheckpointManager()
    print(f"Total seen authors: {len(mgr.seen_authors)}")
