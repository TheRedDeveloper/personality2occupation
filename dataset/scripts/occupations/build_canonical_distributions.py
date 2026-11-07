"""Aggregate user 24D personality distributions by canonical occupation.

Step 4 of Milestone 5:
1. Loads user personalities and self-reported occupations from user_occupations_personality.parquet.
2. Normalizes raw titles and maps them to Stage 2 canonical occupations via divergence_split_mapping.json.
3. Associates each user's continuous 24D personality vector with their unique canonical occupations.
4. Filters out canonical occupations with fewer than min_sample_count users (default: N < 10).
5. Computes the 24D empirical mean vector and diagonal variance vector for each canonical occupation.
6. Exports the target table to dataset/occupation_personality_variance_count.parquet.
"""

import argparse
import json
import logging
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

# Ensure project root is in sys.path
project_root = str(Path(__file__).resolve().parents[3])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dataset.scripts.occupations.normalize import normalize_title

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Dimension names: Big Five (5) + Schwartz Values (19)
BIG5_TRAITS = ["Openness", "Conscientiousness", "Extraversion", "Agreeableness", "Neuroticism"]
SCHWARTZ_VALUES = [
    "Security-personal", "Security-societal", "Tradition", "Conformity-rules", "Conformity-interpersonal",
    "Humility", "Benevolence-caring", "Benevolence-dependability", "Universalism-concern", "Universalism-nature",
    "Universalism-tolerance", "Self-direction-thought", "Self-direction-action", "Stimulation", "Hedonism",
    "Achievement", "Power-dominance", "Power-resources", "Face"
]
ALL_DIMENSIONS = BIG5_TRAITS + SCHWARTZ_VALUES


def compute_canonical_distributions(
    parquet_path: str = "dataset/user_occupations_personality.parquet",
    mapping_path: str = "dataset/cache/divergence_split_mapping.json",
    min_sample_count: int = 10,
    ddof: int = 1,
) -> pa.Table:
    """Compute mean vector and diagonal variance vector for all canonical occupations with N >= min_sample_count.
    
    Args:
        parquet_path: Path to user personalities parquet.
        mapping_path: Path to Stage 2 canonical mapping JSON.
        min_sample_count: Minimum unique user count threshold (default: 10).
        ddof: Degrees of freedom for sample variance (default: 1 for unbiased estimator).
        
    Returns:
        PyArrow Table containing [canonical_occupation, sample_count, mean, variance].
    """
    logger.info(f"Loading Stage 2 canonical mapping from {mapping_path}...")
    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    # Invert mapping: member_title -> canonical_occupation
    cleaned_to_canonical = {}
    for canon, members in mapping.items():
        for m in members:
            cleaned_to_canonical[m] = canon

    logger.info(f"Loading user personalities from {parquet_path}...")
    table = pq.read_table(parquet_path, columns=["user_id", "occupations", "personality_vector"])
    df = table.to_pandas()

    canonical_vectors = defaultdict(list)

    t0 = time.time()
    for _, row in df.iterrows():
        p_vec = np.array(row["personality_vector"], dtype=np.float32)
        # Deduplicate canonical occupations for this user
        user_canons = set()
        for raw in row["occupations"]:
            cleaned = normalize_title(raw)
            if cleaned:
                canon = cleaned_to_canonical.get(cleaned)
                if canon:
                    user_canons.add(canon)

        for canon in user_canons:
            canonical_vectors[canon].append(p_vec)

    total_associations = sum(len(v) for v in canonical_vectors.values())
    logger.info(
        f"Aggregated {total_associations} user-job associations across "
        f"{len(canonical_vectors)} canonical occupations in {time.time() - t0:.2f}s."
    )

    # Filter canonical occupations by sample count threshold
    eligible_canons = [c for c, vecs in canonical_vectors.items() if len(vecs) >= min_sample_count]
    discarded_canons = len(canonical_vectors) - len(eligible_canons)
    retained_associations = sum(len(canonical_vectors[c]) for c in eligible_canons)

    logger.info(
        f"Retained {len(eligible_canons)} canonical occupations with N >= {min_sample_count} "
        f"({retained_associations} / {total_associations} author associations, "
        f"{retained_associations / max(total_associations, 1) * 100:.2f}% coverage). "
        f"Discarded {discarded_canons} low-sample occupations."
    )

    # Sort occupations by sample count descending
    eligible_canons.sort(key=lambda c: len(canonical_vectors[c]), reverse=True)

    records_occupation = []
    records_count = []
    records_mean = []
    records_variance = []

    for canon in eligible_canons:
        vecs = np.array(canonical_vectors[canon], dtype=np.float32) # [N, 24]
        n_users = len(vecs)
        
        mean_vec = np.mean(vecs, axis=0).astype(np.float32).tolist()
        var_vec = np.var(vecs, axis=0, ddof=ddof).astype(np.float32).tolist()

        records_occupation.append(canon)
        records_count.append(n_users)
        records_mean.append(mean_vec)
        records_variance.append(var_vec)

    # Define PyArrow Schema
    schema = pa.schema([
        pa.field("canonical_occupation", pa.string(), nullable=False),
        pa.field("sample_count", pa.int64(), nullable=False),
        pa.field("mean", pa.list_(pa.float32()), nullable=False),
        pa.field("variance", pa.list_(pa.float32()), nullable=False),
    ])

    pa_table = pa.Table.from_arrays([
        pa.array(records_occupation, type=pa.string()),
        pa.array(records_count, type=pa.int64()),
        pa.array(records_mean, type=pa.list_(pa.float32())),
        pa.array(records_variance, type=pa.list_(pa.float32())),
    ], schema=schema)

    return pa_table


def export_canonical_distributions_parquet(
    parquet_path: str = "dataset/user_occupations_personality.parquet",
    mapping_path: str = "dataset/cache/divergence_split_mapping.json",
    output_parquet_path: str = "dataset/occupation_personality_variance_count.parquet",
    min_sample_count: int = 10,
    ddof: int = 1,
) -> pa.Table:
    """Compute and save the final target canonical distributions parquet file."""
    pa_table = compute_canonical_distributions(
        parquet_path=parquet_path,
        mapping_path=mapping_path,
        min_sample_count=min_sample_count,
        ddof=ddof
    )

    os.makedirs(os.path.dirname(os.path.abspath(output_parquet_path)), exist_ok=True)
    pq.write_table(pa_table, output_parquet_path, compression="snappy")
    file_size_mb = os.path.getsize(output_parquet_path) / (1024 * 1024)
    logger.info(
        f"Saved final distribution table ({len(pa_table)} occupations) to "
        f"{output_parquet_path} ({file_size_mb:.2f} MB)."
    )
    return pa_table


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build final Occupation-Personality-Variance-Count table.")
    parser.add_argument("--parquet", type=str, default="dataset/user_occupations_personality.parquet", help="Path to user personality parquet.")
    parser.add_argument("--mapping", type=str, default="dataset/cache/divergence_split_mapping.json", help="Path to Stage 2 canonical mapping.")
    parser.add_argument("--output", type=str, default="dataset/occupation_personality_variance_count.parquet", help="Path to output target parquet.")
    parser.add_argument("--min-samples", type=int, default=10, help="Minimum sample count per occupation (default: 10).")
    parser.add_argument("--ddof", type=int, default=1, help="Delta degrees of freedom for variance (default: 1).")

    args = parser.parse_args()
    export_canonical_distributions_parquet(
        parquet_path=args.parquet,
        mapping_path=args.mapping,
        output_parquet_path=args.output,
        min_sample_count=args.min_samples,
        ddof=args.ddof
    )
