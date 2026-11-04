"""End-to-end pipeline runner CLI for personality2occupation.

Stages:
  1. download: Sourcing and downloading raw corpora (Blogger, Bluesky, Reddit/Arctic Shift).
  2. ingest: Text bounding, lexicon matching, and Ollama occupation extraction -> user_occupations_text.parquet.
  3. inference: 24D psychometric scoring (ModernBERT Big Five + Touché 2024 Schwartz values) -> user_occupations_personality.parquet.
  4. occupations: Title normalization, semantic clustering, divergence checks -> occupation_personality_variance_count.parquet.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="personality2occupation empirical dataset generation pipeline"
    )
    parser.add_argument(
        "--stage",
        choices=["all", "download", "ingest", "inference", "occupations"],
        default="all",
        help="Pipeline stage to execute (default: all)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Optional path to configuration file",
    )

    args = parser.parse_args()
    print(f"[personality2occupation] Selected stage: {args.stage}")
    # Pipeline stages will be wired up in subsequent milestones.


if __name__ == "__main__":
    main()
