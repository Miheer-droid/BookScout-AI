"""
BookScout AI - Reading Analysis Tool
Searches for reading difficulty, level, and prerequisite information
about a book. Returns raw data for the LLM agent to interpret.
"""

import asyncio
import logging
from typing import Any

from backend.services.scraper_service import ScraperService

logger = logging.getLogger("bookscout.tools.reading_analysis")


class ReadingAnalysisTool:
    """
    Gathers information about a book's reading difficulty, prerequisites,
    and suitability for different reader levels.

    This tool collects raw web data — the LLM reading-analysis agent
    handles interpretation and scoring.
    """

    def __init__(self, scraper: ScraperService) -> None:
        self.scraper = scraper

    async def analyze_reading(self, title: str, author: str) -> dict[str, Any]:
        """
        Search for reading difficulty and prerequisite information.

        Searches multiple queries related to reading level, difficulty,
        and prerequisites, then returns the raw results.

        Args:
            title: The book title.
            author: The book author.

        Returns:
            Dict with keys:
                - raw_results: list of dicts with search snippets
                  about difficulty and reading level
                - sources_used: list of source names
        """
        defaults: dict[str, Any] = {
            "raw_results": [],
            "sources_used": [],
        }

        if not title:
            return defaults

        book_str = f"{title} {author}".strip()

        search_queries = [
            f"{title} reading level difficulty prerequisites",
            f"{book_str} who is this book for how long to read",
        ]

        # Run all searches concurrently
        tasks = [
            self._search_single(query) for query in search_queries
        ]

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Reading analysis search failed for '{title}': {e}")
            return defaults

        raw_results: list[dict[str, Any]] = []
        sources_used: set[str] = set()

        for result in results:
            if isinstance(result, list):
                for item in result:
                    raw_results.append(item)
                    sources_used.add(item.get("source", "Web"))
            elif isinstance(result, Exception):
                logger.warning(f"One reading-analysis search failed: {result}")

        if not raw_results:
            logger.info(f"No reading analysis data found for '{title}'")
            return defaults

        return {
            "raw_results": raw_results,
            "sources_used": list(sources_used),
        }

    # ── Private helpers ──────────────────────────────────────────

    async def _search_single(self, query: str) -> list[dict[str, Any]]:
        """Run a single search and tag results with detected source."""
        try:
            results = await self.scraper.search_web(query, max_results=3)
            tagged: list[dict[str, Any]] = []
            for r in results:
                source = self._detect_source(r.get("url", ""))
                tagged.append({
                    "source": source,
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("snippet", ""),
                })
            return tagged
        except Exception as e:
            logger.warning(f"Reading analysis search failed for '{query}': {e}")
            return []

    @staticmethod
    def _detect_source(url: str) -> str:
        """Detect a human-readable source name from a URL."""
        url_lower = url.lower()
        if "goodreads.com" in url_lower:
            return "Goodreads"
        if "reddit.com" in url_lower:
            return "Reddit"
        if "amazon.com" in url_lower or "amazon.co" in url_lower:
            return "Amazon"
        if "lexile.com" in url_lower:
            return "Lexile"
        if "commonsensemedia.org" in url_lower:
            return "Common Sense Media"
        if "wikipedia.org" in url_lower:
            return "Wikipedia"
        if "howlongtoread.com" in url_lower:
            return "How Long to Read"
        return "Web"
