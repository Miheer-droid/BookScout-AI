"""
BookScout AI - Price Scraper Tool
Searches for book prices, availability, and free reading options.
Checks Open Library for free access and searches the web for purchase options.
"""

import asyncio
import logging
from typing import Any

from backend.services.scraper_service import ScraperService

logger = logging.getLogger("bookscout.tools.price_scraper")

_OL_SEARCH_URL = "https://openlibrary.org/search.json"


class PriceScraperTool:
    """
    Scrapes book pricing and availability information.

    Checks Open Library for free reading options and searches the web
    for purchase prices. Returns raw data for the LLM pricing agent
    to structure into PriceOption / PriceResearch objects.
    """

    def __init__(self, scraper: ScraperService) -> None:
        self.scraper = scraper

    async def research_prices(self, title: str, author: str) -> dict[str, Any]:
        """
        Search for book prices and availability.

        Checks Open Library for free reading and searches the web for
        purchase options across formats (paperback, hardcover, ebook).

        Args:
            title: The book title.
            author: The book author.

        Returns:
            Dict with keys:
                - raw_results: list of dicts with search snippets about pricing
                - free_options: list of URLs where the book can be read for free
                - sources_used: list of source names
        """
        defaults: dict[str, Any] = {
            "raw_results": [],
            "free_options": [],
            "sources_used": [],
        }

        if not title:
            return defaults

        # Run free-option check and price search concurrently
        free_task = self._check_open_library(title, author)
        price_task = self._search_prices(title, author)

        try:
            free_results, price_results = await asyncio.gather(
                free_task, price_task, return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Price research failed for '{title}': {e}")
            return defaults

        # Process free options
        free_options: list[str] = []
        if isinstance(free_results, list):
            free_options = free_results
        elif isinstance(free_results, Exception):
            logger.warning(f"Open Library check failed: {free_results}")

        # Process price results
        raw_results: list[dict[str, Any]] = []
        sources_used: set[str] = set()
        if isinstance(price_results, list):
            for item in price_results:
                raw_results.append(item)
                sources_used.add(item.get("source", "Web"))
        elif isinstance(price_results, Exception):
            logger.warning(f"Price search failed: {price_results}")

        if free_options:
            sources_used.add("Open Library")

        return {
            "raw_results": raw_results,
            "free_options": free_options,
            "sources_used": list(sources_used),
        }

    # ── Private helpers ──────────────────────────────────────────

    async def _check_open_library(
        self, title: str, author: str
    ) -> list[str]:
        """
        Check Open Library for free reading options.

        Returns:
            List of URLs where the book can be read for free.
        """
        try:
            query_parts = [f"title={title}"]
            if author and author != "Unknown":
                query_parts.append(f"author={author}")
            search_q = "&".join(query_parts)

            url = f"{_OL_SEARCH_URL}?{search_q}&limit=3&fields=key,title,has_fulltext,ia"
            html = await self.scraper.fetch_page(url)
            if not html:
                return []

            import json
            data = json.loads(html)
            docs = data.get("docs", [])

            free_urls: list[str] = []
            for doc in docs:
                # has_fulltext indicates the book is readable on Open Library
                if doc.get("has_fulltext"):
                    ol_key = doc.get("key", "")
                    if ol_key:
                        free_urls.append(f"https://openlibrary.org{ol_key}")

                # Internet Archive identifiers
                ia_ids = doc.get("ia", [])
                for ia_id in ia_ids[:1]:  # Take first IA copy
                    free_urls.append(f"https://archive.org/details/{ia_id}")

            return free_urls

        except Exception as e:
            logger.debug(f"Open Library check failed for '{title}': {e}")
            return []

    async def _search_prices(
        self, title: str, author: str
    ) -> list[dict[str, Any]]:
        """Search the web for book prices across formats."""
        book_str = f"{title} {author}".strip()

        search_queries = [
            (f"{book_str} buy paperback ebook kindle price", "Retail"),
            (f"{book_str} book price comparison", "Comparison"),
        ]

        tasks = [
            self._search_single(query, source)
            for query, source in search_queries
        ]

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Price search batch failed: {e}")
            return []

        all_results: list[dict[str, Any]] = []
        for result in results:
            if isinstance(result, list):
                all_results.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"One price search failed: {result}")

        return all_results

    async def _search_single(
        self, query: str, source_label: str
    ) -> list[dict[str, Any]]:
        """Run a single price search and tag results."""
        try:
            results = await self.scraper.search_web(query, max_results=3)
            tagged: list[dict[str, Any]] = []
            for r in results:
                detected = self._detect_store(r.get("url", ""), source_label)
                tagged.append({
                    "source": detected,
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("snippet", ""),
                })
            return tagged
        except Exception as e:
            logger.warning(f"Price search failed for '{query}': {e}")
            return []

    @staticmethod
    def _detect_store(url: str, fallback: str) -> str:
        """Detect the store name from a URL."""
        url_lower = url.lower()
        if "amazon.com" in url_lower or "amazon.co" in url_lower:
            return "Amazon"
        if "barnesandnoble.com" in url_lower or "bn.com" in url_lower:
            return "Barnes & Noble"
        if "bookdepository.com" in url_lower:
            return "Book Depository"
        if "thriftbooks.com" in url_lower:
            return "ThriftBooks"
        if "abebooks.com" in url_lower:
            return "AbeBooks"
        if "google.com/books" in url_lower:
            return "Google Books"
        if "kobo.com" in url_lower:
            return "Kobo"
        if "apple.com/books" in url_lower or "books.apple" in url_lower:
            return "Apple Books"
        if "openlibrary.org" in url_lower:
            return "Open Library"
        return fallback
