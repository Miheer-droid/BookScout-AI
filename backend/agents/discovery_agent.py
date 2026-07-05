"""
BookScout AI - Discovery Agent
Finds candidate books using search tools and LLM validation.
"""

import logging
from backend.services.llm_service import LLMService
from backend.tools import BookDiscoveryTool
from backend.models.schemas import ResearchPlan, BookCandidate
from backend.agents.base_agent import BaseAgent

logger = logging.getLogger("bookscout")

SYSTEM_PROMPT = (
    "You are a book discovery expert. Your job is to validate and enrich "
    "a list of candidate books, filling in missing information and filtering "
    "out irrelevant results."
)


class DiscoveryAgent(BaseAgent):
    """Discovers candidate books using tools and LLM validation."""

    def __init__(self, llm: LLMService, book_tool: BookDiscoveryTool) -> None:
        super().__init__(llm, "discovery")
        self.book_tool = book_tool

    async def discover(self, plan: ResearchPlan) -> list[BookCandidate]:
        """
        Find candidate books matching the research plan.

        Args:
            plan: The research plan with search queries

        Returns:
            A list of 3-5 validated BookCandidate objects
        """
        # Step 1: Use the book discovery tool to find raw candidates
        try:
            raw_candidates = await self.book_tool.discover_books(
                queries=plan.search_queries,
                max_books=plan.target_count + 3,  # Fetch extras for filtering
            )
        except Exception as e:
            logger.error(f"[discovery] Book discovery tool failed: {e}")
            raw_candidates = []

        if not raw_candidates:
            logger.warning("[discovery] No candidates found from tool")
            return []

        # Step 2: Use LLM to validate and enrich candidates
        candidates_text = ""
        for i, c in enumerate(raw_candidates):
            candidate = c.model_dump() if isinstance(c, BookCandidate) else c
            entry = (
                f"Book {i + 1}:\n"
                f"  Title: {candidate.get('title', 'Unknown')}\n"
                f"  Author: {candidate.get('author', 'Unknown')}\n"
                f"  Description: {candidate.get('description', 'N/A')}\n"
                f"  Publisher: {candidate.get('publisher', 'N/A')}\n"
                f"  Year: {candidate.get('year', 'N/A')}\n"
                f"  ISBN: {candidate.get('isbn', 'N/A')}\n"
            )
            candidates_text += entry + "\n"

        prompt = f"""I found these candidate books for a research plan focused on: {plan.book_type}
Focus areas: {', '.join(plan.focus_areas)}
Level filter: {plan.level_filter}

RAW CANDIDATES:
{candidates_text}

Your tasks:
1. Remove any duplicates (same book listed twice).
2. Remove books that are clearly irrelevant to the focus areas.
3. Fill in missing descriptions where possible from your knowledge.
4. Keep the best {plan.target_count} candidates (between 3 and 5).

Return a JSON object with this structure:
{{
  "books": [
    {{
      "title": "Book Title",
      "author": "Author Name",
      "description": "A 1-2 sentence description of the book",
      "cover_image": "",
      "publisher": "Publisher if known, else empty string",
      "edition": "Edition info if known, else empty string",
      "year": "Publication year if known, else empty string",
      "isbn": "ISBN if known, else empty string"
    }}
  ]
}}

Return between 3 and 5 books. Prioritize well-known, highly-regarded books."""

        data = await self._ask_json(prompt, SYSTEM_PROMPT)

        if isinstance(data, list):
            books_data = data
        else:
            books_data = data.get("books", [])
        if not books_data:
            # Fallback: convert raw candidates directly
            logger.warning("[discovery] LLM validation returned no books, using raw data")
            books_data = raw_candidates[:plan.target_count]

        result: list[BookCandidate] = []
        for b in books_data[:5]:  # Hard cap at 5
            book_data = b.model_dump() if isinstance(b, BookCandidate) else b
            try:
                result.append(BookCandidate(
                    title=book_data.get("title", "Unknown"),
                    author=book_data.get("author", "Unknown"),
                    description=book_data.get("description", ""),
                    cover_image=book_data.get("cover_image", ""),
                    publisher=book_data.get("publisher", ""),
                    edition=book_data.get("edition", ""),
                    year=book_data.get("year", ""),
                    isbn=book_data.get("isbn", ""),
                ))
            except Exception as e:
                logger.warning(f"[discovery] Skipping invalid candidate: {e}")

        logger.info(f"[discovery] Returning {len(result)} validated candidates")
        return result
