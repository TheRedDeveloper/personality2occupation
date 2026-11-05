"""
Stage B: Parallelized Local Ollama Batch Inference.
Reads candidate snippets from `dataset/cache/candidates_reddit.jsonl`.
Evaluates candidates using concurrent worker threads hitting local Ollama (granite4.1:3b)
with strict JSON array schema enforcement.
Writes verified professionals immediately to `dataset/cache/verified_professionals.jsonl`.
Supports:
  --workers: Number of concurrent threads (default: 4, can scale to 8)
  --continue: Automatically skips already verified authors
"""

import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import json
from pathlib import Path
import time
from typing import Dict, List, Optional, Set
from tqdm import tqdm
from dataset.scripts.ingest.ollama_extractor import OllamaOccupationExtractor


DEFAULT_CANDIDATES_INPUT = Path("dataset/cache/candidates_reddit.jsonl")
DEFAULT_VERIFIED_OUTPUT = Path("dataset/cache/verified_professionals.jsonl")
DEFAULT_EVALUATED_OUTPUT = Path("dataset/cache/reddit_evaluated_uids.txt")


class ParallelOllamaVerificationStage:
    """Stage B: Multi-threaded GPU verification of occupational candidates."""

    def __init__(
        self,
        model_name: str = "granite4.1:3b",
        candidates_input: Path = DEFAULT_CANDIDATES_INPUT,
        verified_output: Path = DEFAULT_VERIFIED_OUTPUT,
        evaluated_output: Path = DEFAULT_EVALUATED_OUTPUT,
    ):
        self.model_name = model_name
        self.candidates_input = Path(candidates_input)
        self.verified_output = Path(verified_output)
        self.evaluated_output = Path(evaluated_output)
        self.verified_output.parent.mkdir(parents=True, exist_ok=True)
        self.already_verified_authors: Set[str] = set()
        self.already_evaluated_uids: Set[str] = set()
        self._load_existing_verified()
        self._load_existing_evaluated()

    def _load_existing_verified(self):
        if self.verified_output.exists():
            try:
                with open(self.verified_output, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            rec = json.loads(line)
                            u = rec.get("user_id")
                            if u:
                                self.already_verified_authors.add(u)
            except Exception as e:
                print(f"[Stage B] Error loading existing verified authors: {e}")
        print(f"[Stage B] Loaded {len(self.already_verified_authors):,} already verified authors from disk.")

    def _load_existing_evaluated(self):
        if self.evaluated_output.exists():
            try:
                with open(self.evaluated_output, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            self.already_evaluated_uids.add(line)
            except Exception as e:
                print(f"[Stage B] Error loading evaluated uids: {e}")
        print(f"[Stage B] Loaded {len(self.already_evaluated_uids):,} already evaluated uids from disk.")

    def run(
        self,
        max_workers: int = 4,
        max_candidates: Optional[int] = None,
        batch_size: int = 200,
    ) -> int:
        """Processes candidates through concurrent Ollama workers and flushes verified hits."""
        if not self.candidates_input.exists():
            print(f"[Stage B] Candidates file not found at: {self.candidates_input}")
            return 0

        writer = open(self.verified_output, "a", encoding="utf-8")
        eval_writer = open(self.evaluated_output, "a", encoding="utf-8")
        total_processed = 0
        total_verified = 0
        t0 = time.time()

        print("\n" + "=" * 70)
        print("Stage B: Parallelized Local Ollama Verification")
        print(f"Model: {self.model_name} | Parallel Workers: {max_workers}")
        print(f"Reading: {self.candidates_input}")
        print(f"Writing: {self.verified_output}")
        print(f"Tracking Evaluated: {self.evaluated_output}")
        print(f"Skipping: {len(self.already_evaluated_uids):,} already evaluated authors")
        print("=" * 70)

        # Worker function: creates an extractor instance per thread
        def verify_candidate(cand_item: Dict) -> tuple[Optional[Dict], str]:
            extractor = OllamaOccupationExtractor(model=self.model_name)
            user_id = cand_item.get("user_id") or ""
            snippets = cand_item.get("context_snippets", [])
            if not snippets:
                return None, user_id

            # Optimization: Combine up to 3 snippets into a single forward pass (~3x speedup)
            combined_text = "\n---\n".join(snippets[:3])
            extracted = extractor.extract(combined_text)

            if extracted:
                return {
                    "user_id": user_id,
                    "occupations": sorted(list(set(extracted))),
                    "source": cand_item.get("source", "reddit"),
                    "sample_snippet": snippets[0],
                }, user_id
            return None, user_id

        TOTAL_REDDIT_CANDIDATES = 1899522
        total_remaining = max_candidates if max_candidates else max(0, TOTAL_REDDIT_CANDIDATES - len(self.already_evaluated_uids))

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                with open(self.candidates_input, "r", encoding="utf-8") as f:
                    futures = set()
                    pbar = tqdm(
                        total=total_remaining,
                        desc=f"Verifying Reddit ({max_workers} threads)",
                        unit="cand",
                        smoothing=0,
                        mininterval=1.0,
                        dynamic_ncols=True,
                    )
                    pbar.set_postfix({"verified": total_verified, "hit_rate": "0.0%"}, refresh=True)

                    for line in f:
                        if not line.strip():
                            continue
                        cand = json.loads(line)
                        user_id = cand.get("user_id")

                        if user_id in self.already_evaluated_uids or user_id in self.already_verified_authors:
                            continue

                        futures.add(executor.submit(verify_candidate, cand))

                        # Keep buffer size around max_workers * 10 to stream smoothly
                        if len(futures) >= max_workers * 10:
                            # Wait for at least one to complete
                            done, futures = concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_COMPLETED)
                            for fut in done:
                                total_processed += 1
                                pbar.update(1)
                                res, uid = fut.result()
                                if uid:
                                    eval_writer.write(uid + "\n")
                                    self.already_evaluated_uids.add(uid)
                                if res:
                                    writer.write(json.dumps(res, ensure_ascii=False) + "\n")
                                    writer.flush()
                                    self.already_verified_authors.add(res["user_id"])
                                    total_verified += 1
                                if total_processed % 50 == 0:
                                    eval_writer.flush()
                                hit_pct = f"{(total_verified / max(1, total_processed)):.1%}"
                                pbar.set_postfix({"verified": total_verified, "hit_rate": hit_pct}, refresh=False)

                        if max_candidates and total_processed >= max_candidates:
                            break

                    # Drain remaining futures
                    for fut in as_completed(futures):
                        total_processed += 1
                        pbar.update(1)
                        res, uid = fut.result()
                        if uid:
                            eval_writer.write(uid + "\n")
                            self.already_evaluated_uids.add(uid)
                        if res:
                            writer.write(json.dumps(res, ensure_ascii=False) + "\n")
                            writer.flush()
                            self.already_verified_authors.add(res["user_id"])
                            total_verified += 1
                        hit_pct = f"{(total_verified / max(1, total_processed)):.1%}"
                        pbar.set_postfix({"verified": total_verified, "hit_rate": hit_pct}, refresh=False)

                    pbar.close()
        finally:
            writer.close()
            eval_writer.close()

        elapsed = round(time.time() - t0, 1)
        print(f"\n[Stage B] Finished! Processed {total_processed:,} candidates in {elapsed}s. Verified {total_verified:,} professionals.")
        return total_verified


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage B Parallelized Ollama Verification")
    parser.add_argument("--workers", type=int, default=8, help="Number of concurrent worker threads (default: 8)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of candidates to process")
    args = parser.parse_args()

    stage_b = ParallelOllamaVerificationStage()
    stage_b.run(max_workers=args.workers, max_candidates=args.limit)
