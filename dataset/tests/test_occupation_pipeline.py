"""End-to-end integration test for the occupation data pipeline.

Tests title normalization, semantic clustering, singleton absorption,
psychological divergence splitting, and personality distribution aggregation.
"""

import json
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from dataset.scripts.occupations.normalize import normalize_title, normalize_titles_list
from dataset.scripts.occupations.cluster import absorb_singletons, build_canonical_mapping
from dataset.scripts.occupations.divergence import (
    is_spelling_or_morphological_variant,
    check_subrole_divergence,
    evaluate_and_split_divergent_occupations,
)
from dataset.scripts.occupations.build_canonical_distributions import (
    compute_canonical_distributions,
    export_canonical_distributions_parquet,
)


def test_occupation_pipeline_end_to_end(tmp_path):
    """Verify the entire occupation processing and distribution pipeline end-to-end:
    
    1. Normalization: strips noise, symbols, seniority prefixes, and deduplicates.
    2. Singleton Absorption: absorbs typos and semantically close low-count titles.
    3. Divergence Check: splits genuine psychological divergence while guarding morphological variants.
    4. Distribution Aggregation: aggregates multi-occupation users, computes 24D mean & unbiased variance,
       filters N < threshold, and exports valid Parquet table.
    """
    # ---------------------------------------------------------
    # Step 1: Normalization
    # ---------------------------------------------------------
    raw_inputs = [
        "Doctor🩺Surgeon",
        "REALTOR®Agent",
        "Senior Software Engineer",
        "laywer",
        "lawyer",
        "game developer",
        "game programmer",
        "software dev",
        "software engineer",
    ]
    cleaned = [normalize_title(t) for t in raw_inputs]
    assert "doctor surgeon" in cleaned
    assert "realtor agent" in cleaned
    assert "software engineer" in cleaned
    assert "laywer" in cleaned

    # List deduplication and normalization
    user_raw_titles = ["Senior Software Engineer", "software engineer", "Doctor🩺Surgeon"]
    deduped = normalize_titles_list(user_raw_titles)
    assert deduped == ["software engineer", "doctor surgeon"]

    # ---------------------------------------------------------
    # Step 2: Singleton Absorption & Clustering
    # ---------------------------------------------------------
    # Initial mapping with anchors (N >= 10) and low-count orphans (N < 10)
    initial_mapping = {
        "lawyer": ["lawyer"],
        "software engineer": ["software engineer"],
        "game developer": ["game developer"],
        "laywer": ["laywer"],                      # Orphan typo
        "game programmer": ["game programmer"],    # Orphan sub-title
    }
    author_counts = {
        "lawyer": 50,
        "software engineer": 100,
        "game developer": 30,
        "laywer": 1,
        "game programmer": 5,
    }

    # Synthetic embeddings for singleton absorption
    # Vector layout: [lawyer_axis, swe_axis, gamedev_axis]
    embeddings = {
        "lawyer": np.array([1.0, 0.0, 0.0], dtype=np.float32),
        "software engineer": np.array([0.0, 1.0, 0.0], dtype=np.float32),
        "game developer": np.array([0.0, 0.0, 1.0], dtype=np.float32),
        "laywer": np.array([0.98, 0.0, 0.0], dtype=np.float32),  # Typo match
        "game programmer": np.array([0.0, 0.05, 0.99], dtype=np.float32),  # Close to game developer
    }

    stage1_mapping = absorb_singletons(
        canonical_mapping=initial_mapping,
        title_author_counts=author_counts,
        title_embeddings=embeddings,
        min_anchor_authors=10,
        relaxed_threshold=0.15,
        margin_ratio=0.88,
    )

    # 'laywer' absorbed into 'lawyer' (via typo/Damerau-Levenshtein)
    assert "laywer" in stage1_mapping["lawyer"]
    # 'game programmer' absorbed into 'game developer' (semantically close)
    assert "game programmer" in stage1_mapping["game developer"]

    # ---------------------------------------------------------
    # Step 3: Psychological Divergence Check
    # ---------------------------------------------------------
    # Morphological and abbreviation guards
    assert is_spelling_or_morphological_variant("software dev", "software developer") is True
    assert is_spelling_or_morphological_variant("game programmer", "game developer") is False

    # Simulate subrole divergence with standardized Z-scores
    np.random.seed(42)
    # Parent: game developer (N=30)
    parent_vecs = np.random.normal(loc=0.0, scale=1.0, size=(30, 24)).astype(np.float32)
    # Subrole: game programmer (N=15) with significant divergence on trait 0 (d > 0.5)
    divergent_vecs = np.random.normal(loc=0.0, scale=1.0, size=(15, 24)).astype(np.float32)
    divergent_vecs[:, 0] += 1.5  # Strong divergence

    diverges, divergent_traits = check_subrole_divergence(
        vecs_sub=divergent_vecs,
        vecs_rem=parent_vecs,
        min_cohens_d=0.5,
        p_val_threshold=0.01,
        min_sig_traits=1,
    )
    assert diverges is True
    assert len(divergent_traits) >= 1
    assert abs(divergent_traits[0]["cohens_d"]) > 1.0

    # Write Stage 2 mapping JSON
    stage2_mapping = {
        "lawyer": ["lawyer", "laywer"],
        "software engineer": ["software engineer", "software dev", "swe"],
        "game developer": ["game developer"],
        "game programmer": ["game programmer"],  # Split by divergence
    }
    stage2_path = tmp_path / "divergence_split_mapping.json"
    with open(stage2_path, "w", encoding="utf-8") as f:
        json.dump(stage2_mapping, f)

    # ---------------------------------------------------------
    # Step 4: Final Distribution Aggregation & Parquet Export
    # ---------------------------------------------------------
    # Create synthetic user dataset:
    # 15 users for 'game programmer' (N >= 10)
    # 12 users for 'software engineer' (N >= 10)
    # 10 users for 'lawyer' (N >= 10)
    # 5 users for 'game developer' (N = 5 < 10 -> will be filtered out)
    users_data = []

    # Game programmers
    for i in range(15):
        users_data.append({
            "user_id": f"gp_{i}",
            "occupations": ["game programmer"],
            "personality_vector": divergent_vecs[i].tolist(),
        })

    # Software engineers (including multi-title duplicate and multi-occupation author)
    users_data.append({
        "user_id": "swe_multi_title",
        "occupations": ["Software Engineer", "software dev"],  # Duplicate canonicals
        "personality_vector": np.random.normal(0, 1, 24).astype(np.float32).tolist(),
    })
    users_data.append({
        "user_id": "swe_multi_job",
        "occupations": ["Senior Software Engineer", "laywer"],  # Multi-occupation (swe + lawyer)
        "personality_vector": np.random.normal(0, 1, 24).astype(np.float32).tolist(),
    })
    for i in range(10):
        users_data.append({
            "user_id": f"swe_{i}",
            "occupations": ["swe"],
            "personality_vector": np.random.normal(0, 1, 24).astype(np.float32).tolist(),
        })

    # Lawyers (9 more users, total 10 including swe_multi_job)
    for i in range(9):
        users_data.append({
            "user_id": f"lawyer_{i}",
            "occupations": ["lawyer"],
            "personality_vector": np.random.normal(0, 1, 24).astype(np.float32).tolist(),
        })

    # Game developers (only 5 users, below min_samples=10)
    for i in range(5):
        users_data.append({
            "user_id": f"gamedev_{i}",
            "occupations": ["game developer"],
            "personality_vector": parent_vecs[i].tolist(),
        })

    user_table = pa.Table.from_pydict({
        "user_id": [u["user_id"] for u in users_data],
        "occupations": [u["occupations"] for u in users_data],
        "personality_vector": [u["personality_vector"] for u in users_data],
    })
    user_parquet_path = tmp_path / "user_occupations_personality.parquet"
    pq.write_table(user_table, user_parquet_path)

    output_parquet_path = tmp_path / "occupation_personality_variance_count.parquet"

    # Export canonical distribution table
    out_table = export_canonical_distributions_parquet(
        parquet_path=str(user_parquet_path),
        mapping_path=str(stage2_path),
        output_parquet_path=str(output_parquet_path),
        min_sample_count=10,
        ddof=1,
    )

    # Invariants verification
    assert len(out_table) == 3  # game programmer (15), software engineer (12), lawyer (10)
    canons = out_table["canonical_occupation"].to_pylist()
    counts = dict(zip(canons, out_table["sample_count"].to_pylist()))

    assert "game programmer" in canons and counts["game programmer"] == 15
    assert "software engineer" in canons and counts["software engineer"] == 12
    assert "lawyer" in canons and counts["lawyer"] == 10
    assert "game developer" not in canons  # Filtered out (N=5 < 10)

    # Schema verification
    assert out_table.schema.names == ["canonical_occupation", "sample_count", "mean", "variance"]
    assert out_table.schema.field("sample_count").type == pa.int64()
    assert out_table.schema.field("mean").type == pa.list_(pa.float32())
    assert out_table.schema.field("variance").type == pa.list_(pa.float32())

    # Check analytical mean & variance for game programmer
    df_out = out_table.to_pandas().set_index("canonical_occupation")
    gp_mean = np.array(df_out.loc["game programmer", "mean"])
    gp_var = np.array(df_out.loc["game programmer", "variance"])
    expected_gp_mean = np.mean(divergent_vecs, axis=0)
    expected_gp_var = np.var(divergent_vecs, axis=0, ddof=1)

    np.testing.assert_allclose(gp_mean, expected_gp_mean, rtol=1e-5, atol=1e-5)
    np.testing.assert_allclose(gp_var, expected_gp_var, rtol=1e-5, atol=1e-5)
    assert np.all(gp_var > 0)
