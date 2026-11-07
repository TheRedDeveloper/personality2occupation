#!/usr/bin/env python3
"""
Step 1: Big Five Personality Trait Inference Engine.

Runs ModernBERT-large (Ritsuk0/aleph-big5-fullp) over user text from
dataset/user_occupations_text.parquet, extracting a 5D continuous
personality vector [Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism]
clamped to [0.0, 1.0].

Features:
- Power-outage / crash resilient JSONL checkpointing.
- Fast startup: loads existing checkpoints in seconds and resumes where left off.
- Configurable --limit and --dry-run flags for safe testing.
- tqdm progress bar with smoothing=0 for stable ETA.
"""

from transformers import AutoModelForSequenceClassification, PreTrainedTokenizerFast
from tqdm import tqdm
from huggingface_hub import hf_hub_download
import torch
import pyarrow.parquet as pq
import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Set, Dict, Any, cast

# Ensure repository root is on sys.path
ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


MODEL_ID = "Ritsuk0/aleph-big5-fullp"
TRAIT_NAMES = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]
DEFAULT_INPUT_PARQUET = Path("dataset/user_occupations_text.parquet")
DEFAULT_CHECKPOINT = Path("dataset/cache/personality_big5_checkpoint.jsonl")


def load_tokenizer() -> PreTrainedTokenizerFast:
    """Loads tokenizer from tokenizer.json to bypass TokenizersBackend class alias."""
    tok_file = hf_hub_download(MODEL_ID, "tokenizer.json")
    tokenizer = PreTrainedTokenizerFast(tokenizer_file=tok_file)
    tokenizer.pad_token = "[PAD]"
    tokenizer.pad_token_id = 50283
    tokenizer.model_max_length = 4096
    return tokenizer


def load_model(device: torch.device, use_fp16: bool = True) -> Any:
    """Loads ModernBERT sequence classification model with PyTorch native SDPA attention."""
    print(f"Loading {MODEL_ID} onto {device} (fp16={use_fp16}, attn=sdpa)...")
    extra_kwargs = {}
    if device.type == "cuda":
        extra_kwargs["attn_implementation"] = "sdpa"
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_ID,
        dtype=torch.float16 if (use_fp16 and device.type == "cuda") else torch.float32,
        **extra_kwargs,
    )
    model.to(device)
    model.eval()
    return model


def load_seen_user_ids(checkpoint_path: Path) -> Set[str]:
    """Reads existing checkpoint file and returns set of completed user IDs."""
    seen: Set[str] = set()
    if not checkpoint_path.exists():
        return seen

    print(f"Reading existing checkpoint from {checkpoint_path}...")
    with open(checkpoint_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if "user_id" in record:
                    seen.add(record["user_id"])
            except json.JSONDecodeError:
                continue
    return seen


def main():
    parser = argparse.ArgumentParser(description="Step 1: Big Five Trait Inference Engine")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PARQUET, help="Path to input text parquet")
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT, help="Path to checkpoint jsonl")
    parser.add_argument("--batch-size", type=int, default=16, help="Inference batch size")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of authors to process (for testing)")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing to checkpoint file")
    parser.add_argument("--no-fp16", action="store_true", help="Disable fp16 half precision on CUDA")
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input parquet file not found at {args.input}", file=sys.stderr)
        sys.exit(1)

    device = torch.device(args.device)
    use_fp16 = not args.no_fp16 and device.type == "cuda"

    # 1. Load seen users from checkpoint
    seen_uids: Set[str] = set()
    if not args.dry_run:
        args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
        seen_uids = load_seen_user_ids(args.checkpoint)

    # 2. Read input dataset table
    print(f"Reading input dataset {args.input}...")
    table = pq.read_table(args.input, columns=["user_id", "text"])
    all_uids: List[str] = table.column("user_id").to_pylist()
    all_texts: List[str] = table.column("text").to_pylist()
    total_in_file = len(all_uids)

    # Filter out completed users
    pending_items: List[tuple[str, str]] = []
    for uid, text in zip(all_uids, all_texts):
        if uid not in seen_uids:
            pending_items.append((uid, text))

    completed_count = len(seen_uids)
    print(f"Total authors: {total_in_file:,} | Already completed: {completed_count:,} | Pending: {len(pending_items):,}")

    if args.limit is not None and args.limit > 0:
        pending_items = pending_items[:args.limit]
        print(f"Applied --limit: processing {len(pending_items)} author(s)")

    if not pending_items:
        print("All authors have already been evaluated! Nothing to do.")
        return

    # 3. Load model and tokenizer
    tokenizer = load_tokenizer()
    model = load_model(device, use_fp16=use_fp16)

    # 4. Process in batches with tqdm
    checkpoint_file = None
    if not args.dry_run:
        checkpoint_file = open(args.checkpoint, "a", encoding="utf-8")

    batch_size = max(1, args.batch_size)
    pbar = tqdm(
        total=len(pending_items),
        desc="Scoring Big Five",
        unit="user",
        smoothing=0,
        mininterval=1.0,
        dynamic_ncols=True,
    )

    try:
        for i in range(0, len(pending_items), batch_size):
            chunk = pending_items[i:i + batch_size]
            chunk_uids = [item[0] for item in chunk]
            chunk_texts = [item[1] for item in chunk]

            # Tokenize batch
            inputs = tokenizer(
                chunk_texts,
                padding=True,
                truncation=True,
                max_length=4096,
                return_tensors="pt",
            )
            input_ids = cast(torch.Tensor, inputs["input_ids"]).to(device)
            attention_mask = cast(torch.Tensor, inputs["attention_mask"]).to(device)

            with torch.no_grad():
                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                # Raw regression logits clamped to [0.0, 1.0]
                clamped_scores = torch.clamp(outputs.logits, 0.0, 1.0).cpu().tolist()

            for uid, scores in zip(chunk_uids, clamped_scores):
                rounded_scores = [round(float(s), 4) for s in scores]
                record = {
                    "user_id": uid,
                    "big5": rounded_scores,
                }
                if not args.dry_run and checkpoint_file is not None:
                    checkpoint_file.write(json.dumps(record) + "\n")
                elif args.dry_run and i == 0 and uid == chunk_uids[0]:
                    trait_preview = {name: val for name, val in zip(TRAIT_NAMES, rounded_scores)}
                    print(f"\n[DRY RUN SAMPLE] user_id: {uid} -> {trait_preview}")

            if not args.dry_run and checkpoint_file is not None:
                checkpoint_file.flush()

            pbar.update(len(chunk))

    finally:
        pbar.close()
        if checkpoint_file is not None:
            checkpoint_file.close()

    print("\nStep 1 Big Five scoring pass finished.")


if __name__ == "__main__":
    main()
