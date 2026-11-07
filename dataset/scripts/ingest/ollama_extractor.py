"""Ollama-based occupation extractor using Granite-3B with GBNF JSON-array schema enforcement."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Iterable

import ollama

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert occupational entity extractor.
Your task is to extract the occupation, job title, profession, trade, or workplace role held by the AUTHOR / SPEAKER.

RULES:
1. Return [] (empty list) if:
   - The occupation is held by someone else (third party, provider, or third person):
     * Service encounters or professionals interacting with the author (e.g. "the doctor told me", "the officer gave me", "my therapist recommended", "my lawyer told me"). The author is a patient, client, or recipient, NOT the worker.
     * Hired help or providers, even with "my" or "the" (e.g. "my personal trainer", "called the plumber", "hired a contractor").
     * Third persons, family, or coworkers ("she is a butcher", "he was a driver", "my brother is an electrician").
   - Not currently employed or not yet hired:
     * Job interviews ("interviewed for"), applications ("applied for"), studying for exam/bar ("studying for the bar exam"), seeking services ("looking for a plumber").
   - Future plans without concrete details:
     * Return [] if vague or distant with no concrete schedule (e.g. "I'm going to work at [company]", "in a few years", "hoping to work").
     * DO NOT extract future jobs unless there is a concrete near-term timeframe, location, or coworker.
   - Figurative speech: metaphors, idioms, costumes, insults, hobbies, or personal status ("real butcher", "boss is a clown", "Halloween costume", "computer whiz", "mother of two").
   - Company promotional accounts or degree lists without an occupation ("Cleaning LLC", "BS + MBA").

2. Extract the occupation if the AUTHOR / SPEAKER:
   - Currently works in, holds, or reports their own job, trade, or role (e.g. "I work as...", "I drive a school bus", "I bag groceries").
   - Past, quit, or former jobs held by the author (e.g. "I quit my cashier job", "former beat reporter", "retired hotelier", "retired horticulturist").
   - Works in a sector or organization (e.g. "work in tech" -> ["Tech Worker"], "work for a non-profit" -> ["Non-Profit Worker"]).
   - States their professional, creative, or academic title in a bio (e.g. Researcher, Professor, Author, Artist, Tech Writer, Correspondent, Critic, Physician, Hotelier).
   - Has a concrete planned job with a specific near-term timeframe (e.g. "this summer", "in winter", "this holiday"), location (e.g. "downtown"), or coworker (e.g. "with [name]").

Output ONLY a JSON array of strings, e.g. ["Software Engineer"] or []."""

# Native GBNF JSON array schema enforced by llama.cpp / Ollama
ARRAY_SCHEMA = {
    "type": "array",
    "items": {
        "type": "string"
    }
}

GENERIC_STANDALONE = {
    "none", "n/a", "unknown", "headache", "senior", "junior", "student",
    "job", "work", "other job", "profession", "occupation", "career",
    "employment", "employee", "worker", "tradesmen", "tradesman",
    "full time", "part time", "unemployed", "job title", "title"
}

BANNED_WORDS_PATTERN = re.compile(
    r"\b(hey|sorry|hello|please|unspecified|temp|old|job\s+seeker|job\s+applicant)\b",
    re.IGNORECASE,
)


def sanitize_occupation_title(occ: str) -> str | None:
    """Sanitizes an extracted occupation string according to project rules:
    - Strips surrounding whitespace and quotes.
    - Rejects strings with >= 15 words.
    - Rejects whole-word matches of conversational/status terms: hey, sorry, hello, please, unspecified, temp, old, job seeker, job applicant.
    - Handles commas:
        * If a comma is inside a parentheses section, strips that parenthetical section (e.g. 'VP (e.g., VP of Ops, ...)' -> 'VP').
        * If any comma remains outside parentheses (e.g. 'VP of Ops, VP of Mktg'), rejects the entire title.
    - Rejects standalone generic words or strings < 2 chars.
    """
    if not occ:
        return None
    cleaned = occ.strip(" \t\n\r\"'")
    if not cleaned:
        return None

    # 1. Word count limit (>= 15 words -> reject conversational rants)
    if len(cleaned.split()) >= 15:
        return None

    # 2. Whole word matches of banned terms
    if BANNED_WORDS_PATTERN.search(cleaned):
        return None

    # 3. Comma and parentheses handling:
    # If a parenthetical section contains a comma, strip that parenthetical section
    def _strip_paren_if_comma(match: re.Match) -> str:
        content = match.group(0)
        if "," in content:
            return ""
        return content

    cleaned = re.sub(r"\s*\([^)]*\)", _strip_paren_if_comma, cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" \t\n\r\"'")

    # If any comma remains, reject the whole occupation
    if "," in cleaned:
        return None

    # 4. Filter generic standalone words and short tokens
    if cleaned.lower() in GENERIC_STANDALONE:
        return None
    if len(cleaned) < 2:
        return None

    return cleaned


class OllamaOccupationExtractor:
    """Extractor calling local Ollama instance with schema-constrained decoding and noise filtering."""

    def __init__(
        self,
        model: str = "granite4.1:3b",
        host: str | None = None,
        temperature: float = 0.0,
        timeout: int = 30,
    ):
        self.host = host
        self.temperature = temperature
        self.timeout = timeout
        self.client = ollama.Client(host=host) if host else ollama.Client()
        self.model = self._resolve_model(model)

    def _resolve_model(self, requested_model: str) -> str:
        """Find requested model or fallback to available model in Ollama."""
        try:
            res = self.client.list()
            models_list = getattr(res, "models", []) or []
            available: list[str] = [
                str(m.model)
                for m in models_list
                if getattr(m, "model", None) is not None
            ]
            # Exact match
            if requested_model in available:
                return requested_model
            # Prefix match
            req_prefix = requested_model.split(":")[0]
            for a in available:
                if a.startswith(req_prefix):
                    logger.info(f"Resolved model '{requested_model}' to available '{a}'")
                    return a
            # Fallback to first available if requested model not found
            if available:
                fallback = available[0]
                logger.warning(
                    f"Model '{requested_model}' not found in Ollama ({available}). Falling back to '{fallback}'."
                )
                return fallback
        except Exception as exc:
            logger.warning(f"Could not connect to Ollama to list models ({exc}). Using '{requested_model}'.")
        return requested_model

    def parse_json_response(self, content: str) -> list[str]:
        """Safely parse JSON list from LLM output, handling markdown fences and edge cases."""
        content = content.strip()
        if not content:
            return []

        # Strip markdown fences if present
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"\s*```$", "", content)
            content = content.strip()

        # Direct JSON decode
        try:
            parsed = json.loads(content)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if isinstance(item, (str, int)) and str(item).strip()]
            if isinstance(parsed, dict):
                # If wrapped in a dictionary
                for val in parsed.values():
                    if isinstance(val, list):
                        return [str(item).strip() for item in val if isinstance(item, (str, int)) and str(item).strip()]
        except Exception:
            pass

        # Regex fallback for array [ ... ]
        array_match = re.search(r"\[(.*?)\]", content, flags=re.DOTALL)
        if array_match:
            try:
                candidate = f"[{array_match.group(1)}]"
                parsed = json.loads(candidate)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except Exception:
                items = re.findall(r'"([^"]+)"', array_match.group(1))
                if items:
                    return [item.strip() for item in items if item.strip()]

        return []

    def extract(self, text: str) -> list[str]:
        """Extract occupations from a text snippet using schema-constrained generation."""
        if not text or not text.strip():
            return []

        prompt = text.strip()
        try:
            res = self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                format=ARRAY_SCHEMA,
                options={"temperature": self.temperature, "num_ctx": 1024},
            )
            raw_output = res.message.content or ""
            occupations = self.parse_json_response(raw_output)

            # Clean and sanitize results using standard project rules
            sanitized: list[str] = []
            for occ in occupations:
                clean_title = sanitize_occupation_title(occ)
                if clean_title:
                    sanitized.append(clean_title)

            return sanitized
        except Exception as exc:
            logger.error(f"Error querying Ollama extractor: {exc}")
            return []

    def extract_with_screening(self, text: str, lexicon: Any) -> list[str]:
        """Screen with lexicon trie first. If no candidate matches, skip LLM call."""
        if not lexicon.contains_any(text):
            return []
        return self.extract(text)
