"""
BookScout AI - Review Scraper Tool
Searches for book reviews across multiple sources and returns raw
review text for the LLM agent to analyze and synthesize.
"""

import asyncio
import logging
from typing import Any

from backend.services.scraper_service import ScraperService

logger = logging.getLogger("bookscout.tools.review_scraper")


class ReviewScraperTool:
    """
    Scrapes book review data from multiple web sources.

    This tool gathers raw review text — the LLM review agent handles
    sentiment analysis, praise/complaint extraction, and summarization.
    """

    def __init__(self, scraper: ScraperService) -> None:
        self.scraper = scraper

    async def research_reviews(self, title: str, author: str) -> dict[str, Any]:
        """
        Search for reviews of a book from multiple sources.

        Queries Reddit, Goodreads, and general web for reviews, then
        returns the raw text for the LLM agent to process.

        Args:
            title: The book title.
            author: The book author.

        Returns:
            Dict with keys:
                - raw_reviews: list of dicts with source, title, snippet, content
                - common_praise: [] (placeholder for LLM)
                - common_complaints: [] (placeholder for LLM)
                - positive_sentiment: "" (placeholder for LLM)
                - negative_sentiment: "" (placeholder for LLM)
                - overall_opinion: "" (placeholder for LLM)
                - summary: "" (placeholder for LLM)
                - confidence: "low" | "medium" | "high"
                - sources_used: list of source names found
        """
        defaults = self._empty_result(title)

        if not title:
            return defaults

        book_str = f"{title} {author}".strip()

        # Two focused queries instead of four — Goodreads/Reddit tend to
        # surface the most substantive reader opinions, and a general
        # review query catches everything else. Fewer calls = faster,
        # less likely to hit search rate limits.
        search_queries = [
            (f"{book_str} review reddit goodreads", "Web"),
            (f"{title} review", "Web"),
        ]

        # Run all searches concurrently
        raw_reviews, sources_used = await self._fetch_reviews(search_queries)

        if not raw_reviews:
            logger.info(f"No reviews found for '{title}'")
            return defaults

        # Calculate confidence based on how many sources we found
        confidence = self._assess_confidence(raw_reviews, sources_used)

        return {
            "raw_reviews": raw_reviews,
            "common_praise": [],
            "common_complaints": [],
            "positive_sentiment": "",
            "negative_sentiment": "",
            "overall_opinion": "",
            "summary": "",
            "confidence": confidence,
            "sources_used": list(sources_used),
        }

    # ── Private helpers ──────────────────────────────────────────

    async def _fetch_reviews(
        self, search_queries: list[tuple[str, str]]
    ) -> tuple[list[dict[str, Any]], set[str]]:
        """
        Execute review search queries concurrently and collect results.

        Returns:
            (raw_reviews, sources_used) tuple.
        """
        tasks = [
            self._search_single(query, source)
            for query, source in search_queries
        ]

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Review search batch failed: {e}")
            return [], set()

        raw_reviews: list[dict[str, Any]] = []
        sources_used: set[str] = set()

        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"One review search failed: {result}")
                continue
            if isinstance(result, list):
                for item in result:
                    raw_reviews.append(item)
                    sources_used.add(item.get("source", "Web"))

        return raw_reviews, sources_used

    async def _search_single(
        self, query: str, source_label: str
    ) -> list[dict[str, Any]]:
        """Run a single search query and tag results with the source."""
        try:
            results = await self.scraper.search_and_extract(
                query, max_results=2
            )
            tagged: list[dict[str, Any]] = []
            for r in results:
                # Detect actual source from URL
                detected_source = self._detect_source(
                    r.get("url", ""), source_label
                )
                tagged.append({
                    "source": detected_source,
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("snippet", ""),
                    "content": r.get("content", ""),
                })
            return tagged
        except Exception as e:
            logger.warning(f"Review search failed for '{query}': {e}")
            return []

    @staticmethod
    def _detect_source(url: str, fallback: str) -> str:
        """Detect the source name from a URL."""
        url_lower = url.lower()
        if "reddit.com" in url_lower:
            return "Reddit"
        if "goodreads.com" in url_lower:
            return "Goodreads"
        if "amazon.com" in url_lower or "amazon.co" in url_lower:
            return "Amazon"
        if "nytimes.com" in url_lower:
            return "NYT"
        if "theguardian.com" in url_lower:
            return "The Guardian"
        if "kirkusreviews.com" in url_lower:
            return "Kirkus"
        if "publishersweekly.com" in url_lower:
            return "Publishers Weekly"
        return fallback

    @staticmethod
    def _assess_confidence(
        raw_reviews: list[dict[str, Any]], sources: set[str]
    ) -> str:
        """Estimate confidence based on volume and diversity of sources."""
        if len(raw_reviews) >= 5 and len(sources) >= 3:
            return "high"
        if len(raw_reviews) >= 2 and len(sources) >= 2:
            return "medium"
        return "low"

    @staticmethod
    def _empty_result(title: str) -> dict[str, Any]:
        """Return the default empty result structure."""
        return {
            "raw_reviews": [],
            "common_praise": [],
            "common_complaints": [],
            "positive_sentiment": "",
            "negative_sentiment": "",
            "overall_opinion": "",
            "summary": "",
            "confidence": "low",
            "sources_used": [],
        }
