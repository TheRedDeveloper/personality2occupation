import sys
import json
import random

sys.stdout.reconfigure(encoding='utf-8')

with open('dataset/cache/bluesky_evaluated_uids.txt', 'r', encoding='utf-8') as f:
    eval_lines = [line.strip() for line in f if line.strip()][75154:]

with open('dataset/cache/verified_bluesky.jsonl', 'r', encoding='utf-8') as f:
    ver_lines = [line.strip() for line in f if line.strip()][29287:]

new_ver_uids = set(json.loads(line).get('user_id') for line in ver_lines)
rejected_uids = set(u for u in eval_lines if u not in new_ver_uids)

rejected_records = []
with open('dataset/cache/bluesky_bios.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        rec = json.loads(line)
        uid = rec.get('user_id') or rec.get('handle')
        if uid in rejected_uids:
            rejected_records.append(rec)
            if len(rejected_records) == len(rejected_uids):
                break

print(f'Total rejected records found: {len(rejected_records)}')

random.seed(42)
sample = random.sample(rejected_records, min(30, len(rejected_records)))

print('\n=== RANDOM SAMPLE OF 30 REJECTED BIOS ===')
for i, r in enumerate(sample, 1):
    uid = r.get('handle') or r.get('user_id')
    bio = r.get('bio', '').replace('\n', ' ')
    matched = r.get('matched_keywords', [])
    print(f'{i:2d}. [{uid}] (lexicon match: {matched})')
    print(f'    "{bio}"')
