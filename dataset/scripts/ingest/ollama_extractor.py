"""Ollama-based occupation extractor using Granite-3B with GBNF JSON-array schema enforcement."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Iterable

import ollama

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert occupational entity extractor.
Your task is to identify and extract the occupation(s), profession(s), clinical titles, or trades that the author self-reports in the provided text.

Strict Extraction Rules:
1. Extract self-reported jobs, clinical titles, professions, trades, or industry roles (e.g. "software engineer", "commercial electrician", "video game specialist", "construction worker", "fire chief").
2. REJECT false positives:
   - Do NOT extract recreational hobbies, casual gaming, sports fandom, or consumer interests (e.g. "I love gaming", "gamer", "crypto enthusiast", "football fan"). Note: Professional roles in tech/gaming/trades (e.g. "game designer", "video game specialist") ARE occupations.
   - Do NOT extract educational or student status (e.g. "high school senior", "junior at university", "college student").
   - Do NOT extract medical conditions or symptoms (e.g. "headache", "migraine", "insomnia").
   - Do NOT extract family roles (e.g. "mother of 2", "father", "husband").
   - Do NOT extract company names alone (e.g. "Google", "Amazon").
3. If the author reports multiple distinct occupations (e.g. career switch or dual professions), extract all of them.
4. Capitalize job titles cleanly (e.g. "Software Engineer", "Electrician", "Dentist"). Strip excessive conversational qualifiers.
5. Return ONLY a valid JSON list of strings:
   ["Commercial Electrician"]
   ["High School Teacher", "Software Engineer"]
   [] (if no self-reported occupation is found)
Never output markdown fences, commentary, or wrapper objects. Just the JSON array."""

# Native GBNF JSON array schema enforced by llama.cpp / Ollama
ARRAY_SCHEMA = {
    "type": "array",
    "items": {
        "type": "string"
    }
}


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
            available = [m.model for m in res.models]
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

        prompt = f"Text to extract occupations from:\n\"\"\"{text.strip()}\"\"\""
        try:
            res = self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                format=ARRAY_SCHEMA,
                options={"temperature": self.temperature},
            )
            raw_output = res.message.content or ""
            occupations = self.parse_json_response(raw_output)

            # Clean and sanitize results
            sanitized: list[str] = []
            for occ in occupations:
                occ_clean = occ.strip(" \t\n\r\"'")
                # Filter out obvious false positives that slipped through
                if occ_clean.lower() in {"none", "n/a", "unknown", "headache", "senior", "junior", "student"}:
                    continue
                if len(occ_clean) >= 2:
                    sanitized.append(occ_clean)

            return sanitized
        except Exception as exc:
            logger.error(f"Error querying Ollama extractor: {exc}")
            return []

    def extract_with_screening(self, text: str, lexicon: Any) -> list[str]:
        """Screen with lexicon trie first. If no candidate matches, skip LLM call."""
        if not lexicon.contains_any(text):
            return []
        return self.extract(text)
