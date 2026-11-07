"""Dense semantic clustering of cleaned occupation titles using BAAI/bge-small-en-v1.5.

Clusters normalized titles via Agglomerative Clustering using cosine distance,
elects the most frequent title in each cluster as the canonical occupation title,
and exports the mapping {canonical: [uncanonical, ...]}.
"""

import json
import logging
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Ensure project root is in sys.path
project_root = str(Path(__file__).resolve().parents[3])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import numpy as np
import pyarrow.parquet as pq
import torch
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering

from dataset.scripts.occupations.normalize import normalize_title

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def extract_cleaned_title_counts(parquet_path: str) -> Tuple[Counter, Counter, Dict[str, str]]:
    """Extract and normalize all occupations from parquet, tracking occurrences and unique authors.
    
    Returns:
        cleaned_counts: Counter mapping cleaned title -> total frequency across occurrences
        author_counts: Counter mapping cleaned title -> unique authors mentioning it
        raw_to_cleaned: Dict mapping raw title string -> cleaned title string
    """
    logger.info(f"Loading parquet occupations from {parquet_path}...")
    table = pq.read_table(parquet_path, columns=["occupations"])
    
    cleaned_counts = Counter()
    author_counts = Counter()
    raw_to_cleaned = {}
    
    for occ_list in table["occupations"].to_pylist():
        if not occ_list:
            continue
        author_seen = set()
        for raw in occ_list:
            if not raw or not isinstance(raw, str):
                continue
            if raw not in raw_to_cleaned:
                raw_to_cleaned[raw] = normalize_title(raw)
            cleaned = raw_to_cleaned[raw]
            if cleaned:
                cleaned_counts[cleaned] += 1
                author_seen.add(cleaned)
        for c in author_seen:
            author_counts[c] += 1
                
    logger.info(
        f"Extracted {len(raw_to_cleaned)} unique raw titles -> "
        f"{len(cleaned_counts)} unique cleaned titles (total occurrences: {sum(cleaned_counts.values())})"
    )
    return cleaned_counts, author_counts, raw_to_cleaned


def embed_titles(
    titles: List[str],
    model_name: str = "BAAI/bge-small-en-v1.5",
    prompt_template: str = 'job with the title "{t}"',
    batch_size: int = 256,
    device: Optional[str] = None
) -> np.ndarray:
    """Embed normalized titles using SentenceTransformer with prompt templating.
    
    Returns normalized L2 embeddings (shape: [N, D]).
    """
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(
        f"Embedding {len(titles)} titles using {model_name} on {device} "
        f"(batch_size={batch_size}, prompt='{prompt_template}')..."
    )
    t0 = time.time()
    model = SentenceTransformer(model_name, device=device)
    formatted_titles = [prompt_template.format(t=t) for t in titles] if prompt_template else titles
    embeddings = model.encode(
        formatted_titles,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True
    )
    elapsed = time.time() - t0
    logger.info(f"Embedded {len(titles)} titles in {elapsed:.2f}s ({len(titles)/elapsed:.0f} titles/sec). Shape: {embeddings.shape}")
    return embeddings


def cluster_titles(
    titles: List[str],
    embeddings: np.ndarray,
    distance_threshold: float = 0.10,
    linkage: str = "average"
) -> np.ndarray:
    """Cluster normalized embeddings using AgglomerativeClustering with cosine distance.
    
    Args:
        titles: List of cleaned title strings.
        embeddings: Normalized embeddings matrix [N, D].
        distance_threshold: Maximum cosine distance threshold for linking clusters.
        linkage: Linkage criterion ('average' or 'complete').
        
    Returns:
        labels: Array of cluster integer labels for each title [N].
    """
    logger.info(
        f"Clustering {len(titles)} titles with AgglomerativeClustering "
        f"(metric=cosine, distance_threshold={distance_threshold}, linkage={linkage})..."
    )
    t0 = time.time()
    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=distance_threshold,
        metric="cosine",
        linkage=linkage
    )
    labels = clustering.fit_predict(embeddings)
    elapsed = time.time() - t0
    num_clusters = len(set(labels))
    logger.info(f"Clustering completed in {elapsed:.2f}s: formed {num_clusters} clusters from {len(titles)} titles.")
    return labels


def build_canonical_mapping(
    titles: List[str],
    labels: np.ndarray,
    title_counts: Counter
) -> Dict[str, List[str]]:
    """Elect the most frequent title in each cluster as canonical, producing the canonical mapping.
    
    Args:
        titles: List of cleaned title strings.
        labels: Cluster label for each title.
        title_counts: Total frequency counts for each cleaned title.
        
    Returns:
        Dict of {canonical_title: [member_title_1, member_title_2, ...]}
    """
    # Group titles by cluster ID
    clusters = defaultdict(list)
    for title, label in zip(titles, labels):
        clusters[label].append(title)
        
    canonical_mapping = {}
    for cluster_id, member_titles in clusters.items():
        # Elect the member with the highest frequency in the corpus.
        # Break ties by shortest title length, then alphabetical.
        canonical_title = max(
            member_titles,
            key=lambda t: (title_counts[t], -len(t), -ord(t[0]) if t else 0)
        )
        # Sort members by frequency descending
        sorted_members = sorted(member_titles, key=lambda t: title_counts[t], reverse=True)
        canonical_mapping[canonical_title] = sorted_members

    # Sort the mapping by the total frequency of all members descending
    sorted_canonical = dict(
        sorted(
            canonical_mapping.items(),
            key=lambda item: sum(title_counts[m] for m in item[1]),
            reverse=True
        )
    )
    return sorted_canonical


def is_one_insertion(short: str, long: str) -> bool:
    """Helper: checks if long string is short string with exactly one character inserted."""
    i = j = 0
    diff = False
    while i < len(short) and j < len(long):
        if short[i] != long[j]:
            if diff:
                return False
            diff = True
            j += 1
        else:
            i += 1
            j += 1
    return True


def is_one_edit_or_swap(s1: str, s2: str) -> bool:
    """Returns True if edit distance is <= 1 (insertion, deletion, substitution, or adjacent character swap)."""
    if s1 == s2:
        return True
    l1, l2 = len(s1), len(s2)
    if l1 == l2:
        mismatches = [i for i in range(l1) if s1[i] != s2[i]]
        if len(mismatches) == 1:
            return True
        if len(mismatches) == 2:
            i, j = mismatches
            if j == i + 1 and s1[i] == s2[j] and s1[j] == s2[i]:
                return True
        return False
    elif l1 + 1 == l2:
        return is_one_insertion(s1, s2)
    elif l1 - 1 == l2:
        return is_one_insertion(s2, s1)
    return False


CHAIR_REGEX = re.compile(r'^[a-z]+(?:\s+[a-z]+)?\s+(professor(?:\s+of\s+[a-z\s]+)?)$')


def absorb_singletons(
    canonical_mapping: Dict[str, List[str]],
    title_author_counts: Counter,
    title_embeddings: Dict[str, np.ndarray],
    min_anchor_authors: int = 10,
    relaxed_threshold: float = 0.125,
    margin_ratio: float = 0.88,
) -> Dict[str, List[str]]:
    """Absorb low-count orphan titles and singletons into frozen established anchors.
    
    Guaranteed to prevent overmerging:
    - Established Anchors (clusters with >= min_anchor_authors authors) are FROZEN and never merge together.
    - Track 1 (Typo): Damerau-Levenshtein transposition / edit distance <= 1 + semantic cosine distance <= 0.22.
    - Track 2 (Chair): Academic chairs and endowed professorships map to head canonicals.
    - Track 3 (Semantic): Nearest anchor centroid with relaxed threshold <= relaxed_threshold and margin ratio guard.
    """
    t0 = time.time()
    
    # 1. Identify Established Anchors
    cluster_author_counts = Counter()
    for canon, members in canonical_mapping.items():
        cluster_author_counts[canon] = sum(title_author_counts[m] for m in members)

    anchors = set(c for c, cnt in cluster_author_counts.items() if cnt >= min_anchor_authors)
    orphans = [c for c in canonical_mapping if c not in anchors]

    logger.info(
        f"Pass 2 Absorption: {len(anchors)} established anchors (N >= {min_anchor_authors}), "
        f"{len(orphans)} low-count candidate clusters to absorb..."
    )

    anchor_list = sorted(list(anchors))
    anchor_centroids = []
    members_by_bucket = defaultdict(list)

    for a in anchor_list:
        members = canonical_mapping[a]
        embs = [title_embeddings[m] for m in members if m in title_embeddings]
        if embs:
            centroid = np.mean(embs, axis=0)
            norm = np.linalg.norm(centroid)
            if norm > 0:
                centroid /= norm
        else:
            centroid = title_embeddings.get(a, np.zeros(384))
        anchor_centroids.append(centroid)

        for m in members:
            if m:
                members_by_bucket[(m[0], len(m))].append((m, a))

    anchor_centroids = np.array(anchor_centroids) # [num_anchors, D]
    anchor_to_idx = {a: i for i, a in enumerate(anchor_list)}

    absorbed_to_anchor = defaultdict(list)
    clusters_to_remove = set()

    absorbed_typo_count = 0
    absorbed_chair_count = 0
    absorbed_semantic_count = 0

    unabsorbed_titles = []

    for orphan_canon in orphans:
        members = canonical_mapping[orphan_canon]
        
        for t in members:
            t_emb = title_embeddings.get(t)
            destination_anchor = None

            # Track 1: Typo Matching via bucket index
            if len(t) >= 4:
                t_len = len(t)
                first_ch = t[0]
                candidates = []
                for l in (t_len, t_len - 1, t_len + 1):
                    candidates.extend(members_by_bucket.get((first_ch, l), []))

                for cand_member, anchor in candidates:
                    if is_one_edit_or_swap(t, cand_member):
                        if t_emb is not None:
                            a_idx = anchor_to_idx[anchor]
                            cos_dist = 1.0 - float(np.dot(t_emb, anchor_centroids[a_idx]))
                            if cos_dist <= 0.22:
                                destination_anchor = anchor
                                absorbed_typo_count += 1
                                break
                        else:
                            destination_anchor = anchor
                            absorbed_typo_count += 1
                            break

            # Track 2: Academic Chair / Endowed Professorship
            if not destination_anchor:
                m = CHAIR_REGEX.match(t)
                if m:
                    base = m.group(1).strip()
                    if base in anchors:
                        destination_anchor = base
                    elif "professor" in anchors:
                        destination_anchor = "professor"
                    if destination_anchor:
                        absorbed_chair_count += 1

            if destination_anchor:
                absorbed_to_anchor[destination_anchor].append(t)
            else:
                unabsorbed_titles.append(t)

    # Track 3: Vectorized Semantic Absorption on remaining unabsorbed
    if unabsorbed_titles and len(anchor_centroids) > 1:
        orphan_embs = np.array([title_embeddings[t] for t in unabsorbed_titles if t in title_embeddings])
        valid_unabsorbed = [t for t in unabsorbed_titles if t in title_embeddings]
        
        sims = np.dot(orphan_embs, anchor_centroids.T) # [num_orphans, num_anchors]
        dists = 1.0 - sims
        
        # Partition top 2 smallest distances
        top2_idx = np.argpartition(dists, 2, axis=1)[:, :2]
        row_indices = np.arange(len(valid_unabsorbed))
        col0 = top2_idx[:, 0]
        col1 = top2_idx[:, 1]
        
        d_col0 = dists[row_indices, col0]
        d_col1 = dists[row_indices, col1]
        
        swap = d_col0 > d_col1
        d1 = np.where(swap, d_col1, d_col0)
        d2 = np.where(swap, d_col0, d_col1)
        best_anchor_idx = np.where(swap, col1, col0)

        for i, t in enumerate(valid_unabsorbed):
            best_dist = d1[i]
            second_dist = d2[i]
            best_anchor = anchor_list[best_anchor_idx[i]]

            if best_dist <= relaxed_threshold and (best_dist <= 0.09 or (best_dist / max(second_dist, 1e-6) <= margin_ratio)):
                absorbed_to_anchor[best_anchor].append(t)
                absorbed_semantic_count += 1

    # Check which orphan clusters had all their members absorbed
    for orphan_canon in orphans:
        members = canonical_mapping[orphan_canon]
        if all(any(m in absorbed_list for absorbed_list in absorbed_to_anchor.values()) for m in members):
            clusters_to_remove.add(orphan_canon)

    # Build final mapping
    new_mapping = {}
    for canon, members in canonical_mapping.items():
        if canon in clusters_to_remove:
            continue
        new_members = list(members)
        if canon in absorbed_to_anchor:
            for extra in absorbed_to_anchor[canon]:
                if extra not in new_members:
                    new_members.append(extra)
            new_members.sort(key=lambda m: title_author_counts[m], reverse=True)
        new_mapping[canon] = new_members

    sorted_new_mapping = dict(
        sorted(
            new_mapping.items(),
            key=lambda item: sum(title_author_counts[m] for m in item[1]),
            reverse=True
        )
    )

    elapsed = time.time() - t0
    logger.info(
        f"Pass 2 Absorption completed in {elapsed:.2f}s: "
        f"absorbed {absorbed_typo_count} typos, {absorbed_chair_count} chairs, {absorbed_semantic_count} semantic singletons. "
        f"Consolidated and removed {len(clusters_to_remove)} clusters -> Final canonical count: {len(sorted_new_mapping)}"
    )
    return sorted_new_mapping


def run_dense_clustering(
    parquet_path: str = "dataset/user_occupations_personality.parquet",
    output_json_path: str = "dataset/cache/canonical_occupations_mapping.json",
    distance_threshold: float = 0.10,
    linkage: str = "average",
    min_title_freq: int = 1,
    prompt_template: str = 'job with the title "{t}"',
    model_name: str = "BAAI/bge-small-en-v1.5",
    min_anchor_authors: int = 10,
    relaxed_threshold: float = 0.125,
    margin_ratio: float = 0.88,
) -> Dict[str, List[str]]:
    """Run end-to-end dense semantic clustering with two-pass singleton absorption."""
    cleaned_counts, author_counts, _ = extract_cleaned_title_counts(parquet_path)
    
    # Filter titles by minimum frequency if specified (default 1 includes all)
    if min_title_freq > 1:
        filtered_titles = [t for t, cnt in cleaned_counts.items() if cnt >= min_title_freq]
        logger.info(f"Filtered titles with frequency >= {min_title_freq}: {len(filtered_titles)} / {len(cleaned_counts)}")
    else:
        filtered_titles = list(cleaned_counts.keys())

    # Sort titles deterministically
    filtered_titles.sort(key=lambda t: cleaned_counts[t], reverse=True)
    
    # Pass 1: Embed titles and cluster with strict threshold
    embeddings = embed_titles(filtered_titles, model_name=model_name, prompt_template=prompt_template)
    labels = cluster_titles(filtered_titles, embeddings, distance_threshold=distance_threshold, linkage=linkage)
    canonical_mapping = build_canonical_mapping(filtered_titles, labels, cleaned_counts)

    # Pass 2: Asymmetric Singleton & Low-Count Absorption
    title_embeddings_dict = {t: embeddings[i] for i, t in enumerate(filtered_titles)}
    canonical_mapping = absorb_singletons(
        canonical_mapping,
        title_author_counts=author_counts,
        title_embeddings=title_embeddings_dict,
        min_anchor_authors=min_anchor_authors,
        relaxed_threshold=relaxed_threshold,
        margin_ratio=margin_ratio,
    )
    
    # Save to JSON
    os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(canonical_mapping, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Saved canonical mapping ({len(canonical_mapping)} canonical titles) to {output_json_path}")
    return canonical_mapping


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Dense semantic clustering of cleaned occupation titles.")
    parser.add_argument("--parquet", type=str, default="dataset/user_occupations_personality.parquet", help="Path to input parquet.")
    parser.add_argument("--output", type=str, default="dataset/cache/canonical_occupations_mapping.json", help="Path to output JSON.")
    parser.add_argument("--threshold", type=float, default=0.10, help="Cosine distance threshold (default: 0.10).")
    parser.add_argument("--linkage", type=str, default="average", choices=["average", "complete"], help="Linkage criterion.")
    parser.add_argument("--min-freq", type=int, default=1, help="Minimum raw frequency for titles (default: 1).")
    parser.add_argument("--prompt", type=str, default='job with the title "{t}"', help="Prompt template for title embedding.")
    parser.add_argument("--min-anchor-authors", type=int, default=10, help="Minimum author count to qualify as an established anchor (default: 10).")
    parser.add_argument("--relaxed-threshold", type=float, default=0.125, help="Relaxed threshold for singleton absorption (default: 0.125).")
    parser.add_argument("--margin-ratio", type=float, default=0.88, help="Margin ratio guard d1/d2 for semantic absorption (default: 0.88).")
    
    args = parser.parse_args()
    run_dense_clustering(
        parquet_path=args.parquet,
        output_json_path=args.output,
        distance_threshold=args.threshold,
        linkage=args.linkage,
        min_title_freq=args.min_freq,
        prompt_template=args.prompt,
        min_anchor_authors=args.min_anchor_authors,
        relaxed_threshold=args.relaxed_threshold,
        margin_ratio=args.margin_ratio
    )
