"""
BookScout AI - Utility Helpers
Common utility functions used across the application.
"""

import re
import json
import logging

logger = logging.getLogger("bookscout")


def sanitize_text(text: str, max_length: int = 5000) -> str:
    """Clean and truncate scraped text content."""
    if not text:
        return ""
    # Remove excess whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove non-printable characters
    text = ''.join(c for c in text if c.isprintable() or c in '\n\t')
    return text[:max_length]


def extract_json_from_response(text: str) -> dict:
    """
    Extract JSON from an LLM response that may contain markdown fences or extra text.
    Tries multiple strategies to find valid JSON.
    """
    if not text:
        return {}

    # Strategy 1: Try parsing the entire text as JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from ```json ... ``` fences
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 3: Find the first { ... } block
    brace_match = re.search(r'\{.*\}', text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    # Strategy 4: Find the first [ ... ] block (for arrays)
    bracket_match = re.search(r'\[.*\]', text, re.DOTALL)
    if bracket_match:
        try:
            result = json.loads(bracket_match.group(0))
            return {"items": result} if isinstance(result, list) else result
        except json.JSONDecodeError:
            pass

    logger.warning("Failed to extract JSON from LLM response")
    return {}


def truncate_text(text: str, max_length: int = 1500) -> str:
    """Truncate text to a maximum length, adding ellipsis if needed."""
    if not text or len(text) <= max_length:
        return text or ""
    return text[:max_length] + "..."


def build_search_query(terms: list[str], site: str = "") -> str:
    """Build a search query string from terms and optional site filter."""
    query = " ".join(terms)
    if site:
        query = f"site:{site} {query}"
    return query
