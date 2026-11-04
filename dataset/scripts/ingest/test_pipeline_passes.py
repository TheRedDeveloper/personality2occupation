"""
Test and demonstration pipeline for verifying Pass 1 (Lexicon Screening)
and Pass 2 (Ollama Extraction & Text Bounding) on controlled samples across:
  1. Synthetic test cases (true positives, false alarms, boundary checks).
  2. Blogger sample records.
  3. Reddit subreddit sample records.
  4. Bluesky sample records.
"""

import argparse
from pathlib import Path
from dataset.scripts.ingest.pass1_screen import ScreeningPass
from dataset.scripts.ingest.pass2_extract import ExtractionPass, bound_text


def run_synthetic_test(screening: ScreeningPass, extraction: ExtractionPass):
    print("\n" + "=" * 60)
    print("Running Synthetic Test Suite for Pass 1 & Pass 2")
    print("=" * 60)

    synthetic_users = [
        {
            "user_id": "synth_electrician_1",
            "source": "synthetic_reddit",
            "texts": [
                "I am a licensed industrial electrician with 12 years in commercial wiring.",
                "Always remember to lock out and tag out before testing any disconnect switch panel.",
                "The conduit run needs proper bending radius according to the latest national code.",
                " " * 50 + "More trade discussion about transformers, three-phase power, voltage drop, and motor control centers to reach the necessary word count requirement for statistical psychometric analysis in our test suite." * 5,
            ],
        },
        {
            "user_id": "synth_dentist_1",
            "source": "synthetic_reddit",
            "texts": [
                "As a practicing general dentist, I see patients with cracked molars weekly.",
                "Composite restorations require proper etching and isolation to avoid postoperative sensitivity.",
                "Root canal therapy is straightforward if canal curvature is evaluated beforehand on the periapical radiograph.",
                "Here is additional text about dental crowns, hygiene education, periodontal charting, and practice management to ensure we easily exceed the one hundred word boundary required by the dataset specification." * 4,
            ],
        },
        {
            "user_id": "synth_false_alarm_senior",
            "source": "synthetic_blogger",
            "texts": [
                "I am in my senior year of high school and studying for college entrance exams.",
                "My friends and I went to the mall after school to hang out and get some burgers.",
                "Tomorrow is the big basketball tournament against our rival school team.",
                "It feels weird knowing this is our final semester before graduation and moving away from home." * 6,
            ],
        },
        {
            "user_id": "synth_false_alarm_headache",
            "source": "synthetic_blogger",
            "texts": [
                "I have a terrible migraine headache today and can barely keep my eyes open.",
                "I took some aspirin and laid in bed in the dark room trying to get some quiet sleep.",
                "Hopefully tomorrow feels better so I can get back to studying for my history exam." * 6,
            ],
        },
        {
            "user_id": "synth_too_short",
            "source": "synthetic_reddit",
            "texts": [
                "I am an HVAC technician.",
            ],
        },
    ]

    print(f"Screening {len(synthetic_users)} synthetic users through Pass 1...")
    candidates = screening.screen_user_records(iter(synthetic_users))
    print(f"Pass 1 Candidates Found: {len(candidates)}")
    for c in candidates:
        print(f" -> User: {c['user_id']} | Matched: {c['matched_keywords']} | Snippets: {len(c['context_snippets'])}")

    print("\nRunning Pass 2 (Ollama Extraction + Bounding) on candidates...")
    verified = extraction.process_candidates(iter(candidates))
    print(f"\nPass 2 Verified Profiles: {len(verified)}")
    for v in verified:
        print(f" -> [VERIFIED] User: {v['user_id']} | Occupations: {v['occupations']} | Words: {v['word_count']} | Source: {v['source']}")

    # Assertions
    verified_ids = [v["user_id"] for v in verified]
    assert "synth_electrician_1" in verified_ids, "Failed to extract electrician!"
    assert "synth_dentist_1" in verified_ids, "Failed to extract dentist!"
    assert "synth_false_alarm_senior" not in verified_ids, "False positive senior leaked!"
    assert "synth_false_alarm_headache" not in verified_ids, "False positive headache leaked!"
    assert "synth_too_short" not in verified_ids, "Under-budget text (<100 words) leaked!"
    print("\nAll synthetic assertions PASSED successfully!")


def run_sample_subreddits_test(screening: ScreeningPass, extraction: ExtractionPass, sample_limit: int = 50):
    print("\n" + "=" * 60)
    print(f"Running Subreddit Sample Screening (Limit: {sample_limit} comments)")
    print("=" * 60)
    from dataset.scripts.download.download_reddit import load_subreddit_dataframe

    sub_file = Path("dataset/raw/reddit/Dentistry_comments_cleaned.parquet")
    if not sub_file.exists():
        print(f"File {sub_file} not found locally. Skipping.")
        return

    df = load_subreddit_dataframe("Dentistry", local_dir=Path("dataset/raw/reddit"), limit=sample_limit)
    print(f"Loaded {len(df)} sample comments from {sub_file.name}.")

    # Group by author
    user_records = []
    for author, group in df.groupby("author"):
        if author in ("[deleted]", "AutoModerator"):
            continue
        user_records.append({
            "user_id": author,
            "source": "reddit/Dentistry",
            "texts": group["body"].dropna().tolist(),
        })

    print(f"Unique authors in sample: {len(user_records)}")
    candidates = screening.screen_user_records(iter(user_records))
    print(f"Pass 1 Candidates in sample: {len(candidates)}")
    for c in candidates:
        print(f" Candidate author: {c['user_id']} | Keywords: {c['matched_keywords']}")
        print(f" Snippet: {c['context_snippets'][0][:120]}...\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Pass 1 and Pass 2 on synthetic and sample data")
    parser.add_argument("--mode", choices=["synthetic", "reddit", "all"], default="all")
    args = parser.parse_args()

    screening = ScreeningPass()
    extraction = ExtractionPass()

    if args.mode in ("synthetic", "all"):
        run_synthetic_test(screening, extraction)

    if args.mode in ("reddit", "all"):
        run_sample_subreddits_test(screening, extraction, sample_limit=100)
