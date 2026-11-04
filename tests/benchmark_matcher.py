"""High-throughput matcher benchmark simulating Reddit / social data ingestion.

Distribution:
  - 99.9% (999/1000) generic conversational text (no jobs)
  - 0.05% (1/2000) casual job mentions / candidate words (false alarms or ambiguous mentions)
  - 0.05% (1/2000) genuine self-reported job declarations

Evaluates:
  - Single-core throughput (texts/sec, MB/sec)
  - Multi-core scaling across 4, 8, 16, 32 CPU worker processes
  - Large-scale corpus screening projections (1M, 10M, 100M comments)
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataset.scripts.ingest.lexicon import OccupationLexicon, build_or_load_lexicon

# Typical realistic negative Reddit comments (no occupational terms)
NEGATIVE_TEMPLATES = [
    "Honestly I think the third movie was way better than the second one, the pacing just felt right.",
    "Did anyone else experience connection drops after the latest firmware patch? Resetting didn't help.",
    "That recipe looks delicious! Do you think I could substitute olive oil for butter without ruining it?",
    "The traffic on I-95 this morning was completely stopped for two hours due to some minor construction.",
    "I've been playing this game for over two hundred hours and still haven't found all the hidden collectibles.",
    "Make sure to bring plenty of water if you're hiking up the trail tomorrow, there's zero shade up there.",
    "My cat always knocks over the glass right when I sit down on the couch to watch TV.",
    "The camera quality in low light is surprisingly decent for a phone that costs under four hundred dollars.",
    "Can anyone recommend a good fantasy book series that isn't grimdark and has a satisfying conclusion?",
    "That goal in the final minute of stoppage time was absolutely legendary, best match of the season so far.",
    "I tried clearing the browser cache and cookies but the login redirect loop keeps happening on Chrome.",
    "The autumn colors are peaking in the mountains right now, definitely worth taking a day trip this weekend.",
    "I really hope they don't cancel this series after only one season, the character development is great.",
    "Does anyone have advice on how to keep houseplants alive during winter when indoor humidity is super low?",
    "Just got back from my trip to Portugal, the seafood and pastries were completely out of this world.",
]

# Accidental / candidate match texts (contains an occupational word in a non-job or hobby context)
AMBIGUOUS_TEMPLATES = [
    "I was watching Doctor Who with my kids all afternoon, the tenth doctor is still the greatest.",
    "The hotel room service forgot my extra towels, but the room itself was clean and spacious.",
    "I love modern art museums and listening to jazz in the morning while drinking black coffee.",
    "Had a bad migraine headache during my senior year, could barely study for final exams.",
    "Spent the weekend playing games with my friends, great way to unwind after a crazy busy week.",
]

# Genuine self-reported job declarations (1 in 2000)
GENUINE_JOB_TEMPLATES = [
    "I've been working as a commercial electrician for eight years now, mostly doing industrial conduit.",
    "As a pediatric dentist, I always advise parents to avoid letting toddlers sleep with juice bottles.",
    "Former high school teacher for seven years, made the transition to software engineer last fall.",
    "Working night shifts as an ER registered nurse (RN) has completely destroyed my sleep schedule.",
    "I'm a licensed journeyman plumber in Texas, happy to answer any questions about tankless heaters.",
    "Senior data analyst at a fintech firm, currently redesigning our customer retention pipeline.",
    "Full-time cabinet maker and woodworker specializing in custom walnut dining tables and desks.",
    "Practicing civil attorney and litigator focusing on commercial property and zoning disputes.",
]


def generate_benchmark_corpus(n_samples: int) -> list[str]:
    """Generate realistic text corpus matching 1/1000 candidate and 1/2000 genuine job distribution."""
    random.seed(42)
    corpus: list[str] = []

    for i in range(n_samples):
        r = random.random()
        if r < 0.0005:
            # 1 in 2000: Genuine job declaration
            text = random.choice(GENUINE_JOB_TEMPLATES)
        elif r < 0.0010:
            # 1 in 2000: Ambiguous candidate word
            text = random.choice(AMBIGUOUS_TEMPLATES)
        else:
            # 99.9%: Pure negative text
            text = random.choice(NEGATIVE_TEMPLATES)
            # Add small random variations to avoid string caching
            if random.random() < 0.3:
                text = f"{text} (Ref #{i})"
        corpus.append(text)

    return corpus


# Worker initialization and batch chunk processing
_global_lexicon: OccupationLexicon | None = None


def _init_worker(lexicon_terms: list[str]) -> None:
    global _global_lexicon
    _global_lexicon = OccupationLexicon(lexicon_terms)


def _process_chunk(texts: list[str]) -> tuple[int, int]:
    """Process a chunk of texts, returning (total_screened, total_matched)."""
    global _global_lexicon
    assert _global_lexicon is not None
    matched_count = 0
    for t in texts:
        if _global_lexicon.contains_any(t):
            matched_count += 1
    return len(texts), matched_count


def benchmark_single_core(lexicon: OccupationLexicon, corpus: list[str]) -> dict:
    """Benchmark screening throughput on a single CPU core."""
    total_bytes = sum(len(t.encode("utf-8")) for t in corpus)
    total_texts = len(corpus)

    # Warmup
    for t in corpus[:1000]:
        lexicon.contains_any(t)

    t0 = time.perf_counter()
    matched = 0
    for t in corpus:
        if lexicon.contains_any(t):
            matched += 1
    elapsed = time.perf_counter() - t0

    tps = total_texts / elapsed
    mb_per_sec = (total_bytes / (1024 * 1024)) / elapsed

    return {
        "cores": 1,
        "elapsed": elapsed,
        "total_texts": total_texts,
        "matched": matched,
        "match_rate": (matched / total_texts) * 100,
        "tps": tps,
        "mb_s": mb_per_sec,
    }


def benchmark_multi_core(lexicon_terms: list[str], corpus: list[str], num_workers: int) -> dict:
    """Benchmark screening throughput with multiprocessing worker pool."""
    total_bytes = sum(len(t.encode("utf-8")) for t in corpus)
    total_texts = len(corpus)

    chunk_size = max(500, total_texts // (num_workers * 8))
    chunks = [corpus[i:i + chunk_size] for i in range(0, total_texts, chunk_size)]

    t0 = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=num_workers,
        initializer=_init_worker,
        initargs=(lexicon_terms,),
    ) as executor:
        results = list(executor.map(_process_chunk, chunks))
    elapsed = time.perf_counter() - t0

    matched = sum(r[1] for r in results)
    tps = total_texts / elapsed
    mb_per_sec = (total_bytes / (1024 * 1024)) / elapsed

    return {
        "cores": num_workers,
        "elapsed": elapsed,
        "total_texts": total_texts,
        "matched": matched,
        "match_rate": (matched / total_texts) * 100,
        "tps": tps,
        "mb_s": mb_per_sec,
    }


def main():
    parser = argparse.ArgumentParser(description="Aho-Corasick Matcher Throughput Benchmark")
    parser.add_argument("--n", type=int, default=100000, help="Number of texts to benchmark (default: 100,000)")
    parser.add_argument("--workers", type=int, default=None, help="Max workers to test (default: all CPU cores)")
    args = parser.parse_args()

    max_cpu = os.cpu_count() or 4
    workers_to_test = [w for w in [1, 4, 8, 16, 24, 32] if w <= max_cpu]
    if args.workers and args.workers not in workers_to_test:
        workers_to_test.append(args.workers)
        workers_to_test.sort()

    print("=" * 70)
    print("AHO-CORASICK OCCUPATION MATCHER THROUGHPUT BENCHMARK")
    print(f"Hardware: {max_cpu} CPU cores available")
    print(f"Sample size: {args.n:,} texts")
    print("Distribution: 99.9% Negative | 0.05% Ambiguous | 0.05% Genuine Job")
    print("=" * 70)

    # 1. Load lexicon
    print("\n[1/3] Loading compiled lexicon...")
    t_load = time.perf_counter()
    lexicon = build_or_load_lexicon()
    print(f"Loaded {len(lexicon):,} compiled terms in {time.perf_counter() - t_load:.3f}s")

    # 2. Generate corpus
    print(f"\n[2/3] Generating realistic benchmark corpus ({args.n:,} texts)...")
    corpus = generate_benchmark_corpus(args.n)
    total_mb = sum(len(t.encode("utf-8")) for t in corpus) / (1024 * 1024)
    print(f"Generated {len(corpus):,} texts ({total_mb:.2f} MB total text payload)")

    # 3. Benchmark single-core
    print("\n[3/3] Running Benchmarks across CPU Core Configurations...")
    lexicon_terms = sorted(lexicon.terms)

    results = []
    # Single core
    res_1 = benchmark_single_core(lexicon, corpus)
    results.append(res_1)
    print(f"  ->  1 Worker : {res_1['tps']:10,.0f} texts/sec | {res_1['mb_s']:6.1f} MB/s | Elapsed: {res_1['elapsed']:.2f}s | Matches: {res_1['matched']} ({res_1['match_rate']:.2f}%)")

    # Multi-core scaling
    for w in workers_to_test:
        if w == 1:
            continue
        res_w = benchmark_multi_core(lexicon_terms, corpus, w)
        speedup = res_w["tps"] / res_1["tps"]
        results.append(res_w)
        print(f"  -> {w:2d} Workers: {res_w['tps']:10,.0f} texts/sec | {res_w['mb_s']:6.1f} MB/s | Elapsed: {res_w['elapsed']:.2f}s | Speedup: {speedup:4.1f}x")

    # Print Projections Table
    best = max(results, key=lambda x: x["tps"])
    print("\n" + "=" * 70)
    print("LARGE-SCALE REDDIT SIFTING PROJECTIONS (Best Config)")
    print(f"Peak Throughput: {best['tps']:,.0f} comments/sec ({best['mb_s']:.1f} MB/s) using {best['cores']} workers")
    print("=" * 70)

    for volume, label in [
        (1_000_000, "1 Million Comments"),
        (10_000_000, "10 Million Comments"),
        (50_000_000, "50 Million Comments"),
        (100_000_000, "100 Million Comments"),
    ]:
        est_sec = volume / best["tps"]
        if est_sec < 60:
            time_str = f"{est_sec:.1f} seconds"
        elif est_sec < 3600:
            time_str = f"{est_sec / 60:.1f} minutes"
        else:
            time_str = f"{est_sec / 3600:.2f} hours"

        # Estimated LLM calls (at 0.1% match rate)
        llm_calls = int(volume * (best["match_rate"] / 100))
        # At 0.08s per LLM call on Granite-3B
        llm_time_sec = llm_calls * 0.08
        llm_time_str = f"{llm_time_sec / 60:.1f} min" if llm_time_sec >= 60 else f"{llm_time_sec:.1f} sec"

        print(f"  * {label:22s}: Screening Time = {time_str:>13s} | Triggered LLM calls = {llm_calls:6,d} (~{llm_time_str})")

    print("=" * 70)


if __name__ == "__main__":
    main()
