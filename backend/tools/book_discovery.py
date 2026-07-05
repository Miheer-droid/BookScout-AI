"""
BookScout AI - Book Discovery Tool
Searches the web to discover candidate books matching user queries.
Deduplicates by title and attempts to enrich results with cover images.
"""

import asyncio
import json
import logging
import re
from typing import Any
from urllib.parse import urlencode

from backend.models.schemas import BookCandidate
from backend.services.scraper_service import ScraperService

logger = logging.getLogger("bookscout.tools.book_discovery")

# Open Library covers endpoint
_OL_COVER_ID_URL = "https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
_OL_COVER_URL = "https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg"
_OL_SEARCH_URL = "https://openlibrary.org/search.json"


class BookDiscoveryTool:
    """
    Discovers candidate books by searching the web with multiple queries,
    deduplicating results, and enriching them with cover images.
    """

    def __init__(self, scraper: ScraperService) -> None:
        self.scraper = scraper

    # ── Public API ───────────────────────────────────────────────

    async def discover_books(
        self,
        queries: list[str],
        max_books: int = 5,
    ) -> list[BookCandidate]:
        """
        Search for books using multiple queries, deduplicate, and return
        BookCandidate objects.

        The tool expands each raw query into several search-engine-friendly
        variants, collects snippets, extracts book metadata from them,
        and returns up to *max_books* unique candidates.

        Args:
            queries: Search queries (e.g. ["machine learning beginner"]).
            max_books: Maximum number of unique books to return.

        Returns:
            List of BookCandidate objects (may be empty on total failure).
        """
        if not queries:
            return []

        # Step 1: Build expanded search queries
        search_queries = self._expand_queries(queries)
        logger.info(
            "[discovery_tool] input queries=%s expanded_count=%d max_books=%d",
            queries,
            len(search_queries),
            max_books,
        )

        # Step 2: Run all searches concurrently
        all_results = await self._run_searches(search_queries)
        logger.info(
            "[discovery_tool] search_results_count=%d",
            len(all_results),
        )

        if not all_results:
            logger.warning("No search results for any discovery query")
            return await self._search_open_library_candidates(queries, max_books)

        # Step 3: Parse raw results into candidate dicts
        raw_candidates = self._parse_candidates(all_results)
        logger.info(
            "[discovery_tool] parsed_candidates_count=%d sample=%s",
            len(raw_candidates),
            raw_candidates[:3],
        )
        if not raw_candidates:
            logger.warning("Search results did not contain parseable book candidates")
            return await self._search_open_library_candidates(queries, max_books)

        # Step 4: Deduplicate by normalized title
        unique = self._deduplicate(raw_candidates, max_books)
        logger.info(
            "[discovery_tool] unique_candidates_count=%d sample=%s",
            len(unique),
            unique[:3],
        )

        # Step 5: Build BookCandidate objects and try to attach covers
        candidates = await self._build_candidates(unique)

        logger.info(f"Discovered {len(candidates)} unique book candidates")
        return candidates

    # ── Private helpers ──────────────────────────────────────────

    def _expand_queries(self, queries: list[str]) -> list[str]:
        """
        Use the planner's search queries directly rather than expanding
        each into 3 variants. The planner already generates diverse,
        search-engine-ready queries — tripling them just multiplies
        latency and rate-limit risk without adding real diversity.
        """
        return list(queries)

    async def _run_searches(
        self, search_queries: list[str]
    ) -> list[dict[str, Any]]:
        """Run all search queries concurrently and merge results."""
        tasks = [
            self.scraper.search_web(sq, max_results=5) for sq in search_queries
        ]
        try:
            results_per_query = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Concurrent search batch failed: {e}")
            return []

        merged: list[dict[str, Any]] = []
        for result in results_per_query:
            if isinstance(result, list):
                merged.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"One search query failed: {result}")
        return merged

    def _parse_candidates(
        self, results: list[dict[str, Any]]
    ) -> list[dict[str, str]]:
        """
        Extract book-like information from search snippets.

        This is intentionally rough — the LLM agent will refine later.
        We look for patterns like "Title by Author" in titles and snippets.
        """
        candidates: list[dict[str, str]] = []

        for r in results:
            title_text = r.get("title", "")
            snippet = r.get("snippet", "")
            url = r.get("url", "")
            combined = f"{title_text} {snippet}"

            # Try to extract "Book Title by Author Name" pattern
            by_match = re.search(
                r"[\"']?(.+?)[\"']?\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})",
                combined,
            )
            if by_match:
                book_title = by_match.group(1).strip().strip("\"'")
                author = by_match.group(2).strip()
                candidates.append({
                    "title": book_title,
                    "author": author,
                    "description": snippet[:300],
                    "source_url": url,
                })
                continue

            # Fallback: use the search result title as-is if it looks book-ish
            if any(kw in combined.lower() for kw in ["book", "edition", "isbn", "paperback", "hardcover"]):
                candidates.append({
                    "title": title_text[:120],
                    "author": "",
                    "description": snippet[:300],
                    "source_url": url,
                })

        return candidates

    @staticmethod
    def _normalize_title(title: str) -> str:
        """Normalize a title for deduplication (lowercase, strip punctuation)."""
        t = title.lower().strip()
        t = re.sub(r"[^\w\s]", "", t)
        t = re.sub(r"\s+", " ", t)
        return t

    def _deduplicate(
        self, candidates: list[dict[str, str]], max_books: int
    ) -> list[dict[str, str]]:
        """Keep only the first occurrence of each normalized title."""
        seen: set[str] = set()
        unique: list[dict[str, str]] = []
        for c in candidates:
            key = self._normalize_title(c.get("title", ""))
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(c)
            if len(unique) >= max_books:
                break
        return unique

    async def _build_candidates(
        self, raw: list[dict[str, str]]
    ) -> list[BookCandidate]:
        """Convert raw dicts to BookCandidate objects, enriching with covers."""
        candidates: list[BookCandidate] = []
        for item in raw:
            title = item.get("title", "Unknown")
            author = item.get("author", "Unknown")

            # Try to get an ISBN and cover from Open Library
            isbn, cover_url = await self._search_open_library(title, author)

            candidates.append(
                BookCandidate(
                    title=title,
                    author=author if author else "Unknown",
                    description=item.get("description", ""),
                    cover_image=cover_url,
                    isbn=isbn,
                )
            )
        return candidates

    async def _search_open_library(
        self, title: str, author: str
    ) -> tuple[str, str]:
        """
        Search Open Library for a book to get its ISBN and cover URL.

        Returns:
            A (isbn, cover_url) tuple. Either or both may be empty strings.
        """
        try:
            query_parts = [f"title={title}"]
            if author and author != "Unknown":
                query_parts.append(f"author={author}")
            search_q = "&".join(query_parts)

            url = f"{_OL_SEARCH_URL}?{search_q}&limit=1&fields=isbn,title,author_name"
            html = await self.scraper.fetch_page(url)
            if not html:
                return "", ""

            import json
            data = json.loads(html)
            docs = data.get("docs", [])
            if not docs:
                return "", ""

            isbns = docs[0].get("isbn", [])
            if not isbns:
                return "", ""

            isbn = isbns[0]
            cover_url = _OL_COVER_URL.format(isbn=isbn)
            return isbn, cover_url

        except Exception as e:
            logger.debug(f"Open Library lookup failed for '{title}': {e}")
            return "", ""

    async def _search_open_library_candidates(
        self,
        queries: list[str],
        max_books: int,
    ) -> list[BookCandidate]:
        """Fallback discovery path when general web search is unavailable."""
        logger.info(
            "[discovery_tool] open_library_fallback input_queries=%s max_books=%d",
            queries,
            max_books,
        )

        docs: list[dict[str, Any]] = []
        for query in self._open_library_queries(queries):
            docs.extend(await self._fetch_open_library_docs(query, max_books))
            if len(docs) >= max_books * 2:
                break

        candidates: list[BookCandidate] = []
        seen: set[str] = set()
        for doc in docs:
            title = doc.get("title", "").strip()
            if not title:
                continue

            author_names = doc.get("author_name", [])
            author = author_names[0] if author_names else "Unknown"
            key = self._normalize_title(f"{title} {author}")
            if key in seen:
                continue
            seen.add(key)

            isbns = doc.get("isbn", [])
            isbn = isbns[0] if isbns else ""
            cover_image = ""
            if isbn:
                cover_image = _OL_COVER_URL.format(isbn=isbn)
            elif doc.get("cover_i"):
                cover_image = _OL_COVER_ID_URL.format(cover_id=doc["cover_i"])

            first_sentence = doc.get("first_sentence", [])
            if isinstance(first_sentence, list):
                description = first_sentence[0] if first_sentence else ""
            else:
                description = str(first_sentence)
            if not description:
                description = doc.get("subtitle", "")

            publishers = doc.get("publisher", [])
            publisher = publishers[0] if publishers else ""

            candidates.append(
                BookCandidate(
                    title=title,
                    author=author,
                    description=description,
                    cover_image=cover_image,
                    publisher=publisher,
                    year=str(doc.get("first_publish_year", "")),
                    isbn=isbn,
                )
            )
            if len(candidates) >= max_books:
                break

        logger.info(
            "[discovery_tool] open_library_fallback output_count=%d sample=%s",
            len(candidates),
            [
                {"title": book.title, "author": book.author}
                for book in candidates[:3]
            ],
        )
        return candidates

    # Words that break Open Library's implicit AND-across-terms search
    # when left in a full conversational sentence.
    _OL_STOPWORDS = (
        r"\b(best|top|rated|recommendation|recommendations|novel|novels|"
        r"book|books|like|similar|to|and|or|with|for|about|gripping|"
        r"great|good|classic|popular|new|scientific|accuracy)\b"
    )

    def _open_library_queries(self, queries: list[str]) -> list[str]:
        """Build forgiving Open Library queries from planner search strings."""
        fallback_queries: list[str] = []
        for query in queries:
            clean = query.strip()
            if not clean:
                continue

            variants = [clean]
            if ":" in clean:
                variants.append(clean.split(":", 1)[0].strip())
            variants.append(re.sub(r"\b(best|top rated|recommendations?)\b", "", clean, flags=re.I).strip())

            # Aggressive keyword-only variant: Open Library's search treats
            # multi-word queries as an implicit AND across every word, so a
            # full conversational sentence ("novels like X and Y") almost
            # never matches a real record. Strip connector/filler words so
            # what's left is closer to actual title/genre tokens.
            keyword_only = re.sub(self._OL_STOPWORDS, "", clean, flags=re.I)
            keyword_only = re.sub(r"\s+", " ", keyword_only).strip()
            if keyword_only:
                variants.append(keyword_only)

            # Extract likely book-title phrases (consecutive capitalized
            # words, e.g. "Project Hail Mary") and search each on its own.
            # This is far more precise than the blended sentence and works
            # even if the stopword list above misses a word.
            for phrase in re.findall(r"\b[A-Z][A-Za-z']*(?:\s+[A-Z][A-Za-z']*){1,4}\b", clean):
                variants.append(phrase.strip())

            for variant in variants:
                variant = re.sub(r"\s+", " ", variant).strip()
                if variant and variant not in fallback_queries:
                    fallback_queries.append(variant)

        joined = " ".join(queries).lower()
        if "python" in joined:
            fallback_queries.extend([
                "python beginner programming",
                "learn python programming",
            ])

        return fallback_queries

    async def _fetch_open_library_docs(
        self,
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Fetch Open Library search docs for one query."""
        params = urlencode({
            "q": query,
            "limit": limit,
            "fields": (
                "title,author_name,first_publish_year,isbn,first_sentence,"
                "publisher,cover_i,subtitle"
            ),
        })
        html = await self.scraper.fetch_page(f"{_OL_SEARCH_URL}?{params}")
        if not html:
            return []

        try:
            data = json.loads(html)
        except json.JSONDecodeError:
            logger.warning("Open Library returned non-JSON search response")
            return []

        docs = data.get("docs", [])
        return docs if isinstance(docs, list) else []
