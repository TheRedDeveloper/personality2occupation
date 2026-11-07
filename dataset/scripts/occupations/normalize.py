"""Rule-based normalization for occupational titles.

Cleans raw self-reported occupation strings by:
1. Stripping emojis, trademark/copyright symbols, and noise tokens.
2. Normalizing unicode accents (NFKD) and standardizing apostrophes/quotes.
3. Lowercasing and cleaning delimiters/punctuation.
4. Stripping seniority and status prefixes (senior, junior, lead, staff,
   principal, apprentice, intern, assistant, associate, retired, former)
   while protecting semantic edge cases (e.g., 'junior high', 'lead generation',
   'assistant to', standalone titles like 'vice president', 'principal', 'intern').
5. Preserving domain/company qualifiers (e.g. 'wendy's employee') for dense semantic clustering.
"""

import re
import unicodedata
from typing import List, Optional


# Contexts where words like 'junior', 'lead', 'assistant', 'staff' have specific semantic meanings
# and should NOT be stripped as seniority prefixes.
PROTECTED_PREFIX_PATTERNS = [
    re.compile(r'\bjunior\s+high\b', re.IGNORECASE),
    re.compile(r'\blead\s+gen(eration)?\b', re.IGNORECASE),
    re.compile(r'\bassistant\s+to\b', re.IGNORECASE),
    re.compile(r'\bchief\s+of\s+staff\b', re.IGNORECASE),
]

# Seniority & status prefix regex (only matches at the start of the string)
SENIORITY_PREFIX_REGEX = re.compile(
    r'^(senior|sr|junior|jr|lead|staff|principal|apprentice|intern|assistant|associate|retired|former)\s+',
    re.IGNORECASE
)

# Meaningless residual tokens that shouldn't stand alone if prefix is stripped
MEANINGLESS_REMAINDERS = {'', 'of', 'for', 'the', 'at', 'in', 'to', 'and', 'a', 'an'}


def normalize_title(title: Optional[str]) -> str:
    """Normalize a raw occupation title.
    
    Args:
        title: Raw title string (e.g., "Senior Software Engineer", "Vice President", "Wendy's Employee").
        
    Returns:
        Cleaned, normalized title string, or empty string if input is invalid/empty.
    """
    if not title or not isinstance(title, str):
        return ""

    text = title.strip()
    if not text:
        return ""

    # 1. Normalize apostrophes, quotes, and common punctuation variations first
    text = re.sub(r"[’'ʻ‘`]", "'", text)

    # 2. Unicode normalization: convert accented letters to ASCII base (e.g. é -> e)
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))

    # 3. Comprehensive symbol, emoji, punctuation, and noise character replacement:
    # Replaces all non-alphanumeric characters (except apostrophe and hyphen) with spaces
    # so adjacent words are separated cleanly and emojis/symbols never fuse words together.
    text = re.sub(r"[^a-zA-Z0-9\s'-]", ' ', text)

    # 4. Lowercase
    text = text.lower()

    # 5. Collapse hyphens to spaces
    text = re.sub(r'-+', ' ', text)

    # 6. Clean apostrophes: preserve possessives like "wendy's" or "children's", remove stray quotes
    text = re.sub(r"\b's\b", "'s", text)
    text = re.sub(r"(?<![a-z])'|'(?![a-z])", " ", text)

    # 7. Collapse multiple whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    if not text:
        return ""

    # 10. Check protected semantic phrases
    for pattern in PROTECTED_PREFIX_PATTERNS:
        if pattern.search(text):
            return text

    # 11. Seniority & status prefix stripping
    match = SENIORITY_PREFIX_REGEX.match(text)
    if match:
        remainder = text[match.end():].strip()
        # Only strip prefix if remainder has meaningful substance
        if remainder and len(remainder) > 1 and remainder not in MEANINGLESS_REMAINDERS:
            text = remainder

    return text


def normalize_titles_list(titles: List[str]) -> List[str]:
    """Normalize a list of occupation titles, deduplicating and omitting empties.
    
    Args:
        titles: List of raw title strings.
        
    Returns:
        List of cleaned, unique title strings.
    """
    cleaned_list = []
    seen = set()
    for t in titles:
        cleaned = normalize_title(t)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            cleaned_list.append(cleaned)
    return cleaned_list
