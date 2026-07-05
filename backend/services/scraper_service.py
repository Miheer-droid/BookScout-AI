"""
BookScout AI - Scraper Service
Provides web scraping and internet search capabilities.
Designed for easy replacement with APIs or MCP tools.
"""

import logging
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from backend.config import settings
from backend.utils.helpers import sanitize_text

logger = logging.getLogger("bookscout")


class ScraperService:
    """
    Service for web scraping and internet search.
    All scraping goes through this service so it can be replaced
    with APIs or MCP tools in future versions.
    """

    def __init__(self):
        self.timeout = settings.REQUEST_TIMEOUT
        self.headers = {
            "User-Agent": settings.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def fetch_page(self, url: str) -> str:
        """
        Fetch a web page and return its HTML content.
        
        Args:
            url: The URL to fetch
            
        Returns:
            Raw HTML string, or empty string on failure
        """
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers=self.headers,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return ""

    async def fetch_text(self, url: str, max_length: int = 5000) -> str:
        """
        Fetch a web page and extract clean text content.
        
        Args:
            url: The URL to fetch
            max_length: Maximum text length to return
            
        Returns:
            Cleaned text content from the page
        """
        html = await self.fetch_page(url)
        if not html:
            return ""

        soup = BeautifulSoup(html, "html.parser")

        # Remove script, style, nav, footer elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)
        return sanitize_text(text, max_length)

    async def search_web(self, query: str, max_results: int = 5) -> list[dict]:
        """
        Search the web using DuckDuckGo.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            
        Returns:
            List of dicts with 'title', 'url', 'snippet' keys
        """
        try:
            from duckduckgo_search import DDGS

            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                    })
            return results
        except Exception as e:
            logger.warning(f"Web search failed for '{query}': {e}")
            return []

    async def search_and_extract(
        self, query: str, max_results: int = 3, max_text_per_page: int = 3000
    ) -> list[dict]:
        """
        Search the web and extract text from each result.
        
        Args:
            query: Search query
            max_results: How many pages to fetch
            max_text_per_page: Max text per page
            
        Returns:
            List of dicts with 'title', 'url', 'snippet', 'content' keys
        """
        search_results = await self.search_web(query, max_results)

        enriched = []
        for result in search_results:
            content = await self.fetch_text(result["url"], max_text_per_page)
            enriched.append({
                **result,
                "content": content,
            })

        return enriched

    def parse_html(self, html: str) -> Optional[BeautifulSoup]:
        """Parse HTML string into a BeautifulSoup object."""
        if not html:
            return None
        try:
            return BeautifulSoup(html, "html.parser")
        except Exception:
            return None
