#!/usr/bin/env python3
"""Anonymize user-level Parquet datasets for public release under Zero-BSD.

Transforms:
1. dataset/user_occupations_text.parquet -> dataset/occupations_text.parquet
2. dataset/user_occupations_personality.parquet -> dataset/occupations_personality.parquet

Anonymization protocol:
- Replaces raw platform handles/usernames (Reddit, Bluesky, Blogger) with clean,
  consistent pseudonymous identifiers (e.g. 'u_000001').
- Shuffles the user ordering using a fixed random seed to decouple the published
  record order from the original scraping order.
- Applies the exact same ID mapping across both tables to preserve 1:1 joinability
  between the text corpus and the 24D personality vectors for researchers.
- Filters out the 37 corrupted/empty-text records that failed psychometric validation,
  leaving exactly 111,472 validated, complete profiles in both datasets.
"""

import argparse
import hashlib
import logging
import os
from pathlib import Path
import random
import time

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_INPUT_TEXT = "dataset/user_occupations_text.parquet"
DEFAULT_INPUT_PERS = "dataset/user_occupations_personality.parquet"
DEFAULT_OUTPUT_TEXT = "dataset/occupations_text.parquet"
DEFAULT_OUTPUT_PERS = "dataset/occupations_personality.parquet"


def anonymize_datasets(
    input_text_path: str = DEFAULT_INPUT_TEXT,
    input_pers_path: str = DEFAULT_INPUT_PERS,
    output_text_path: str = DEFAULT_OUTPUT_TEXT,
    output_pers_path: str = DEFAULT_OUTPUT_PERS,
    seed: int = 42,
) -> None:
    """Read raw user datasets, generate consistent anonymized IDs, and write public parquets."""
    t0 = time.time()
    logger.info("Starting dataset anonymization pipeline...")

    # 1. Read input tables
    logger.info(f"Loading personality dataset from {input_pers_path}...")
    tbl_pers = pq.read_table(input_pers_path)
    logger.info(f"Loaded {tbl_pers.num_rows:,} personality rows.")

    logger.info(f"Loading text dataset from {input_text_path}...")
    tbl_text = pq.read_table(input_text_path)
    logger.info(f"Loaded {tbl_text.num_rows:,} text rows.")

    # 2. Identify the valid, intersection user set
    uids_pers = tbl_pers.column("user_id").to_pylist()
    valid_uids_set = set(uids_pers)
    logger.info(f"Unique validated users in personality table: {len(valid_uids_set):,}")

    # 3. Create deterministic pseudo-random shuffling of user IDs
    # Sorting first guarantees reproducible shuffle across runs with the same seed
    sorted_uids = sorted(list(valid_uids_set))
    rng = random.Random(seed)
    shuffled_uids = list(sorted_uids)
    rng.shuffle(shuffled_uids)

    # Assign clean anonymous IDs: u_000001, u_000002, ...
    uid_to_anon = {raw_uid: f"u_{idx + 1:06d}" for idx, raw_uid in enumerate(shuffled_uids)}
    logger.info(f"Generated {len(uid_to_anon):,} anonymous user IDs (u_000001 to u_{len(uid_to_anon):06d}).")

    # -------------------------------------------------------------
    # 4. Anonymize and Export Personality Table
    # -------------------------------------------------------------
    logger.info("Processing occupations_personality.parquet...")
    pers_raw_uids = tbl_pers.column("user_id").to_pylist()
    pers_anon_uids = [uid_to_anon[u] for u in pers_raw_uids]

    # Build anonymized PyArrow Table
    anon_tbl_pers = pa.Table.from_arrays([
        pa.array(pers_anon_uids, type=pa.string()),
        tbl_pers.column("occupations"),
        tbl_pers.column("personality_vector"),
        tbl_pers.column("word_count"),
        tbl_pers.column("source"),
    ], names=["user_id", "occupations", "personality_vector", "word_count", "source"])

    # Sort table by anonymous user_id
    sort_indices_pers = np.argsort(pers_anon_uids)
    anon_tbl_pers = anon_tbl_pers.take(sort_indices_pers)

    os.makedirs(os.path.dirname(os.path.abspath(output_pers_path)), exist_ok=True)
    pq.write_table(anon_tbl_pers, output_pers_path, compression="snappy")
    pers_size_mb = os.path.getsize(output_pers_path) / (1024 * 1024)
    logger.info(
        f"Exported {anon_tbl_pers.num_rows:,} rows to {output_pers_path} "
        f"({pers_size_mb:.2f} MB)."
    )

    # -------------------------------------------------------------
    # 5. Anonymize and Export Text Table
    # -------------------------------------------------------------
    logger.info("Processing occupations_text.parquet...")
    text_raw_uids = tbl_text.column("user_id").to_pylist()

    # Filter text table to the valid 111,472 users and map IDs
    keep_indices = []
    text_anon_uids = []
    for idx, raw_u in enumerate(text_raw_uids):
        if raw_u in uid_to_anon:
            keep_indices.append(idx)
            text_anon_uids.append(uid_to_anon[raw_u])

    logger.info(
        f"Retained {len(keep_indices):,} / {len(text_raw_uids):,} text records "
        f"(dropped {len(text_raw_uids) - len(keep_indices)} invalid records)."
    )

    filtered_text_tbl = tbl_text.take(keep_indices)
    anon_tbl_text = pa.Table.from_arrays([
        pa.array(text_anon_uids, type=pa.string()),
        filtered_text_tbl.column("occupations"),
        filtered_text_tbl.column("text"),
        filtered_text_tbl.column("word_count"),
        filtered_text_tbl.column("source"),
    ], names=["user_id", "occupations", "text", "word_count", "source"])

    # Sort table by anonymous user_id to match personality ordering
    sort_indices_text = np.argsort(text_anon_uids)
    anon_tbl_text = anon_tbl_text.take(sort_indices_text)

    os.makedirs(os.path.dirname(os.path.abspath(output_text_path)), exist_ok=True)
    pq.write_table(anon_tbl_text, output_text_path, compression="snappy")
    text_size_mb = os.path.getsize(output_text_path) / (1024 * 1024)
    logger.info(
        f"Exported {anon_tbl_text.num_rows:,} rows to {output_text_path} "
        f"({text_size_mb:.2f} MB)."
    )

    # -------------------------------------------------------------
    # 6. Verification
    # -------------------------------------------------------------
    logger.info("Verifying output consistency...")
    assert anon_tbl_pers.num_rows == anon_tbl_text.num_rows == 111472
    assert anon_tbl_pers.column("user_id").to_pylist() == anon_tbl_text.column("user_id").to_pylist()
    logger.info("1:1 alignment check PASSED: both tables share the exact same 111,472 anonymous IDs in identical order!")

    elapsed = time.time() - t0
    logger.info(f"Anonymization complete in {elapsed:.1f}s.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Anonymize user-level datasets for public release.")
    parser.add_argument("--input-text", default=DEFAULT_INPUT_TEXT, help="Path to user_occupations_text.parquet")
    parser.add_argument("--input-pers", default=DEFAULT_INPUT_PERS, help="Path to user_occupations_personality.parquet")
    parser.add_argument("--output-text", default=DEFAULT_OUTPUT_TEXT, help="Path to occupations_text.parquet")
    parser.add_argument("--output-pers", default=DEFAULT_OUTPUT_PERS, help="Path to occupations_personality.parquet")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic user shuffling")
    args = parser.parse_args()

    anonymize_datasets(
        input_text_path=args.input_text,
        input_pers_path=args.input_pers,
        output_text_path=args.output_text,
        output_pers_path=args.output_pers,
        seed=args.seed,
    )
