"""
Bluesky Step 1: Search for users by occupational terms via public AT Protocol.
Outputs discovered actor records to `dataset/cache/bluesky_users.jsonl`.
Resumable: skips already queried terms via `dataset/cache/bluesky_searched_terms.json`.
"""

import argparse
import json
from pathlib import Path
import time
from typing import List, Optional, Set
import requests
from tqdm import tqdm

from dataset.scripts.ingest.lexicon import build_or_load_lexicon


BLUESKY_SEARCH_ACTORS_API = "https://public.api.bsky.app/xrpc/app.bsky.actor.searchActors"
DEFAULT_USERS_OUTPUT = Path("dataset/cache/bluesky_users.jsonl")
DEFAULT_TERMS_STATE = Path("dataset/cache/bluesky_searched_terms.json")


def search_bluesky_users(
    output_path: Path = DEFAULT_USERS_OUTPUT,
    state_path: Path = DEFAULT_TERMS_STATE,
    max_terms: Optional[int] = None,
    limit_per_term: int = 100,
    resumable: bool = True,
) -> int:
    output_path = Path(output_path)
    state_path = Path(state_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    searched_terms: Set[str] = set()
    if resumable and state_path.exists():
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                searched_terms = set(json.load(f))
        except Exception:
            searched_terms = set()

    seen_dids: Set[str] = set()
    if resumable and output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line).get("did")
                if d:
                    seen_dids.add(d)

    lex = build_or_load_lexicon()
    terms = sorted(list(lex.terms))
    if max_terms:
        terms = terms[:max_terms]

    pending_terms = [t for t in terms if t not in searched_terms]

    print("\n" + "=" * 70)
    print("Bluesky Step 1: Search Users by Occupation via public.api.bsky.app")
    print(f"Total Terms: {len(terms):,} | Pending: {len(pending_terms):,}")
    print(f"Output: {output_path}")
    print("=" * 70)

    discovered_count = 0
    writer = open(output_path, "a", encoding="utf-8")

    try:
        pbar = tqdm(pending_terms, desc="Searching Bluesky Terms")
        for term in pbar:
            try:
                resp = requests.get(
                    BLUESKY_SEARCH_ACTORS_API,
                    params={"q": term, "limit": limit_per_term},
                    timeout=15,
                )
                if resp.status_code == 200:
                    actors = resp.json().get("actors", [])
                    new_for_term = 0
                    for a in actors:
                        did = a.get("did")
                        if did and did not in seen_dids:
                            writer.write(json.dumps(a, ensure_ascii=False) + "\n")
                            seen_dids.add(did)
                            new_for_term += 1
                            discovered_count += 1
                    writer.flush()
                    searched_terms.add(term)
                    pbar.set_postfix({"new_users": discovered_count, "last_term_found": new_for_term})
                elif resp.status_code == 429:
                    print(f"\n[Bluesky Step 1] Rate limited (429). Sleeping 10s...")
                    time.sleep(10)
                else:
                    print(f"\n[Bluesky Step 1] HTTP {resp.status_code} for term '{term}'")
            except Exception as e:
                time.sleep(1)

            time.sleep(0.05)  # Respectful spacing
    finally:
        writer.close()
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(sorted(list(searched_terms)), f, indent=2)

    print(f"[Bluesky Step 1] Finished! Discovered {discovered_count:,} unique users across terms.")
    return discovered_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bluesky Step 1: Search Users")
    parser.add_argument("--max-terms", type=int, default=None, help="Max terms to search")
    parser.add_argument("--limit-per-term", type=int, default=100, help="Limit actors per term (max 100)")
    parser.add_argument("--continue", dest="cont", action="store_true", default=True, help="Resume search")
    args = parser.parse_args()

    search_bluesky_users(
        max_terms=args.max_terms,
        limit_per_term=args.limit_per_term,
        resumable=args.cont,
    )
