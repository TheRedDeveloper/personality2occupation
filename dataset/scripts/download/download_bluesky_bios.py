"""
Bluesky Step 2: Extract & Download bios into `dataset/cache/bluesky_bios.jsonl`.
Reads `dataset/cache/bluesky_users.jsonl`. If any profile bio is empty or needs refresh,
can batch request `app.bsky.actor.getProfiles`.
Resumable: skips users already written to `dataset/cache/bluesky_bios.jsonl`.
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Set
import requests
from tqdm import tqdm
from dataset.scripts.ingest.lexicon import build_or_load_lexicon


DEFAULT_USERS_INPUT = Path("dataset/cache/bluesky_users.jsonl")
DEFAULT_BIOS_OUTPUT = Path("dataset/cache/bluesky_bios.jsonl")
BLUESKY_GET_PROFILES_API = "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfiles"


def extract_and_download_bios(
    users_input: Path = DEFAULT_USERS_INPUT,
    bios_output: Path = DEFAULT_BIOS_OUTPUT,
    resumable: bool = True,
    refresh_missing: bool = False,
) -> int:
    users_input = Path(users_input)
    bios_output = Path(bios_output)
    bios_output.parent.mkdir(parents=True, exist_ok=True)

    if not users_input.exists():
        print(f"[Bluesky Step 2] Users file not found at: {users_input}")
        return 0

    lex = build_or_load_lexicon()

    seen_users: Set[str] = set()
    if resumable and bios_output.exists():
        with open(bios_output, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                u = rec.get("user_id") or rec.get("handle") or rec.get("did")
                if u:
                    seen_users.add(u)

    print("\n" + "=" * 70)
    print("Bluesky Step 2: Extract & Lexicon-Filter Bios")
    print(f"Reading: {users_input}")
    print(f"Output: {bios_output}")
    print(f"Already Formatted: {len(seen_users):,}")
    print("=" * 70)

    writer = open(bios_output, "a", encoding="utf-8")
    count = 0
    missing_bio_dids: List[Dict] = []

    try:
        with open(users_input, "r", encoding="utf-8") as f:
            for line in tqdm(f, desc="Parsing Bluesky Users"):
                rec = json.loads(line)
                did = rec.get("did")
                handle = rec.get("handle")
                ident = handle or did
                if not ident or ident in seen_users:
                    continue

                bio = (rec.get("description") or "").strip()
                if bio:
                    matches = lex.match(bio)
                    if matches:
                        out_rec = {
                            "user_id": ident,
                            "handle": handle,
                            "did": did,
                            "display_name": rec.get("displayName") or "",
                            "bio": bio,
                            "matched_keywords": matches,
                        }
                        writer.write(json.dumps(out_rec, ensure_ascii=False) + "\n")
                        seen_users.add(ident)
                        count += 1
                elif refresh_missing and did:
                    missing_bio_dids.append(rec)

        writer.flush()

        # Batch refresh any missing profiles via getProfiles in chunks of 25
        if missing_bio_dids:
            print(f"[Bluesky Step 2] Attempting to refresh {len(missing_bio_dids):,} empty bios...")
            for i in range(0, len(missing_bio_dids), 25):
                chunk = missing_bio_dids[i : i + 25]
                params = [("actors[]", x["did"]) for x in chunk if x.get("did")]
                try:
                    resp = requests.get(BLUESKY_GET_PROFILES_API, params=params, timeout=15)
                    if resp.status_code == 200:
                        profiles = resp.json().get("profiles", [])
                        for p in profiles:
                            b = (p.get("description") or "").strip()
                            h = p.get("handle") or p.get("did")
                            if b and h and h not in seen_users:
                                out_rec = {
                                    "user_id": h,
                                    "handle": p.get("handle"),
                                    "did": p.get("did"),
                                    "display_name": p.get("displayName") or "",
                                    "bio": b,
                                }
                                writer.write(json.dumps(out_rec, ensure_ascii=False) + "\n")
                                seen_users.add(h)
                                count += 1
                        writer.flush()
                except Exception:
                    pass
    finally:
        writer.close()

    print(f"[Bluesky Step 2] Complete! Formatted {count:,} user bios into {bios_output}.")
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bluesky Step 2: Download/Extract Bios")
    parser.add_argument("--continue", dest="cont", action="store_true", default=True, help="Resume from disk")
    args = parser.parse_args()

    extract_and_download_bios(resumable=args.cont)
