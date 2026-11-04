"""Comprehensive tests for OllamaOccupationExtractor against real scenarios."""

import time
import pytest
from dataset.scripts.ingest.lexicon import OccupationLexicon
from dataset.scripts.ingest.ollama_extractor import OllamaOccupationExtractor


@pytest.fixture(scope="module")
def extractor():
    # Use granite4.1:3b (default 3.4B model with native array schema)
    return OllamaOccupationExtractor(model="granite4.1:3b", temperature=0.0)


@pytest.fixture(scope="module")
def sample_lexicon():
    return OccupationLexicon([
        "software engineer", "teacher", "rn", "registered nurse",
        "electrician", "plumber", "hvac", "dentist", "doctor",
        "specialist", "worker", "chief", "manager", "director", "officer",
    ])


def test_extraction_simple_profession(extractor):
    text = "I have been working as a commercial electrician for 5 years now, love the trade."
    res = extractor.extract(text)
    assert any("electrician" in item.lower() for item in res), f"Expected electrician in {res}"


def test_role_turner_nouns(extractor, sample_lexicon):
    # Tests 'specialist', 'worker', and 'chief'
    text_spec = "I have been working as a video game specialist for over three years."
    assert sample_lexicon.contains_any(text_spec), "Screening should pass on 'specialist'"
    res_spec = extractor.extract_with_screening(text_spec, sample_lexicon)
    assert any("specialist" in item.lower() for item in res_spec), f"Expected specialist in {res_spec}"

    text_worker = "Worked as a construction worker on high-rise buildings."
    assert sample_lexicon.contains_any(text_worker), "Screening should pass on 'worker'"
    res_worker = extractor.extract_with_screening(text_worker, sample_lexicon)
    assert any("worker" in item.lower() for item in res_worker), f"Expected worker in {res_worker}"

    text_chief = "He served as a fire chief for twenty years."
    assert sample_lexicon.contains_any(text_chief), "Screening should pass on 'chief'"
    res_chief = extractor.extract_with_screening(text_chief, sample_lexicon)
    assert any("chief" in item.lower() for item in res_chief), f"Expected chief in {res_chief}"


def test_false_positive_rejection_student_and_symptoms(extractor):
    # 'headache' and 'high school senior' must NEVER be extracted as jobs
    text = "Had a bad migraine headache all day. In my senior year of high school right now."
    res = extractor.extract(text)
    assert res == [], f"Expected empty list for false positive text, got: {res}"


def test_false_positive_rejection_hobbies(extractor):
    text = "Huge video gamer, fitness runner, and dog lover spending weekends outdoors."
    res = extractor.extract(text)
    assert res == [], f"Expected empty list for hobby text, got: {res}"


def test_multi_occupation_job_history(extractor):
    text = "I worked as a high school teacher for six years before making a career switch to become a software engineer."
    res = extractor.extract(text)
    res_lower = [item.lower() for item in res]
    assert any("teacher" in item for item in res_lower), f"Expected teacher in {res}"
    assert any("software engineer" in item or "engineer" in item for item in res_lower), f"Expected software engineer in {res}"


def test_clinical_acronym_in_bio(extractor):
    text = "Bio: ER registered nurse (RN), night owl, mother of 2."
    res = extractor.extract(text)
    res_lower = [item.lower() for item in res]
    assert any("nurse" in item or "rn" in item for item in res_lower), f"Expected nurse/rn in {res}"


def test_lexicon_screening_integration(extractor, sample_lexicon):
    # Screening check: if text mentions no occupation from lexicon, LLM call is bypassed
    text_without_jobs = "The weather in Seattle is rainy and cold today. Walking in the park."
    res = extractor.extract_with_screening(text_without_jobs, sample_lexicon)
    assert res == []

    text_with_job = "I work as a software engineer at a cloud infrastructure firm."
    res = extractor.extract_with_screening(text_with_job, sample_lexicon)
    assert any("software engineer" in item.lower() for item in res)


if __name__ == "__main__":
    pytest.main(["-v", "-s", __file__])
