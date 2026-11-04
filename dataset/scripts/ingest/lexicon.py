"""High-recall occupation lexicon harvester, cleaner, and Aho-Corasick automaton matcher.

Harvests from:
  1. O*NET Alternate Titles
  2. Wikidata Occupations & Professions (SPARQL)
  3. English Wiktionary Categories (MediaWiki API)
  4. Manual slang, trade abbreviations, and tech/medical/legal acronyms

Features:
  - Delimiter splitting: slashes/pipes (e.g. 'Flight Attendant/Inflight Manager') are split into distinct titles.
  - Corporate entity rejection: companies (e.g. 'ltd', 'inc', 'llc', 'corp', 'gmbh') are strictly filtered.
  - Role-turner nouns: primary occupational suffixes ('worker', 'specialist', 'chief', 'officer', 'manager',
    'director', 'technician', 'operator', 'consultant', etc.) are core entries that match compound professions.
  - Subsumption cleaning: eliminates compound multi-word strings when an existing shorter
    constituent term already matches on whole-word boundaries (e.g. 'ap mechanic' is subsumed by 'mechanic').
  - Word boundary checking in Aho-Corasick automaton to prevent substring false positives.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Iterable, Set

import ahocorasick
import requests

logger = logging.getLogger(__name__)

# Standalone seniority / hierarchy tokens that must never trigger matches alone
# (e.g., 'senior in high school' or 'lead guitar' should not trigger standalone matches)
GENERIC_MODIFIERS: Set[str] = {
    "senior", "junior", "lead", "head", "chief-of-staff",
    "intern", "apprentice", "journeyman", "master", "second",
}

# Corporate legal designators and business entity terms to reject company names
CORPORATE_SUFFIXES: Set[str] = {
    "ltd", "limited", "inc", "incorporated", "llc", "corp", "corporation",
    "gmbh", "plc", "pvt", "pty", "llp", "lp",
}

# Pure grammatical function words (articles, prepositions, conjunctions) that must never enter the lexicon alone
STOP_FUNCTION_WORDS: Set[str] = {
    "the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "for",
    "with", "by", "from", "as", "into", "like", "through", "after",
    "over", "between", "out", "against", "during", "without", "before",
    "under", "around", "among", "is", "it", "its", "this", "that",
}

# High-value domain acronyms and abbreviations
MANUAL_ACRONYMS: Set[str] = {
    # Tech
    "swe", "dev", "sre", "dba", "qa", "devops", "sysadmin", "tpm", "pm",
    # Healthcare
    "rn", "lpn", "np", "cna", "md", "pa", "pt", "ot", "slp", "crna", "emt",
    "dmd", "dds", "pharmd",
    # Legal / Finance / Business
    "cpa", "cfa", "esq", "jd", "mba", "ceo", "cto", "cfo", "coo", "cio", "cso",
    # Trades
    "hvac",
}

# Core occupations and role-turner nouns to guarantee high baseline recall
BASELINE_OCCUPATIONS: Set[str] = {
    # Universal role-turner nouns (words that turn descriptors into occupations)
    "worker", "specialist", "chief", "expert", "operator", "technician",
    "consultant", "analyst", "administrator", "coordinator", "assistant",
    "associate", "agent", "inspector", "supervisor", "examiner", "installer",
    "driver", "clerk", "aide", "manager", "director", "officer", "practitioner",
    "therapist", "instructor", "trainer", "educator", "specialist",
    "executive", "maker", "racer", "tech", "player", "principal", "liaison",
    "scholar", "professional", "crewmember",
    # Tech
    "software engineer", "software developer", "programmer", "data scientist",
    "data engineer", "data analyst", "system administrator", "network engineer",
    "security engineer", "web developer", "frontend developer", "backend developer",
    "fullstack developer", "mobile developer", "ios developer", "android developer",
    "machine learning engineer", "ai engineer", "product manager", "project manager",
    "scrum master", "technical writer", "game developer", "game designer",
    # Medical & Clinical
    "physician", "doctor", "surgeon", "dentist", "orthodontist", "nurse",
    "registered nurse", "nurse practitioner", "paramedic", "pharmacist",
    "radiologist", "anesthesiologist", "cardiologist", "dermatologist",
    "psychiatrist", "psychologist", "physical therapist", "occupational therapist",
    "speech therapist", "dental hygienist", "veterinarian",
    # Legal & Financial
    "lawyer", "attorney", "paralegal", "judge", "accountant", "auditor",
    "actuary", "financial analyst", "investment banker", "tax consultant",
    # Skilled Trades
    "electrician", "plumber", "carpenter", "welder", "machinist", "mechanic",
    "hvac technician", "pipefitter", "roofer", "ironworker", "mason", "painter",
    "locksmith", "blacksmith", "lineman", "boilermaker",
    # Science & Education
    "teacher", "professor", "lecturer", "researcher", "scientist", "biologist",
    "chemist", "physicist", "geologist", "mathematician", "statistician",
    "astronomer", "historian", "sociologist", "economist",
    # Service, Hospitality & Arts
    "chef", "cook", "baker", "barista", "bartender", "waiter", "waitress",
    "librarian", "archivist", "journalist", "reporter", "photographer",
    "graphic designer", "illustrator", "animator", "architect", "interior designer",
    "pilot", "flight attendant", "police officer", "firefighter",
    "social worker", "counselor", "realtor", "real estate agent", "broker",
}


def resolve_slash_compound(term: str) -> list[str]:
    """Smart resolver for slash-separated compound occupational titles.

    Rules:
      1. Single-word modifier before a multi-word title inherits the tail of the next title:
         "water/wastewater manager" -> ["water manager", "wastewater manager"]
      2. Multi-word titles split cleanly:
         "Flight Attendant/Inflight Manager" -> ["Flight Attendant", "Inflight Manager"]
      3. Three+ segments distribute appropriately:
         "Flight Attendant/Waste/Inflight Manager" -> ["Flight Attendant", "Waste Manager", "Inflight Manager"]
         "Flight Attendant/Waste Doctor/Manager" -> ["Flight Attendant", "Waste Doctor", "Waste Manager"]
      4. Slashes never emit standalone single words:
         "Water/Doctor" -> ["Water Doctor"]
    """
    normalized = term.replace("-", " ")
    raw_segments = [s.strip() for s in re.split(r"[/\\|]+", normalized) if s.strip()]
    if len(raw_segments) <= 1:
        return raw_segments

    word_counts = [len(s.split()) for s in raw_segments]
    # If all segments are 1 word, it cannot possibly split without emitting single words
    if all(wc == 1 for wc in word_counts):
        return [" ".join(raw_segments)]

    results: list[str] = []
    for i, seg in enumerate(raw_segments):
        words = seg.split()
        if len(words) >= 2:
            results.append(seg)
        else:
            # 1-word segment: look forward for a following multi-word title to share its tail
            found = False
            for j in range(i + 1, len(raw_segments)):
                other_words = raw_segments[j].split()
                if len(other_words) >= 2:
                    tail = " ".join(other_words[1:])
                    results.append(f"{seg} {tail}")
                    found = True
                    break
            if not found:
                # Look backward for a preceding multi-word title to share its head
                for j in range(i - 1, -1, -1):
                    other_words = raw_segments[j].split()
                    if len(other_words) >= 2:
                        head = " ".join(other_words[:-1])
                        results.append(f"{head} {seg}")
                        found = True
                        break
            if not found:
                results.append(seg)

    # Guarantee: never output single words from slash compounds
    final = [r for r in results if len(r.split()) >= 2]
    if not final:
        return [" ".join(raw_segments)]
    return final


def clean_term(term: str) -> set[str]:
    """Clean a raw occupational term, distributing slashes and filtering corporate/noise tokens."""
    term = term.strip()
    if not term:
        return set()

    results: set[str] = set()

    # 1. Match and extract parenthetical content (e.g. "Registered Nurse (RN)")
    paren_match = re.search(r"\((.*?)\)", term)
    if paren_match:
        inside = paren_match.group(1).strip()
        cleaned_base = re.sub(r"\(.*?\)", "", term).strip()
        if inside:
            inside_lower = inside.lower()
            if inside_lower in STOP_FUNCTION_WORDS:
                # Optional word like "Professor of (the) practice"
                with_word = re.sub(r"\(.*?\)", inside, term).strip()
                results.update(clean_term(with_word))
            else:
                inside_words = inside.split()
                if len(inside_words) == 1:
                    # Single word in paren: keep only if known, verified domain acronym
                    if inside_lower in MANUAL_ACRONYMS:
                        results.update(clean_term(inside))
                else:
                    results.update(clean_term(inside))
        if cleaned_base:
            results.update(clean_term(cleaned_base))
        return results

    # 2. Smart slash/pipe resolver for compound titles
    if any(delim in term for delim in ["/", "\\", "|"]):
        resolved = resolve_slash_compound(term)
        for subterm in resolved:
            results.update(clean_term(subterm))
        return results

    # 3. Convert dashes to spaces and remove non-alphanumeric punctuation
    term_lower = term.lower().replace("-", " ")
    cleaned = re.sub(r"[^\w\s]", "", term_lower).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    # 4. Filter out empty, non-ascii, length < 2, or pure function words
    if len(cleaned) < 2 or not cleaned.isascii():
        return set()

    if cleaned in STOP_FUNCTION_WORDS:
        return set()

    # 5. Reject corporate entities (e.g. contains 'ltd', 'inc', 'llc', 'corp', 'gmbh')
    words = cleaned.split()
    if any(w in CORPORATE_SUFFIXES for w in words):
        return set()

    # 6. Reject standalone generic hierarchy modifiers (e.g. lone "senior" or "junior")
    if cleaned in GENERIC_MODIFIERS:
        return set()

    # 7. For 2-letter tokens, only keep known valid acronyms
    if len(cleaned) == 2 and cleaned not in MANUAL_ACRONYMS:
        return set()

    results.add(cleaned)
    return results


def prune_subsumed_terms(terms: set[str]) -> set[str]:
    """Prune any composite term that is already subsumed by a shorter term on whole-word boundaries.

    For example, if 'mechanic' is in the lexicon, composite variants like 'ap mechanic',
    'auto mechanic', 'aircraft mechanic' are subsumed and removed because matching 'mechanic'
    will already trigger on all of them in text.
    """
    by_word_count: dict[int, list[str]] = {}
    for t in terms:
        wc = len(t.split())
        by_word_count.setdefault(wc, []).append(t)

    accepted: list[str] = []
    auto = ahocorasick.Automaton()

    def check_whole_word_match(text: str, automaton: ahocorasick.Automaton) -> bool:
        text_len = len(text)
        for end_idx, term in automaton.iter(text):
            start_idx = end_idx - len(term) + 1
            # Check boundary before
            if start_idx > 0:
                char_before = text[start_idx - 1]
                if char_before.isalnum() or char_before == "_":
                    continue
            # Check boundary after
            if end_idx + 1 < text_len:
                char_after = text[end_idx + 1]
                if char_after.isalnum() or char_after == "_":
                    continue
            return True
        return False

    # Process incrementally by word count: 1-word terms first, then 2-word, etc.
    for wc in sorted(by_word_count.keys()):
        candidates = sorted(by_word_count[wc], key=lambda x: (len(x), x))
        retained_for_wc: list[str] = []

        if len(auto) == 0:
            retained_for_wc = candidates
        else:
            for c in candidates:
                if not check_whole_word_match(c, auto):
                    retained_for_wc.append(c)

        accepted.extend(retained_for_wc)

        # Rebuild automaton with all accepted terms so far
        auto = ahocorasick.Automaton()
        for a in accepted:
            auto.add_word(a, a)
        auto.make_automaton()

    pruned_count = len(terms) - len(accepted)
    logger.info(f"Subsumption cleaning: {len(terms)} -> {len(accepted)} terms (pruned {pruned_count} redundant compounds)")
    return set(accepted)


def fetch_onet_titles(timeout: int = 15) -> set[str]:
    """Harvest alternate occupational titles from O*NET Center database."""
    url = "https://www.onetcenter.org/dl_files/database/db_20_3_text/Alternate%20Titles.txt"
    titles: set[str] = set()
    try:
        logger.info(f"Fetching O*NET Alternate Titles from {url}...")
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            lines = resp.text.splitlines()
            for line in lines[1:]:  # skip header
                parts = line.split("\t")
                if len(parts) >= 2:
                    raw_title = parts[1]
                    for cleaned in clean_term(raw_title):
                        titles.add(cleaned)
            logger.info(f"Successfully harvested {len(titles)} titles from O*NET.")
        else:
            logger.warning(f"O*NET request returned HTTP {resp.status_code}")
    except Exception as exc:
        logger.warning(f"Failed to fetch O*NET titles: {exc}")
    return titles


def fetch_wikidata_occupations(limit: int = 15000, timeout: int = 25) -> set[str]:
    """Harvest English occupation/profession labels and aliases from Wikidata via SPARQL."""
    url = "https://query.wikidata.org/sparql"
    # Query subclasses of profession (Q28640) and occupation (Q12737077)
    query = f"""
    SELECT DISTINCT ?label ?alias WHERE {{
      {{ ?item wdt:P279* wd:Q28640. }}
      UNION
      {{ ?item wdt:P279* wd:Q12737077. }}
      ?item rdfs:label ?label.
      FILTER(LANG(?label) = "en")
      OPTIONAL {{
        ?item skos:altLabel ?alias.
        FILTER(LANG(?alias) = "en")
      }}
    }}
    LIMIT {limit}
    """
    titles: set[str] = set()
    headers = {
        "User-Agent": "Personality2Occupation/1.0 (academic research; contact@example.com)",
        "Accept": "application/sparql-results+json",
    }
    try:
        logger.info("Querying Wikidata SPARQL for occupations and aliases...")
        resp = requests.get(url, params={"query": query, "format": "json"}, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            bindings = data.get("results", {}).get("bindings", [])
            for row in bindings:
                if "label" in row:
                    for cleaned in clean_term(row["label"]["value"]):
                        titles.add(cleaned)
                if "alias" in row:
                    for cleaned in clean_term(row["alias"]["value"]):
                        titles.add(cleaned)
            logger.info(f"Successfully harvested {len(titles)} titles from Wikidata.")
        else:
            logger.warning(f"Wikidata SPARQL returned HTTP {resp.status_code}")
    except Exception as exc:
        logger.warning(f"Failed to fetch Wikidata occupations: {exc}")
    return titles


def fetch_wiktionary_occupations(timeout: int = 15) -> set[str]:
    """Harvest English occupation terms from Wiktionary Category:en:Occupations."""
    url = "https://en.wiktionary.org/w/api.php"
    titles: set[str] = set()
    categories = [
        "Category:en:Occupations",
        "Category:en:Healthcare occupations",
        "Category:en:Technology occupations",
        "Category:en:Crafts",
    ]
    headers = {"User-Agent": "Personality2Occupation/1.0"}

    for cat in categories:
        try:
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": cat,
                "cmlimit": "500",
                "format": "json",
            }
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                members = data.get("query", {}).get("categorymembers", [])
                for item in members:
                    raw_title = item.get("title", "")
                    if not raw_title.startswith("Category:"):
                        for cleaned in clean_term(raw_title):
                            titles.add(cleaned)
        except Exception as exc:
            logger.warning(f"Failed to fetch Wiktionary category {cat}: {exc}")
            continue

    logger.info(f"Successfully harvested {len(titles)} titles from Wiktionary.")
    return titles


class OccupationLexicon:
    """Aho-Corasick automaton backed lexicon with exact word-boundary matching."""

    def __init__(self, terms: Iterable[str]):
        self.terms: set[str] = set(terms)
        self.automaton = ahocorasick.Automaton()
        for term in self.terms:
            self.automaton.add_word(term, term)
        self.automaton.make_automaton()

    def __len__(self) -> int:
        return len(self.terms)

    def match(self, text: str) -> list[str]:
        """Search text and return matched occupation terms with strict word boundary checks."""
        # Convert dashes/hyphens to spaces before matching
        text_lower = text.lower().replace("-", " ")
        matched: list[str] = []
        text_len = len(text_lower)

        for end_idx, term in self.automaton.iter(text_lower):
            start_idx = end_idx - len(term) + 1

            # Check boundary before term
            if start_idx > 0:
                char_before = text_lower[start_idx - 1]
                if char_before.isalnum() or char_before == "_":
                    continue

            # Check boundary after term
            if end_idx + 1 < text_len:
                char_after = text_lower[end_idx + 1]
                if char_after.isalnum() or char_after == "_":
                    continue

            matched.append(term)

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for m in matched:
            if m not in seen:
                seen.add(m)
                deduped.append(m)
        return deduped

    def contains_any(self, text: str) -> bool:
        """Fast boolean check whether text mentions any occupation term (short-circuits on first match)."""
        text_lower = text.lower().replace("-", " ")
        text_len = len(text_lower)
        for end_idx, term in self.automaton.iter(text_lower):
            start_idx = end_idx - len(term) + 1
            if start_idx > 0:
                char_before = text_lower[start_idx - 1]
                if char_before.isalnum() or char_before == "_":
                    continue
            if end_idx + 1 < text_len:
                char_after = text_lower[end_idx + 1]
                if char_after.isalnum() or char_after == "_":
                    continue
            return True
        return False


def build_or_load_lexicon(
    cache_path: str | Path | None = None,
    force_refresh: bool = False,
    include_remote: bool = True,
) -> OccupationLexicon:
    """Build the full occupation lexicon with subsumption pruning or load from disk cache."""
    if cache_path is None:
        cache_path = Path(__file__).resolve().parents[2] / "cache" / "lexicon.json"
    else:
        cache_path = Path(cache_path)

    if not force_refresh and cache_path.exists():
        logger.info(f"Loading lexicon from cache: {cache_path}")
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                terms = json.load(f)
            logger.info(f"Loaded {len(terms)} terms from cache.")
            return OccupationLexicon(terms)
        except Exception as exc:
            logger.warning(f"Could not read cache ({exc}); rebuilding lexicon...")

    # Start with baseline and acronyms
    all_terms: set[str] = set()
    for t in BASELINE_OCCUPATIONS:
        all_terms.update(clean_term(t))
    for a in MANUAL_ACRONYMS:
        all_terms.update(clean_term(a))

    if include_remote:
        # 1. O*NET
        onet = fetch_onet_titles()
        all_terms.update(onet)

        # 2. Wikidata
        wikidata = fetch_wikidata_occupations()
        all_terms.update(wikidata)

        # 3. Wiktionary
        wiktionary = fetch_wiktionary_occupations()
        all_terms.update(wiktionary)

    # Apply Subsumption Pruning: remove any compound phrase whose constituent
    # subphrase is already an independent term in the lexicon.
    minimal_terms = prune_subsumed_terms(all_terms)

    # Save to cache
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(sorted(minimal_terms), f, indent=2)
        logger.info(f"Saved {len(minimal_terms)} irreducible terms to {cache_path}")
    except Exception as exc:
        logger.warning(f"Failed to cache lexicon: {exc}")

    return OccupationLexicon(minimal_terms)
