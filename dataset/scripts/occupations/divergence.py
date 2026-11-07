"""Psychological Divergence Check for Occupational Clusters.

Inspects the empirical 24D personality distributions of member titles within each
canonical cluster. All 24 dimensions are standardized against population means and
variances (Z ~ N(0, 1)) so that all psychological traits and values carry equal weight.

If a constituent sub-role shows statistically significant psychological divergence
(Cohen's d effect size and Welch's t-test with multiple testing protection) and both
the sub-role and remainder cluster retain sufficient sample size (N >= min_split_authors),
the sub-role is split into an independent canonical occupation and related members
are re-evaluated and reassigned.
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pyarrow.parquet as pq
from scipy import stats

# Ensure project root is in sys.path
project_root = str(Path(__file__).resolve().parents[3])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dataset.scripts.occupations.cluster import embed_titles, is_one_edit_or_swap
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

# Known abbreviation expansions to prevent informal slang from splitting away from standard titles
ABBREVIATION_EXPANSIONS = {
    "dev": "developer",
    "qa": "quality assurance",
    "prof": "professor",
    "doc": "doctor",
    "eng": "engineer",
    "rep": "representative",
    "tech": "technician",
    "mgr": "manager",
    "asst": "assistant",
    "assoc": "associate",
}

GENDER_SUFFIXES = ("person", "man", "woman")


def is_spelling_or_morphological_variant(
    title1: str,
    title2: str,
    cluster_members: Optional[List[str]] = None,
    member_counts: Optional[Dict[str, int]] = None,
) -> bool:
    """Check if title1 is merely a spacing, hyphen, gender, or abbreviation variant of title2."""
    if title1 == title2:
        return True

    # 1. Spacing and punctuation collapse (e.g. 'candle maker' vs 'candlemaker')
    t1_compact = title1.replace(" ", "").replace("-", "")
    t2_compact = title2.replace(" ", "").replace("-", "")
    if t1_compact == t2_compact:
        return True

    # 2. American vs. British spelling or minor 1-edit typo (e.g. 'colorist' vs 'colourist')
    if is_one_edit_or_swap(t1_compact, t2_compact):
        return True

    # 3. Gender suffixes: craftsperson / craftsman / craftswoman, salesperson / salesman
    for sfx in GENDER_SUFFIXES:
        if t1_compact.endswith(sfx):
            base1 = t1_compact[:-len(sfx)]
            for sfx2 in GENDER_SUFFIXES:
                if t2_compact == base1 + sfx2:
                    return True

    # 4. Abbreviation token check (e.g., 'software dev' -> 'software developer')
    tokens1 = title1.split()
    expanded_tokens = [ABBREVIATION_EXPANSIONS.get(tok, tok) for tok in tokens1]
    expanded1 = " ".join(expanded_tokens)

    if expanded1 == title2:
        return True

    if cluster_members and member_counts and expanded1 in cluster_members and expanded1 != title1:
        if member_counts.get(expanded1, 0) >= member_counts.get(title1, 0):
            return True

    # 5. QA vs Quality Assurance
    if ("quality assurance" in title2 and "quality" in title1) or ("quality assurance" in title1 and "quality" in title2):
        if "engineer" in title1 and "engineer" in title2:
            return True

    return False


def check_subrole_divergence(
    vecs_sub: np.ndarray,
    vecs_rem: np.ndarray,
    min_cohens_d: float = 0.50,
    p_val_threshold: float = 0.02,
    min_sig_traits: int = 1,
    stringent_p_threshold: float = 0.003,
) -> Tuple[bool, List[Dict[str, Any]]]:
    """Test whether sub-role personality vectors statistically diverge from cluster remainder.
    
    Uses standardized Z-scores so all 24 dimensions carry equal weight.
    Applies multiple-testing protection:
    - Split triggered if at least 1 trait satisfies Bonferroni-level significance (p < stringent_p_threshold)
      OR at least 2 traits satisfy p < p_val_threshold with |d| >= min_cohens_d.
    """
    n_sub, n_rem = len(vecs_sub), len(vecs_rem)
    if n_sub < 2 or n_rem < 2:
        return False, []

    divergent_traits = []

    for i, trait in enumerate(ALL_DIMENSIONS):
        vals_sub = vecs_sub[:, i]
        vals_rem = vecs_rem[:, i]

        m_sub, m_rem = float(np.mean(vals_sub)), float(np.mean(vals_rem))
        s_sub, s_rem = float(np.std(vals_sub, ddof=1)), float(np.std(vals_rem, ddof=1))

        # Welch's t-test
        t_stat, p_val = stats.ttest_ind(vals_sub, vals_rem, equal_var=False)

        # Cohen's d (pooled standard deviation)
        pooled_var = (((n_sub - 1) * s_sub**2 + (n_rem - 1) * s_rem**2) / (n_sub + n_rem - 2))
        pooled_sd = np.sqrt(max(pooled_var, 1e-12))
        cohens_d = (m_sub - m_rem) / pooled_sd

        # Require meaningful effect size and significance
        if abs(cohens_d) >= min_cohens_d and p_val <= p_val_threshold:
            divergent_traits.append({
                "trait": trait,
                "sub_mean": m_sub,
                "rem_mean": m_rem,
                "diff": m_sub - m_rem,
                "cohens_d": cohens_d,
                "p_val": p_val,
            })

    # Multiple testing guard: Bonferroni-level single trait OR multi-trait divergence
    has_stringent_single = any(t["p_val"] <= stringent_p_threshold and abs(t["cohens_d"]) >= min_cohens_d for t in divergent_traits)
    has_multi_traits = len(divergent_traits) >= max(2, min_sig_traits)

    should_split = has_stringent_single or has_multi_traits
    return should_split, divergent_traits


def evaluate_and_split_divergent_occupations(
    parquet_path: str = "dataset/user_occupations_personality.parquet",
    mapping_path: str = "dataset/cache/canonical_occupations_mapping.json",
    output_path: str = "dataset/cache/divergence_split_mapping.json",
    min_split_authors: int = 10,
    min_cohens_d: float = 0.50,
    p_val_threshold: float = 0.02,
    stringent_p_threshold: float = 0.003,
    min_sig_traits: int = 1,
    skip_spelling_variants: bool = True,
    dry_run: bool = False,
) -> Tuple[Dict[str, List[str]], List[Dict[str, Any]]]:
    """Run psychological divergence check across all canonical clusters and split divergent roles."""
    if output_path is None:
        output_path = "dataset/cache/divergence_split_mapping.json"

    logger.info(f"Loading canonical mapping from {mapping_path}...")
    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    logger.info(f"Loading user personalities from {parquet_path}...")
    table = pq.read_table(parquet_path)
    df = table.to_pandas()

    # Standardize 24D personality space to population Z-scores (mean=0, std=1)
    raw_vecs = np.array(df["personality_vector"].to_list(), dtype=np.float32)
    pop_mean = np.mean(raw_vecs, axis=0)
    pop_std = np.std(raw_vecs, axis=0)
    z_vecs = (raw_vecs - pop_mean) / (pop_std + 1e-8)
    logger.info("Standardized 24D personality space to population Z-scores (mean=0, std=1 across all 24 dimensions).")

    cleaned_to_canonical = {}
    for canon, members in mapping.items():
        for m in members:
            cleaned_to_canonical[m] = canon

    # Map authors to standardized vectors and member titles
    title_author_counts = Counter()
    cluster_member_vectors = defaultdict(lambda: defaultdict(list))

    for idx, row in df.iterrows():
        z_vec = z_vecs[idx]
        seen_titles = set()
        for raw in row["occupations"]:
            c = normalize_title(raw)
            if c and c not in seen_titles:
                seen_titles.add(c)
                title_author_counts[c] += 1
                canon = cleaned_to_canonical.get(c)
                if canon:
                    cluster_member_vectors[canon][c].append(z_vec)

    # Embed unique titles to enable semantic reassignment of related sub-members upon split
    all_titles = list(title_author_counts.keys())
    logger.info(f"Embedding {len(all_titles)} titles for split member reassignment...")
    embs = embed_titles(all_titles)
    title_embeddings = {t: embs[i] for i, t in enumerate(all_titles)}

    updated_mapping = {canon: list(members) for canon, members in mapping.items()}
    split_records = []

    logger.info(
        f"Evaluating {len(mapping)} clusters for divergence "
        f"(min_split_authors={min_split_authors}, min_cohens_d={min_cohens_d}, "
        f"p_val_threshold={p_val_threshold}, stringent_p={stringent_p_threshold}, "
        f"skip_spelling_variants={skip_spelling_variants})..."
    )

    eligible_canons = [c for c, m in updated_mapping.items() if len(m) > 1]

    for canon in eligible_canons:
        if canon not in updated_mapping:
            continue

        members = list(updated_mapping[canon])
        member_data = cluster_member_vectors[canon]
        m_counts = {m: len(member_data[m]) for m in members}
        total_cluster_authors = sum(m_counts.values())

        if total_cluster_authors < 2 * min_split_authors:
            continue

        candidates = [m for m in members if m != canon and m_counts[m] >= min_split_authors]
        candidates.sort(key=lambda m: m_counts[m], reverse=True)

        for cand in candidates:
            # Skip trivial spelling, abbreviation, or synonym variants of the canonical title
            if skip_spelling_variants and is_spelling_or_morphological_variant(cand, canon, members, m_counts):
                continue

            cand_vecs = np.array(member_data[cand])
            rem_vecs = []
            for m in updated_mapping[canon]:
                if m != cand:
                    rem_vecs.extend(member_data[m])

            if len(rem_vecs) < min_split_authors:
                continue

            rem_vecs = np.array(rem_vecs)
            should_split, divergent_traits = check_subrole_divergence(
                cand_vecs,
                rem_vecs,
                min_cohens_d=min_cohens_d,
                p_val_threshold=p_val_threshold,
                min_sig_traits=min_sig_traits,
                stringent_p_threshold=stringent_p_threshold,
            )

            if should_split:
                top_trait = max(divergent_traits, key=lambda t: abs(t["cohens_d"]))
                logger.info(
                    f"[SPLIT] '{canon}' -> Splitting sub-role '{cand}' (N={len(cand_vecs)} vs Remainder N={len(rem_vecs)}) | "
                    f"Top Divergence: {top_trait['trait']} (diff={top_trait['diff']:+.2f} std, d={top_trait['cohens_d']:+.2f}, p={top_trait['p_val']:.4f})"
                )

                # Execute split
                new_cluster_members = [cand]
                rem_cluster_members = [m for m in updated_mapping[canon] if m != cand]

                # Semantic reassignment of related sub-members
                cand_emb = title_embeddings.get(cand)
                canon_emb = title_embeddings.get(canon)

                if cand_emb is not None and canon_emb is not None:
                    for other_m in list(rem_cluster_members):
                        if other_m == canon:
                            continue
                        m_emb = title_embeddings.get(other_m)
                        if m_emb is not None:
                            d_cand = 1.0 - float(np.dot(m_emb, cand_emb))
                            d_canon = 1.0 - float(np.dot(m_emb, canon_emb))
                            if d_cand < d_canon:
                                rem_cluster_members.remove(other_m)
                                new_cluster_members.append(other_m)

                # Elect canonical title in both clusters by author count
                new_canon = max(new_cluster_members, key=lambda m: (title_author_counts[m], -len(m)))
                new_cluster_members.sort(key=lambda m: title_author_counts[m], reverse=True)

                rem_canon = max(rem_cluster_members, key=lambda m: (title_author_counts[m], -len(m)))
                rem_cluster_members.sort(key=lambda m: title_author_counts[m], reverse=True)

                # Update mapping
                if rem_canon != canon:
                    del updated_mapping[canon]
                updated_mapping[rem_canon] = rem_cluster_members
                updated_mapping[new_canon] = new_cluster_members

                split_records.append({
                    "original_cluster": canon,
                    "new_cluster": new_canon,
                    "candidate_split": cand,
                    "new_authors_count": len(cand_vecs),
                    "rem_authors_count": len(rem_vecs),
                    "divergent_traits": divergent_traits,
                    "new_members_count": len(new_cluster_members),
                    "rem_members_count": len(rem_cluster_members)
                })
                break

    # Re-sort final mapping by total author count
    sorted_updated_mapping = dict(
        sorted(
            updated_mapping.items(),
            key=lambda item: sum(title_author_counts[m] for m in item[1]),
            reverse=True
        )
    )

    logger.info(
        f"Psychological divergence check complete: executed {len(split_records)} splits. "
        f"Cluster count: {len(mapping)} -> {len(sorted_updated_mapping)}."
    )

    if not dry_run:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(sorted_updated_mapping, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved updated canonical mapping to {output_path}")

    return sorted_updated_mapping, split_records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Psychological divergence check for occupational clusters.")
    parser.add_argument("--parquet", type=str, default="dataset/user_occupations_personality.parquet", help="Path to input parquet.")
    parser.add_argument("--mapping", type=str, default="dataset/cache/canonical_occupations_mapping.json", help="Path to input Stage 1 canonical mapping.")
    parser.add_argument("--output", type=str, default="dataset/cache/divergence_split_mapping.json", help="Path to output Stage 2 mapping.")
    parser.add_argument("--min-split-authors", type=int, default=10, help="Minimum author count for sub-role and remainder (default: 10).")
    parser.add_argument("--min-cohens-d", type=float, default=0.50, help="Minimum Cohen's d effect size on a trait (default: 0.50).")
    parser.add_argument("--p-val", type=float, default=0.02, help="Welch's t-test p-value threshold for multi-trait (default: 0.02).")
    parser.add_argument("--stringent-p", type=float, default=0.003, help="Bonferroni-level p-value for single-trait split (default: 0.003).")
    parser.add_argument("--min-sig-traits", type=int, default=1, help="Minimum number of divergent traits required to split (default: 1).")
    parser.add_argument("--allow-spelling-variants", action="store_true", help="Allow morphological/spelling variants to split.")
    parser.add_argument("--dry-run", action="store_true", help="Run analysis without overwriting the mapping file.")

    args = parser.parse_args()
    evaluate_and_split_divergent_occupations(
        parquet_path=args.parquet,
        mapping_path=args.mapping,
        output_path=args.output,
        min_split_authors=args.min_split_authors,
        min_cohens_d=args.min_cohens_d,
        p_val_threshold=args.p_val,
        stringent_p_threshold=args.stringent_p,
        min_sig_traits=args.min_sig_traits,
        skip_spelling_variants=not args.allow_spelling_variants,
        dry_run=args.dry_run
    )
