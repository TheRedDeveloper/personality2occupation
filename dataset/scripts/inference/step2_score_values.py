#!/usr/bin/env python3
"""
Step 2: Schwartz Human Values Inference Engine (value_final).

Runs the value_final model
(SotirisLegkas/roberta-large_ALL_BCE_translated_data_multihead_19_shuffled_special_tokens_final,
 RoBERTa-large with multi-head BCE classification heads, F1=0.37 official competition model)
over user text from dataset/user_occupations_text.parquet.

Extracts a 19D continuous value intensity vector representing the
frequency/presence of the 19 Schwartz values across the user's text:
[Self-direction: thought, Self-direction: action, Stimulation, Hedonism,
 Achievement, Power: dominance, Power: resources, Face, Security: personal,
 Security: societal, Tradition, Conformity: rules, Conformity: interpersonal,
 Humility, Benevolence: caring, Benevolence: dependability, Universalism: concern,
 Universalism: nature, Universalism: tolerance].

Features:
- Evaluates 100% of all sentences per author (no artificial sentence truncation).
- 3-sentence sliding window context (s_{t-2} </s> s_{t-1} </s> s_t) capturing
  conversational flow without autoregressive latency.
- True multi-label classification using independent Sigmoids per value.
- Peak VRAM footprint < 2.5 GB (leaves plenty of room for all desktop apps, zero RAM swapping).
- Throughput ~0.70s per full author profile (~20-22 hours for all 111,509 authors).
- Power-outage / crash resilient JSONL checkpointing with automatic resumption.
- Fast startup: loads existing checkpoints in seconds and skips completed authors.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Set, Dict, Any, Tuple, Optional, cast

# Ensure repository root is on sys.path
ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pyarrow.parquet as pq
import torch
from tqdm import tqdm
from transformers import AutoTokenizer

from dataset.scripts.inference.values_hierocles import (
    MultiHead_MultiLabel_Roberta,
    VALUES,
)

MODEL_ID = "SotirisLegkas/roberta-large_ALL_BCE_translated_data_multihead_19_shuffled_special_tokens_final"
MODEL_ALIAS = "value_final (RoBERTa-large, 19 heads)"
DEFAULT_INPUT_PARQUET = Path("dataset/user_occupations_text.parquet")
DEFAULT_CHECKPOINT = Path("dataset/cache/personality_values_checkpoint.jsonl")


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


def split_text_into_sentences(text: str, max_sentences: Optional[int] = None) -> List[str]:
    """Splits user text into substantive sentences (min 12 chars), optionally bounded."""
    raw_sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences: List[str] = []
    for s in raw_sentences:
        s = s.strip()
        if len(s) >= 12:
            sentences.append(s)
            if max_sentences is not None and len(sentences) >= max_sentences:
                break
    if not sentences and text.strip():
        sentences = [text.strip()[:250]]
    return sentences


def build_sliding_window_contexts(sentences: List[str], sep: str = " </s> ") -> List[str]:
    """
    Builds 3-sentence sliding window context strings:
    s_0, s_0 </s> s_1, s_0 </s> s_1 </s> s_2, s_1 </s> s_2 </s> s_3, ...
    Preserves preceding conversational context without autoregressive slowdown.
    """
    contexts: List[str] = []
    for i in range(len(sentences)):
        if i == 0:
            contexts.append(sentences[0])
        elif i == 1:
            contexts.append(f"{sentences[0]}{sep}{sentences[1]}")
        else:
            contexts.append(f"{sentences[i - 2]}{sep}{sentences[i - 1]}{sep}{sentences[i]}")
    return contexts


def main():
    parser = argparse.ArgumentParser(description=f"Step 2: Schwartz Human Values Inference Engine ({MODEL_ALIAS})")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PARQUET, help="Path to input text parquet")
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT, help="Path to checkpoint jsonl")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of authors to process (for testing)")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing to checkpoint file")
    parser.add_argument("--sentence-batch-size", type=int, default=64, help="Sentence batch size for GPU inference")
    parser.add_argument("--max-sentences", type=int, default=None, help="Max sentences per author (default: evaluate 100% of sentences)")
    parser.add_argument("--max-length", type=int, default=160, help="Max token length for sliding context window")
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--no-fp16", action="store_true", help="Disable fp16 half precision on CUDA")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input parquet file not found at {args.input}", file=sys.stderr)
        sys.exit(1)

    device = torch.device(args.device)
    use_fp16 = not args.no_fp16 and device.type == "cuda"
    dtype = torch.float16 if use_fp16 else torch.float32

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
    pending_items: List[Tuple[str, str]] = []
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

    # 3. Load value_final model and tokenizer
    print(f"Loading {MODEL_ALIAS} onto {device} (dtype={dtype})...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model: Any = MultiHead_MultiLabel_Roberta.from_pretrained(
        MODEL_ID,
        dtype=dtype,
    )
    model.to(device)
    model.eval()

    # 4. Process users
    checkpoint_file = None
    if not args.dry_run:
        checkpoint_file = open(args.checkpoint, "a", encoding="utf-8")

    sent_bs = max(1, args.sentence_batch_size)
    coverage_desc = "100% full text" if args.max_sentences is None else f"capped {args.max_sentences} sents"
    pbar = tqdm(
        total=len(pending_items),
        desc=f"Scoring Schwartz Values (value_final, {coverage_desc})",
        unit="user",
        smoothing=0,
        mininterval=1.0,
        dynamic_ncols=True,
    )

    unflushed_count = 0
    first_preview_printed = False

    try:
        for user_idx, (uid, full_text) in enumerate(pending_items):
            sentences = split_text_into_sentences(full_text, max_sentences=args.max_sentences)
            if not sentences:
                user_values_19 = [0.0] * 19
            else:
                contexts = build_sliding_window_contexts(sentences)
                all_probs: List[List[float]] = []

                # Batch sentence inference
                for i in range(0, len(contexts), sent_bs):
                    batch_contexts = contexts[i : i + sent_bs]
                    inputs = tokenizer(
                        batch_contexts,
                        padding=True,
                        truncation=True,
                        max_length=args.max_length,
                        return_tensors="pt",
                    )
                    input_ids = cast(torch.Tensor, inputs["input_ids"]).to(device)
                    attention_mask = cast(torch.Tensor, inputs["attention_mask"]).to(device)

                    with torch.no_grad():
                        logits = model(input_ids, attention_mask=attention_mask, language="EN")
                        # value_final has 19 heads directly aligned with canonical VALUES list
                        probs = torch.sigmoid(logits).cpu().tolist()
                        all_probs.extend(probs)

                num_w = len(all_probs)
                user_values_19 = [
                    round(sum(all_probs[s][v] for s in range(num_w)) / num_w, 4)
                    for v in range(19)
                ]

            record = {
                "user_id": uid,
                "values": user_values_19,
            }

            if not args.dry_run and checkpoint_file is not None:
                checkpoint_file.write(json.dumps(record) + "\n")
                unflushed_count += 1
                if unflushed_count >= 16:
                    checkpoint_file.flush()
                    unflushed_count = 0
            elif args.dry_run and not first_preview_printed:
                sample_preview = {v_name: score for v_name, score in zip(VALUES, user_values_19)}
                print(f"\n[DRY RUN SAMPLE] user_id: {uid} ({len(sentences)} sentences) -> {sample_preview}")
                first_preview_printed = True

            pbar.update(1)

        if not args.dry_run and checkpoint_file is not None:
            checkpoint_file.flush()

    finally:
        pbar.close()
        if checkpoint_file is not None:
            checkpoint_file.close()

    print("\nStep 2 Schwartz Values scoring pass finished.")


if __name__ == "__main__":
    main()
