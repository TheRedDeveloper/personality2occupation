"""
Unified Master Orchestrator for the Occupation & Personality Pipeline.

Stages:
  - Reddit:
      Stage A (Screening): Parquet streaming with fast column scanning -> `dataset/cache/candidates_reddit.jsonl`
      Stage B (Verification): Parallelized Ollama (granite4.1:3b) -> `dataset/cache/verified_professionals.jsonl`
      Stage C (Harvesting): Multi-threaded Arctic Shift personality text -> checkpoint & Parquet
  - Blogger:
      Screening -> Parallel Ollama -> Text bounding & checkpoint
  - Bluesky:
      searchActors -> Profile Bios -> Parallel Ollama -> Author Feed Harvest & checkpoint
  - Export:
      Exports current checkpoint directly to `dataset/user_occupations_text.parquet`

Supports:
  --stage [all|a|b|c|bluesky|blogger|export]
  --continue: Resumes from disk caches
  --workers: Worker thread concurrency
"""

import argparse
from pathlib import Path

from dataset.scripts.ingest.stage_a_screen import RedditScreeningStage
from dataset.scripts.ingest.stage_b_verify import ParallelOllamaVerificationStage
from dataset.scripts.ingest.stage_c_harvest import PersonalityHarvestStage
from dataset.scripts.ingest.ingest_blogger import BloggerIngestPipeline
from dataset.scripts.ingest.ingest_bluesky import BlueskyIngestPipeline
from dataset.scripts.ingest.checkpoint_manager import IngestCheckpointManager


DEFAULT_TARGET_PARQUET = Path("dataset/user_occupations_text.parquet")


def main():
    parser = argparse.ArgumentParser(description="Unified Occupation & Personality Pipeline Orchestrator")
    parser.add_argument(
        "--stage",
        choices=["all", "a", "b", "c", "bluesky", "blogger", "export"],
        default="all",
        help="Pipeline stage to execute",
    )
    parser.add_argument(
        "--continue",
        dest="resume",
        action="store_true",
        default=True,
        help="Resume from last checkpoint (skipping already processed items)",
    )
    parser.add_argument("--test", action="store_true", help="Run in test mode on small sample batches")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel worker threads")
    parser.add_argument("--dest", type=Path, default=DEFAULT_TARGET_PARQUET, help="Final target Parquet path")
    args = parser.parse_args()

    print("=" * 70)
    print(f"Empirical Occupation-Personality Pipeline: Stage '{args.stage.upper()}'")
    print(f"Mode: {'TEST' if args.test else 'PRODUCTION'} | Resumable: {args.resume}")
    print("=" * 70)

    mgr = IngestCheckpointManager()

    # --- Reddit Stage A: Screening ---
    if args.stage in ("all", "a"):
        stage_a = RedditScreeningStage()
        stage_a.run(
            max_subreddits=3 if args.test else None,
            resume=args.resume,
        )

    # --- Reddit Stage B: Ollama Verification ---
    if args.stage in ("all", "b"):
        stage_b = ParallelOllamaVerificationStage()
        stage_b.run(
            max_workers=args.workers,
            max_candidates=25 if args.test else None,
        )

    # --- Reddit Stage C: Arctic Shift Cross-Subreddit Harvest ---
    if args.stage in ("all", "c"):
        stage_c = PersonalityHarvestStage(checkpoint_mgr=mgr, target_parquet=args.dest)
        stage_c.run(
            max_workers=args.workers,
            limit=10 if args.test else None,
        )

    # --- Blogger Pipeline ---
    if args.stage in ("all", "blogger"):
        blogger_pipe = BloggerIngestPipeline()
        blogger_pipe.run_all(
            max_workers=args.workers,
            limit_authors=100 if args.test else None,
            resumable=args.resume,
        )

    # --- Bluesky Pipeline ---
    if args.stage in ("all", "bluesky"):
        bluesky_pipe = BlueskyIngestPipeline()
        bluesky_pipe.run_all(
            max_terms=10 if args.test else None,
            max_workers=args.workers,
            resumable=args.resume,
        )

    # --- Export / Parquet Compilation ---
    if args.stage in ("all", "export"):
        df = mgr.export_to_parquet(args.dest)
        print(f"\n[Pipeline] Parquet exported successfully to {args.dest}: {len(df):,} total profiles.")

    print("\n[Pipeline] Execution completed.")


if __name__ == "__main__":
    main()
