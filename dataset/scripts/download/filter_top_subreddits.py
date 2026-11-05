"""
Filters the 29,000+ discovered subreddits down to the top 2,000 professional,
clinical, trade, and vocational career subreddits using dense BAAI/bge-small-en-v1.5 embeddings
and max-similarity comparison against the harvested occupation lexicon and career concepts.
"""

import argparse
import json
from pathlib import Path
import re
import time
from typing import Dict, List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer


DEFAULT_INDEX_CACHE = Path("dataset/cache/hf_reddit_parquet_files.json")
DEFAULT_LEXICON_PATH = Path("dataset/cache/lexicon.json")
DEFAULT_OUTPUT_PATH = Path("dataset/cache/top_2000_subreddits.json")

# Core vocational and career concepts to ensure broad worker & career forum coverage
CAREER_CONCEPTS = [
    "career guidance and career advice",
    "job search employment and career questions",
    "computer science careers and software engineering career advice",
    "workplace discussions career path and professional development",
    "resume review interview preparation and job hunting",
    "trade union worker apprentice and labor craft discussions",
]


def split_pascal_case(name: str) -> str:
    """Converts CamelCase/PascalCase subreddit names into spaced words.
    e.g. 'AskElectricians' -> 'Ask Electricians', 'SafetyProfessionals' -> 'Safety Professionals'
    """
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    return s.replace("_", " ").strip()


def rank_subreddits_by_occupation(
    index_cache: Path = DEFAULT_INDEX_CACHE,
    lexicon_path: Path = DEFAULT_LEXICON_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    top_k: int = 2000,
    device: str = "cuda",
) -> List[Dict]:
    """Computes max-similarity between each subreddit and all lexicon terms + career concepts.
    Saves the top_k ranked subreddits to JSON.
    """
    index_cache = Path(index_cache)
    lexicon_path = Path(lexicon_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not index_cache.exists():
        raise FileNotFoundError(f"Index cache not found: {index_cache}")
    if not lexicon_path.exists():
        raise FileNotFoundError(f"Lexicon file not found: {lexicon_path}")

    # Load lexicon
    with open(lexicon_path, "r", encoding="utf-8") as f:
        lex_data = json.load(f)
    lex_terms = lex_data.get("terms", []) if isinstance(lex_data, dict) else lex_data
    reference_terms = lex_terms + CAREER_CONCEPTS
    print(f"[filter_subreddits] Loaded {len(lex_terms):,} lexicon terms + {len(CAREER_CONCEPTS)} career concepts.")

    # Load HF parquet file paths
    with open(index_cache, "r", encoding="utf-8") as f:
        all_files: List[str] = json.load(f)

    # Map each subreddit to its comment parquet path
    sub_to_file: Dict[str, str] = {}
    for f in all_files:
        if f.endswith("_comments_cleaned.parquet"):
            sub_name = f.split("/")[-1].replace("_comments_cleaned.parquet", "")
            sub_to_file[sub_name] = f

    distinct_subs = sorted(list(sub_to_file.keys()))
    print(f"[filter_subreddits] Found {len(distinct_subs):,} subreddits with comment archives.")

    # Build asymmetrical prompts
    lex_prompts = [f"subreddit for the {t} profession or occupation" for t in reference_terms]
    sub_prompts = [f"r/{split_pascal_case(s)} subreddit" for s in distinct_subs]

    print(f"[filter_subreddits] Initializing BAAI/bge-small-en-v1.5 on {device}...")
    model = SentenceTransformer("BAAI/bge-small-en-v1.5", device=device)

    t0 = time.time()
    print("[filter_subreddits] Encoding reference terms...")
    lex_embs = model.encode(lex_prompts, batch_size=512, show_progress_bar=False, normalize_embeddings=True)

    print("[filter_subreddits] Encoding subreddit names...")
    sub_embs = model.encode(sub_prompts, batch_size=512, show_progress_bar=False, normalize_embeddings=True)

    print("[filter_subreddits] Computing max-similarity matrix...")
    sim_matrix = np.dot(sub_embs, lex_embs.T)
    max_sims = np.max(sim_matrix, axis=1)
    best_term_indices = np.argmax(sim_matrix, axis=1)
    t1 = time.time()
    print(f"[filter_subreddits] Dense matching completed in {round(t1 - t0, 2)} s.")

    # Sort descending
    sorted_idx = np.argsort(max_sims)[::-1][:top_k]

    results = []
    for rank, idx in enumerate(sorted_idx, start=1):
        sub_name = distinct_subs[idx]
        best_term = reference_terms[best_term_indices[idx]]
        score = float(max_sims[idx])
        results.append({
            "rank": rank,
            "subreddit": sub_name,
            "matched_term": best_term,
            "similarity": round(score, 4),
            "parquet_file": sub_to_file[sub_name],
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"[filter_subreddits] Saved top {len(results)} subreddits to {output_path}")
    print("\nSample top 15 ranked subreddits:")
    for r in results[:15]:
        print(f"  #{r['rank']:<4} r/{r['subreddit']:<25} -> {r['matched_term']:<25} ({r['similarity']})")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rank subreddits by occupational and career similarity")
    parser.add_argument("--top-k", type=int, default=2000, help="Number of top subreddits to retain")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="Output JSON path")
    args = parser.parse_args()

    rank_subreddits_by_occupation(top_k=args.top_k, output_path=args.output)
