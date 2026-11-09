"""Unit tests for OccupationLexicon, cleaning logic, and subsumption pruning."""

import pytest
from dataset.scripts.ingest.lexicon import (
    BASELINE_OCCUPATIONS,
    MANUAL_ACRONYMS,
    OccupationLexicon,
    clean_term,
    prune_subsumed_terms,
    resolve_slash_compound,
)


def test_smart_slash_resolver():
    # User requirement 1: "water/wastewater manager" -> "water manager", "wastewater manager"
    assert resolve_slash_compound("water/wastewater manager") == [
        "water manager",
        "wastewater manager",
    ]

    # User requirement 2: "Flight Attendant/Inflight Manager" -> "Flight Attendant", "Inflight Manager"
    assert resolve_slash_compound("Flight Attendant/Inflight Manager") == [
        "Flight Attendant",
        "Inflight Manager",
    ]

    # User requirement 3: "Flight Attendant/Waste/Inflight Manager" -> "Flight Attendant", "Waste Manager", "Inflight Manager"
    assert resolve_slash_compound("Flight Attendant/Waste/Inflight Manager") == [
        "Flight Attendant",
        "Waste Manager",
        "Inflight Manager",
    ]

    # User requirement 4: "Flight Attendant/Waste Doctor/Manager" -> "Flight Attendant", "Waste Doctor", "Waste Manager"
    assert resolve_slash_compound("Flight Attendant/Waste Doctor/Manager") == [
        "Flight Attendant",
        "Waste Doctor",
        "Waste Manager",
    ]

    # User requirement 5: "Water/Doctor" -> "Water Doctor" (splitting may never output single words)
    assert resolve_slash_compound("Water/Doctor") == ["Water Doctor"]

    # Verify clean_term on these slash expressions never emits standalone single words
    water_res = clean_term("water/wastewater manager")
    assert "water" not in water_res
    assert "wastewater" not in water_res
    assert "water manager" in water_res
    assert "wastewater manager" in water_res

    pair_res = clean_term("Water/Doctor")
    assert "water" not in pair_res
    assert "doctor" not in pair_res
    assert "water doctor" in pair_res


def test_clean_term_function_words():
    # Function words like "the", "a", "an", "in", "of" must never be added alone
    assert clean_term("The") == set()
    assert clean_term("of") == set()
    assert clean_term("in") == set()
    # Parenthetical optional words like "Professor of (the) practice"
    terms = clean_term("Professor of (the) practice")
    assert "the" not in terms
    assert "professor of the practice" in terms
    assert "professor of practice" in terms


def test_clean_term_parenthetical():
    # Should extract both the base string and the parenthetical abbreviation
    terms = clean_term("Registered Nurse (RN)")
    assert "rn" in terms
    assert "registered nurse" in terms


def test_clean_term_filters_corporate_and_modifiers():
    # Standalone modifiers should be filtered out
    assert clean_term("Senior") == set()
    assert clean_term("Junior") == set()
    assert clean_term("Lead") == set()
    assert clean_term("Apprentice") == set()
    # Corporate entities should be filtered out
    assert clean_term("Flavelle Roberts Ltd") == set()
    assert clean_term("Acme Corp") == set()
    assert clean_term("Global Solutions LLC") == set()


def test_subsumption_pruning():
    raw_terms = {
        "mechanic",
        "ap mechanic",
        "aircraft mechanic",
        "diesel mechanic",
        "dentist",
        "pediatric dentist",
        "nurse",
        "registered nurse",
        "flight attendant",  # Neither 'flight' nor 'attendant' is in set alone -> kept
    }
    pruned = prune_subsumed_terms(raw_terms)

    # Shorter base terms must be retained
    assert "mechanic" in pruned
    assert "dentist" in pruned
    assert "nurse" in pruned
    assert "flight attendant" in pruned

    # Longer terms subsumed on whole-word boundary must be pruned
    assert "ap mechanic" not in pruned
    assert "aircraft mechanic" not in pruned
    assert "diesel mechanic" not in pruned
    assert "pediatric dentist" not in pruned
    assert "registered nurse" not in pruned

    # An automaton built with pruned terms still matches the full text
    lexicon = OccupationLexicon(pruned)
    assert lexicon.match("I work as an ap mechanic on commercial jets.") == ["mechanic"]
    assert lexicon.match("She is a pediatric dentist.") == ["dentist"]
    assert lexicon.match("He is a flight attendant.") == ["flight attendant"]


def test_word_boundary_matching():
    lexicon = OccupationLexicon(["rn", "swe", "md", "dentist", "electrician"])

    # Valid matches with word boundaries
    assert "rn" in lexicon.match("I am an RN working the night shift.")
    assert "swe" in lexicon.match("Working as a swe at a tech startup.")
    assert "dentist" in lexicon.match("Bio: Pediatric dentist and avid traveler.")
    assert "electrician" in lexicon.match("Proud residential electrician.")

    # Negative matches - substring within longer words must NEVER match
    # 'rn' inside 'modern', 'learning', 'born', 'morning'
    assert "rn" not in lexicon.match("I love modern art and morning coffee.")
    assert "rn" not in lexicon.match("Born and raised in California, learning every day.")

    # 'md' inside 'cmd' or 'amd'
    assert "md" not in lexicon.match("Using cmd and amd graphics.")


def test_hyphenated_matching():
    lexicon = OccupationLexicon(["designer", "web developer", "game designer"])
    # Hyphenated text in input must be matched cleanly
    assert "designer" in lexicon.match("I work as a game-designer.")
    assert "web developer" in lexicon.match("Experienced web-developer based in Austin.")
    # Dashes inside cleaned lexicon terms must be converted to spaces
    assert clean_term("game-designer") == {"game designer"}
    assert clean_term("front-end-engineer") == {"front end engineer"}


def test_lexicon_contains_any():
    lexicon = OccupationLexicon(["dentist", "plumber"])
    assert lexicon.contains_any("I visited my dentist yesterday.") is True
    assert lexicon.contains_any("Going to the grocery store to buy fruit.") is False


if __name__ == "__main__":
    pytest.main(["-v", __file__])
