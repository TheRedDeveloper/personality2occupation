#!/usr/bin/env python3
"""
Step 3: Fast Assembler & Parquet Join.

Joins the Step 1 Big Five trait cache (5D) and Step 2 Schwartz Human Values cache (19D)
with the base text dataset (dataset/user_occupations_text.parquet) into the final
target table: dataset/user_occupations_personality.parquet.

Target Schema:
- user_id: str
- occupations: List[str]
- personality_vector: List[float] (len 24: indices 0-4 Big Five, indices 5-23 Schwartz values)
- word_count: int
- source: str

Execution Time: ~5-10 seconds for 100k authors.
"""

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Any

# Ensure repository root is on sys.path
ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pyarrow as pa
import pyarrow.parquet as pq

DEFAULT_TEXT_PARQUET = Path("dataset/user_occupations_text.parquet")
DEFAULT_BIG5_CHECKPOINT = Path("dataset/cache/personality_big5_checkpoint.jsonl")
DEFAULT_VALUES_CHECKPOINT = Path("dataset/cache/personality_values_checkpoint.jsonl")
DEFAULT_OUTPUT_PARQUET = Path("dataset/user_occupations_personality.parquet")

BIG5_NAMES = ["Openness", "Conscientiousness", "Extraversion", "Agreeableness", "Neuroticism"]
VALUES_NAMES = [
    "Self-direction: thought", "Self-direction: action", "Stimulation",
    "Hedonism", "Achievement", "Power: dominance", "Power: resources",
    "Face", "Security: personal", "Security: societal", "Tradition",
    "Conformity: rules", "Conformity: interpersonal", "Humility",
    "Benevolence: caring", "Benevolence: dependability", "Universalism: concern",
    "Universalism: nature", "Universalism: tolerance"
]


def load_jsonl_cache(path: Path, score_key: str, expected_len: int) -> Dict[str, List[float]]:
    """Loads a checkpoint JSONL file into a dict {user_id: [scores]} with dimension checks."""
    if not path.exists():
        print(f"Warning: Checkpoint file does not exist: {path}", file=sys.stderr)
        return {}

    cache: Dict[str, List[float]] = {}
    print(f"Loading checkpoint cache from {path}...")
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                uid = record.get("user_id")
                scores = record.get(score_key)
                if uid and scores is not None:
                    if len(scores) != expected_len:
                        print(f"Warning: Line {line_no} has length {len(scores)} != {expected_len}, skipping", file=sys.stderr)
                        continue
                    cache[uid] = scores
            except json.JSONDecodeError:
                continue
    print(f"Loaded {len(cache):,} valid records from {path.name}")
    return cache


def main():
    parser = argparse.ArgumentParser(description="Step 3: Fast Assembler & Parquet Join")
    parser.add_argument("--text-parquet", type=Path, default=DEFAULT_TEXT_PARQUET, help="Path to user text parquet")
    parser.add_argument("--big5-checkpoint", type=Path, default=DEFAULT_BIG5_CHECKPOINT, help="Path to Big5 jsonl")
    parser.add_argument("--values-checkpoint", type=Path, default=DEFAULT_VALUES_CHECKPOINT, help="Path to Values jsonl")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PARQUET, help="Target personality parquet")
    args = parser.parse_args()

    if not args.text_parquet.exists():
        print(f"Error: Base parquet file not found at {args.text_parquet}", file=sys.stderr)
        sys.exit(1)

    # 1. Load checkpoints
    big5_map = load_jsonl_cache(args.big5_checkpoint, "big5", expected_len=5)
    values_map = load_jsonl_cache(args.values_checkpoint, "values", expected_len=19)

    if not big5_map or not values_map:
        print("Error: One or both checkpoint caches are empty. Run Step 1 and Step 2 first.", file=sys.stderr)
        sys.exit(1)

    # 2. Read base text table
    print(f"Reading base text parquet {args.text_parquet}...")
    text_table = pq.read_table(args.text_parquet, columns=["user_id", "occupations", "word_count", "source"])
    
    uids: List[str] = text_table.column("user_id").to_pylist()
    occupations_list: List[List[str]] = text_table.column("occupations").to_pylist()
    word_counts: List[int] = text_table.column("word_count").to_pylist()
    sources: List[str] = text_table.column("source").to_pylist()

    # 3. Inner-join on user_id
    out_uids: List[str] = []
    out_occupations: List[List[str]] = []
    out_vectors: List[List[float]] = []
    out_word_counts: List[int] = []
    out_sources: List[str] = []

    print("Joining Big Five (5D) and Schwartz Values (19D) into 24D personality vectors...")
    for uid, occs, wc, src in zip(uids, occupations_list, word_counts, sources):
        if uid in big5_map and uid in values_map:
            b5 = big5_map[uid]
            val = values_map[uid]
            vec_24 = b5 + val

            # Validation: ensure 24 dimensions and valid range
            if len(vec_24) != 24:
                continue
            if any(math.isnan(x) or math.isinf(x) for x in vec_24):
                continue
            # Clamping guarantee
            clamped_vec = [round(max(0.0, min(1.0, float(x))), 4) for x in vec_24]

            out_uids.append(uid)
            out_occupations.append(occs)
            out_vectors.append(clamped_vec)
            out_word_counts.append(wc)
            out_sources.append(src)

    total_joined = len(out_uids)
    print(f"Successfully joined {total_joined:,} authors with complete 24D profiles.")

    if total_joined == 0:
        print("Error: No intersecting authors found between datasets and checkpoints.", file=sys.stderr)
        sys.exit(1)

    # 4. Construct PyArrow table
    schema = pa.schema([
        ("user_id", pa.string()),
        ("occupations", pa.list_(pa.string())),
        ("personality_vector", pa.list_(pa.float32())),
        ("word_count", pa.int64()),
        ("source", pa.string()),
    ])

    out_table = pa.Table.from_arrays([
        pa.array(out_uids, type=pa.string()),
        pa.array(out_occupations, type=pa.list_(pa.string())),
        pa.array(out_vectors, type=pa.list_(pa.float32())),
        pa.array(out_word_counts, type=pa.int64()),
        pa.array(out_sources, type=pa.string()),
    ], schema=schema)

    # 5. Write to parquet
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(out_table, args.output, compression="snappy")
    print(f"Wrote target table to {args.output} ({args.output.stat().st_size / (1024*1024):.2f} MB)")

    # 6. Statistical Health Check
    print("\n--- Statistical Health Check (First 5 Authors Preview) ---")
    for i in range(min(5, total_joined)):
        print(f"Author: {out_uids[i]} | Occupations: {out_occupations[i]} | Source: {out_sources[i]}")
        print(f"  Big5: {out_vectors[i][:5]}")
        print(f"  Schwartz Values (first 5): {out_vectors[i][5:10]}...")

    print("\nStep 3 Assembler & Parquet Join finished successfully!")


if __name__ == "__main__":
    main()
