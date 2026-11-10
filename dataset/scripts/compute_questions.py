#!/usr/bin/env python3
"""
Compute 24D sensitivity gradients for all questions in dataset/questions.txt.

Pipeline:
1. Loads 1,141 curated personality questions from dataset/questions.txt.
2. Programmatically expands each question into 5 Likert response sentences (5,705 total).
3. Runs batch inference on RTX 3060 across:
   - ModernBERT-large (Ritsuk0/aleph-big5-fullp) -> 5 Big Five traits
   - RoBERTa-large 19-head (value_final) -> 19 Schwartz refined values
4. Computes the robust OLS sensitivity slope vector w_q in R^24 for each question.
5. Exports the lean 3-column table (id, text, gradient) to dataset/question_gradient.parquet.
"""

import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import torch
from huggingface_hub import hf_hub_download
from tqdm import tqdm
from transformers import AutoModelForSequenceClassification, AutoTokenizer, PreTrainedTokenizerFast

from dataset.scripts.inference.values_hierocles import MultiHead_MultiLabel_Roberta, VALUES

# File Paths
QUESTIONS_TXT = PROJECT_ROOT / "dataset" / "questions.txt"
OUTPUT_PARQUET = PROJECT_ROOT / "dataset" / "question_gradient.parquet"

# Models
BIG5_MODEL_ID = "Ritsuk0/aleph-big5-fullp"
VALUES_MODEL_ID = "SotirisLegkas/roberta-large_ALL_BCE_translated_data_multihead_19_shuffled_special_tokens_final"

BIG5_NAMES = ["Openness", "Conscientiousness", "Extraversion", "Agreeableness", "Neuroticism"]
DIM_NAMES = BIG5_NAMES + VALUES  # Exactly 24 dimensions

# Natural Habit & Stance Templates for Likert 1..5
LIKERT_TEMPLATES = [
    "I never {P}; it goes completely against my natural tendencies.",       # L1 (k = -1.0)
    "I rarely {P} and generally prefer not to.",                          # L2 (k = -0.5)
    "I occasionally {P}, but only when circumstances require it.",         # L3 (k =  0.0)
    "I regularly {P} and feel comfortable doing so.",                      # L4 (k = +0.5)
    "I always {P}; it is a fundamental part of who I am."                 # L5 (k = +1.0)
]
K_VALUES = np.array([-1.0, -0.5, 0.0, 0.5, 1.0], dtype=np.float32)
SUM_K_SQUARED = np.sum(K_VALUES ** 2)  # 1.0 + 0.25 + 0 + 0.25 + 1.0 = 2.5


def load_questions(path: Path) -> List[str]:
    """Reads cleaned question predicates from questions.txt."""
    if not path.exists():
        raise FileNotFoundError(f"Questions file not found: {path}")
    questions: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(line)
    return questions


def load_big5_model(device: torch.device):
    """Loads ModernBERT Big Five inference engine."""
    print("Loading ModernBERT-large (aleph-big5-fullp)...")
    tok_file = hf_hub_download(BIG5_MODEL_ID, "tokenizer.json", local_files_only=True)
    tokenizer = PreTrainedTokenizerFast(tokenizer_file=tok_file)
    tokenizer.pad_token = "[PAD]"
    tokenizer.pad_token_id = 50283
    tokenizer.model_max_length = 512

    model = AutoModelForSequenceClassification.from_pretrained(
        BIG5_MODEL_ID,
        local_files_only=True,
        dtype=torch.float16 if device.type == "cuda" else torch.float32,
        attn_implementation="sdpa" if device.type == "cuda" else None,
    ).to(device)
    model.eval()
    return tokenizer, model


def load_values_model(device: torch.device):
    """Loads RoBERTa-large 19-head Schwartz values inference engine."""
    print("Loading RoBERTa-large (value_final)...")
    tokenizer = AutoTokenizer.from_pretrained(VALUES_MODEL_ID, local_files_only=True)
    model = MultiHead_MultiLabel_Roberta.from_pretrained(
        VALUES_MODEL_ID,
        local_files_only=True,
        dtype=torch.float16 if device.type == "cuda" else torch.float32,
    ).to(device)
    model.eval()
    return tokenizer, model


def score_sentences_big5(texts: List[str], tokenizer, model, device: torch.device, batch_size: int = 64) -> np.ndarray:
    """Scores Big Five traits for a list of sentences, returning (N, 5) float32 matrix."""
    all_scores = []
    for i in tqdm(range(0, len(texts), batch_size), desc="Scoring Big Five (ModernBERT)", unit="batch"):
        batch = texts[i : i + batch_size]
        inputs = tokenizer(batch, padding=True, truncation=True, max_length=256, return_tensors="pt")
        input_ids = inputs["input_ids"].to(device)
        attention_mask = inputs["attention_mask"].to(device)
        with torch.no_grad():
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            # Use raw unconstrained continuous logits for maximum directional sensitivity
            scores = outputs.logits.float().cpu().numpy()
            all_scores.append(scores)
    return np.vstack(all_scores)


def score_sentences_values(texts: List[str], tokenizer, model, device: torch.device, batch_size: int = 64) -> np.ndarray:
    """Scores 19 Schwartz values for a list of sentences, returning (N, 19) float32 matrix."""
    all_probs = []
    for i in tqdm(range(0, len(texts), batch_size), desc="Scoring Schwartz Values (RoBERTa)", unit="batch"):
        batch = texts[i : i + batch_size]
        inputs = tokenizer(batch, padding=True, truncation=True, max_length=160, return_tensors="pt")
        input_ids = inputs["input_ids"].to(device)
        attention_mask = inputs["attention_mask"].to(device)
        with torch.no_grad():
            logits = model(input_ids, attention_mask=attention_mask, language="EN")
            probs = torch.sigmoid(logits).float().cpu().numpy()
            all_probs.append(probs)
    return np.vstack(all_probs)


def main():
    start_time = time.time()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Executing Question Calibration Engine on device: {device}")

    # 1. Load Questions
    questions = load_questions(QUESTIONS_TXT)
    n_questions = len(questions)
    print(f"Loaded {n_questions:,} questions from {QUESTIONS_TXT}")

    # 2. Expand into 5 Likert sentences per question
    all_sentences: List[str] = []
    for q in questions:
        for tmpl in LIKERT_TEMPLATES:
            all_sentences.append(tmpl.format(P=q))

    total_sentences = len(all_sentences)
    print(f"Generated {total_sentences:,} response sentences ({n_questions} questions x 5 Likert levels)")

    # 3. Model Inference: Big Five
    b5_tok, b5_model = load_big5_model(device)
    b5_scores = score_sentences_big5(all_sentences, b5_tok, b5_model, device, batch_size=64)
    del b5_model
    del b5_tok
    torch.cuda.empty_cache()

    # 4. Model Inference: Schwartz Values
    val_tok, val_model = load_values_model(device)
    val_scores = score_sentences_values(all_sentences, val_tok, val_model, device, batch_size=64)
    del val_model
    del val_tok
    torch.cuda.empty_cache()

    # Combine into full 24D matrix: (5705, 24)
    all_24d = np.hstack([b5_scores, val_scores]).astype(np.float32)
    print(f"Full inference output matrix shape: {all_24d.shape}")

    # 5. Compute OLS Sensitivity Slope w_q in R^24 for each question
    print("Computing OLS sensitivity gradients for each question...")
    gradients: List[List[float]] = []
    ids: List[int] = []

    for q_idx in range(n_questions):
        # 5 rows corresponding to Likert 1..5 for this question
        y_q = all_24d[q_idx * 5 : (q_idx + 1) * 5]  # shape: (5, 24)
        
        # OLS slope: w = sum(k_i * y_i) / sum(k_i^2)
        # where k = [-1.0, -0.5, 0.0, 0.5, 1.0]
        # w = ((y_5 - y_1) + 0.5 * (y_4 - y_2)) / 2.5
        w_q = np.sum(K_VALUES[:, np.newaxis] * y_q, axis=0) / SUM_K_SQUARED  # shape: (24,)
        
        ids.append(q_idx)
        gradients.append([round(float(v), 5) for v in w_q])

    # 6. Build and save Parquet table
    print(f"Building PyArrow Table and exporting to {OUTPUT_PARQUET}...")
    table = pa.Table.from_pydict(
        {
            "id": pa.array(ids, type=pa.int32()),
            "text": pa.array(questions, type=pa.string()),
            "gradient": pa.array(gradients, type=pa.list_(pa.float32(), 24)),
        }
    )

    OUTPUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, OUTPUT_PARQUET, compression="snappy")

    file_size_kb = OUTPUT_PARQUET.stat().st_size / 1024
    elapsed = time.time() - start_time
    print(f"\nSuccessfully generated {OUTPUT_PARQUET} ({file_size_kb:.1f} KB) in {elapsed:.1f}s")

    # 7. Quality Inspection: Display Top 3 Questions and their Sensitivity Profiles
    print("\n" + "=" * 80)
    print("SAMPLE CALIBRATION OUTPUTS")
    print("=" * 80)
    for sample_id in [0, 100, 200, 500, 800]:
        if sample_id < n_questions:
            q_text = questions[sample_id]
            w = np.array(gradients[sample_id])
            top_pos = np.argsort(w)[::-1][:3]
            top_neg = np.argsort(w)[:2]
            
            pos_str = ", ".join(f"{DIM_NAMES[idx]}: {w[idx]:+.3f}" for idx in top_pos if w[idx] > 0.01)
            neg_str = ", ".join(f"{DIM_NAMES[idx]}: {w[idx]:+.3f}" for idx in top_neg if w[idx] < -0.01)
            
            print(f"Q#{sample_id}: \"{q_text}\"")
            print(f"   -> Top Positive Loadings: {pos_str if pos_str else 'None'}")
            print(f"   -> Top Negative Loadings: {neg_str if neg_str else 'None'}\n")


if __name__ == "__main__":
    main()
