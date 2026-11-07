"""
Dedicated Blogger Ingestion Pipeline with Multi-Threaded Ollama Verification:
1. Fast in-memory grouping of 681k posts by unique author 'id'.
2. Vectorized / Aho-Corasick screening -> `dataset/cache/candidates_blogger.jsonl`.
3. Parallel Ollama GPU verification -> `dataset/cache/verified_blogger.jsonl` (resumable with --continue).
4. Substantive text bounding [1,500 - 3,000] words (min 100 words) -> flushes to checkpoint & parquet.
"""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Set, cast
from tqdm import tqdm

from dataset.scripts.download.download_blogger import download_blogger
from dataset.scripts.ingest.lexicon import build_or_load_lexicon
from dataset.scripts.ingest.pass1_screen import extract_context_window
from dataset.scripts.ingest.pass2_extract import bound_text
from dataset.scripts.ingest.ollama_extractor import OllamaOccupationExtractor
from dataset.scripts.ingest.checkpoint_manager import IngestCheckpointManager


DEFAULT_CANDIDATES_BLOGGER = Path("dataset/cache/candidates_blogger.jsonl")
DEFAULT_VERIFIED_BLOGGER = Path("dataset/cache/verified_blogger.jsonl")


class BloggerIngestPipeline:
    def __init__(
        self,
        candidates_path: Path = DEFAULT_CANDIDATES_BLOGGER,
        verified_path: Path = DEFAULT_VERIFIED_BLOGGER,
        model_name: str = "granite4.1:3b",
    ):
        self.candidates_path = Path(candidates_path)
        self.verified_path = Path(verified_path)
        self.candidates_path.parent.mkdir(parents=True, exist_ok=True)
        self.verified_path.parent.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        self.mgr = IngestCheckpointManager()
        self.lex = build_or_load_lexicon()

    def step_1_screen_candidates(self, limit_authors: Optional[int] = None, resumable: bool = True) -> int:
        """Groups blog posts and screens with Aho-Corasick into candidates_blogger.jsonl."""
        seen_candidates: Set[str] = set()
        if resumable and self.candidates_path.exists():
            with open(self.candidates_path, "r", encoding="utf-8") as f:
                for line in f:
                    u = json.loads(line).get("user_id")
                    if u:
                        seen_candidates.add(u)
            print(f"[Blogger Step 1] Loaded {len(seen_candidates):,} already screened candidates.")

        print("\n" + "=" * 70)
        print("Blogger Step 1: In-Memory Post Grouping & Lexicon Screening")
        print(f"Candidates Output: {self.candidates_path}")
        print("=" * 70)

        ds = download_blogger()
        author_posts = defaultdict(list)
        print(f"[Blogger Step 1] Grouping {len(ds):,} posts by author ID...")
        for raw_row in ds:
            row = cast(Dict[str, Any], raw_row)
            uid = str(row["id"])
            t = (row.get("text") or "").strip()
            if t:
                author_posts[uid].append(t)

        all_authors = list(author_posts.keys())
        if limit_authors:
            all_authors = all_authors[:limit_authors]
        print(f"[Blogger Step 1] Screening {len(all_authors):,} unique authors...")

        new_count = 0
        with open(self.candidates_path, "a", encoding="utf-8") as writer:
            for uid in tqdm(all_authors, desc="Screening Blogger Authors"):
                if uid in seen_candidates or self.mgr.is_author_seen(uid):
                    continue

                posts = author_posts[uid]
                matched_kw = set()
                snippets = []
                for p in posts:
                    m = self.lex.match(p)
                    if m:
                        matched_kw.update(m)
                        if len(snippets) < 3:
                            snippets.append(extract_context_window(p, m[0]))

                if matched_kw and snippets:
                    rec = {
                        "user_id": uid,
                        "matched_keywords": sorted(list(matched_kw)),
                        "snippets": snippets,
                    }
                    writer.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    seen_candidates.add(uid)
                    new_count += 1
            writer.flush()

        print(f"[Blogger Step 1] Screening complete! Found {new_count:,} new candidates.")
        return new_count

    def step_2_verify_candidates(
        self,
        max_workers: int = 4,
        resumable: bool = True,
        max_candidates: Optional[int] = None,
    ) -> int:
        """Parallel multi-threaded Ollama evaluation of Blogger candidates."""
        if not self.candidates_path.exists():
            print(f"[Blogger Step 2] Candidates file not found at: {self.candidates_path}")
            return 0

        already_verified: Set[str] = set()
        if resumable and self.verified_path.exists():
            with open(self.verified_path, "r", encoding="utf-8") as f:
                for line in f:
                    u = json.loads(line).get("user_id")
                    if u:
                        already_verified.add(u)
            print(f"[Blogger Step 2] Loaded {len(already_verified):,} already verified authors from disk.")

        candidates = []
        with open(self.candidates_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                uid = rec.get("user_id")
                if uid and uid not in already_verified and not self.mgr.is_author_seen(uid):
                    candidates.append(rec)
                    if max_candidates and len(candidates) >= max_candidates:
                        break

        print("\n" + "=" * 70)
        print("Blogger Step 2: Parallelized Local Ollama Verification")
        print(f"Model: {self.model_name} | Workers: {max_workers}")
        print(f"Pending Candidates to Evaluate: {len(candidates):,}")
        print("=" * 70)

        if not candidates:
            print("[Blogger Step 2] No candidates pending verification.")
            return 0

        writer = open(self.verified_path, "a", encoding="utf-8")
        verified_count = 0

        def eval_candidate(cand: Dict) -> Optional[Dict]:
            extractor = OllamaOccupationExtractor(model=self.model_name)
            uid = cand["user_id"]
            snippets = cand.get("snippets", [])
            if not snippets:
                return None

            # Optimization: Evaluate combined snippets in 1 forward pass
            combined_text = "\n---\n".join(snippets[:3])
            extracted = extractor.extract(combined_text)

            if extracted:
                return {
                    "user_id": uid,
                    "occupations": sorted(list(set(extracted))),
                    "snippets": snippets,
                    "source": "blogger",
                }
            return None

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(eval_candidate, c): c for c in candidates}
                pbar = tqdm(
                    total=len(candidates),
                    desc=f"Ollama Verifying ({max_workers} threads)",
                    smoothing=0,
                    mininterval=1.0,
                    dynamic_ncols=True,
                )
                pbar.set_postfix({"verified": 0, "hit_rate": "0.0%"}, refresh=True)
                processed = 0
                for future in as_completed(futures):
                    res = future.result()
                    processed += 1
                    pbar.update(1)
                    if res:
                        writer.write(json.dumps(res, ensure_ascii=False) + "\n")
                        writer.flush()
                        verified_count += 1
                    hit_pct = f"{(verified_count / max(1, processed)):.1%}"
                    pbar.set_postfix({"verified": verified_count, "hit_rate": hit_pct}, refresh=False)
                pbar.close()
        finally:
            writer.close()

        print(f"[Blogger Step 2] Complete! Verified {verified_count:,} professional authors.")
        return verified_count

    def step_3_harvest_and_checkpoint(self, resumable: bool = True) -> int:
        """Pulls text for verified authors (reusing previous cache where available), bounds text, and checkpoints."""
        if not self.verified_path.exists():
            print(f"[Blogger Step 3] Verified file not found at {self.verified_path}")
            return 0

        verified_map: Dict[str, List[str]] = {}
        with open(self.verified_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                uid = rec.get("user_id")
                if uid and (not resumable or not self.mgr.is_author_seen(uid)):
                    verified_map[uid] = rec["occupations"]

        print("\n" + "=" * 70)
        print("Blogger Step 3: Text Bounding & Checkpoint Commit")
        print(f"Target Verified Authors to Harvest: {len(verified_map):,}")
        print("=" * 70)

        if not verified_map:
            print("[Blogger Step 3] All verified authors are already checkpointed.")
            return 0

        # Load text cache from previous harvests if available
        text_cache_path = Path("dataset/cache/blogger_text_cache.json")
        text_cache: Dict[str, Dict] = {}
        if text_cache_path.exists():
            try:
                with open(text_cache_path, "r", encoding="utf-8") as f:
                    text_cache = json.load(f)
                cached_hits = sum(1 for uid in verified_map if uid in text_cache)
                print(f"[Blogger Step 3] Reusing {cached_hits:,} pre-bounded texts from previous harvest cache.")
            except Exception as e:
                print(f"[Blogger Step 3] Note: Could not read text cache ({e}).")

        # For any verified authors NOT in cache, load from local corpus
        missing_uids = {uid for uid in verified_map if uid not in text_cache}
        author_posts = defaultdict(list)
        if missing_uids:
            print(f"[Blogger Step 3] Fetching corpus posts for {len(missing_uids):,} new verified authors...")
            ds = download_blogger()
            for raw_row in ds:
                row = cast(Dict[str, Any], raw_row)
                uid = str(row["id"])
                if uid in missing_uids:
                    t = (row.get("text") or "").strip()
                    if t:
                        author_posts[uid].append(t)

        committed_count = 0
        for uid, occs in tqdm(verified_map.items(), desc="Bounding & Checkpointing", dynamic_ncols=True):
            if uid in text_cache:
                cached = text_cache[uid]
                profile = {
                    "user_id": uid,
                    "occupations": occs,
                    "text": cached.get("text", ""),
                    "word_count": cached.get("word_count", len(cached.get("text", "").split())),
                    "source": "blogger",
                }
                self.mgr.append_record(profile)
                committed_count += 1
            else:
                posts = author_posts.get(uid, [])
                bounded = bound_text(posts)
                if bounded:
                    profile = {
                        "user_id": uid,
                        "occupations": occs,
                        "text": bounded,
                        "word_count": len(bounded.split()),
                        "source": "blogger",
                    }
                    self.mgr.append_record(profile)
                    committed_count += 1

        if committed_count > 0:
            target_parquet = Path("dataset/user_occupations_text.parquet")
            self.mgr.export_to_parquet(target_parquet)
            print(f"[Blogger Step 3] Updated final parquet at {target_parquet} with latest records.")

        print(f"[Blogger Step 3] Complete! Checkpointed {committed_count:,} profiles.")
        return committed_count

    def run_all(self, max_workers: int = 4, limit_authors: Optional[int] = None, resumable: bool = True):
        self.step_1_screen_candidates(limit_authors=limit_authors, resumable=resumable)
        self.step_2_verify_candidates(max_workers=max_workers, resumable=resumable)
        self.step_3_harvest_and_checkpoint(resumable=resumable)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Blogger Ingestion Pipeline")
    parser.add_argument("--step", choices=["1", "2", "3", "all"], default="all", help="Pipeline step to run")
    parser.add_argument("--workers", type=int, default=8, help="Parallel Ollama threads (default: 8)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of authors")
    parser.add_argument("--continue", dest="cont", action="store_true", default=True, help="Resume from disk caches")
    args = parser.parse_args()

    pipeline = BloggerIngestPipeline()
    if args.step == "1":
        pipeline.step_1_screen_candidates(limit_authors=args.limit, resumable=args.cont)
    elif args.step == "2":
        pipeline.step_2_verify_candidates(max_workers=args.workers, resumable=args.cont, max_candidates=args.limit)
    elif args.step == "3":
        pipeline.step_3_harvest_and_checkpoint(resumable=args.cont)
    else:
        pipeline.run_all(max_workers=args.workers, limit_authors=args.limit, resumable=args.cont)
