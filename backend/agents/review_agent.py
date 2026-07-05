"""
BookScout AI - Review Agent
Researches and analyzes reviews for a single book.
"""

import logging
from backend.services.llm_service import LLMService
from backend.tools import ReviewScraperTool
from backend.models.schemas import BookCandidate, UserIntent, ReviewResearch
from backend.agents.base_agent import BaseAgent

logger = logging.getLogger("bookscout")

SYSTEM_PROMPT = (
    "You are a book review analyst. You synthesize raw review data from "
    "multiple sources into a clear, balanced assessment of a book's "
    "strengths, weaknesses, and overall reception."
)


class ReviewAgent(BaseAgent):
    """Researches and analyzes reviews for a single book."""

    def __init__(self, llm: LLMService, review_tool: ReviewScraperTool) -> None:
        super().__init__(llm, "review")
        self.review_tool = review_tool

    async def research(self, book: BookCandidate, intent: UserIntent) -> ReviewResearch:
        """
        Research reviews for a specific book.

        Args:
            book: The book to research
            intent: The user's intent (for context-aware analysis)

        Returns:
            ReviewResearch with structured review analysis
        """
        # Step 1: Gather raw review data using the tool
        try:
            raw_data = await self.review_tool.research_reviews(
                title=book.title,
                author=book.author,
            )
        except Exception as e:
            logger.error(f"[review] Tool failed for '{book.title}': {e}")
            raw_data = {}

        # Step 2: Use LLM to analyze the raw review data
        raw_summary = str(raw_data) if raw_data else "No review data was found."

        prompt = f"""Analyze the following raw review data for a book and produce a structured review summary.

BOOK: "{book.title}" by {book.author}
DESCRIPTION: {book.description}

READER'S GOAL: {intent.goal}
READER'S LEVEL: {intent.reading_level}

RAW REVIEW DATA:
{raw_summary[:4000]}

Based on this data, produce a JSON object with EXACTLY these keys:
{{
  "book_title": "{book.title}",
  "common_praise": ["List of 2-5 things reviewers commonly praise"],
  "common_complaints": ["List of 1-3 things reviewers commonly criticize"],
  "positive_sentiment": "A brief summary of the positive consensus (1-2 sentences)",
  "negative_sentiment": "A brief summary of negative feedback (1-2 sentences)",
  "overall_opinion": "The overall consensus in one sentence",
  "summary": "A 2-3 sentence balanced summary of reviews, mentioning relevance to the reader's goal: {intent.goal}",
  "confidence": "low, medium, or high — based on how much review data was available",
  "sources_used": ["List of source names or URLs that contributed data"]
}}

Rules:
- If no review data was found, set confidence to "low" and provide your best general knowledge.
- Be balanced — include both positives and negatives.
- Relate the review analysis back to the reader's stated goal."""

        data = await self._ask_json(prompt, SYSTEM_PROMPT)

        if not data:
            logger.warning(f"[review] LLM returned no analysis for '{book.title}'")
            return ReviewResearch(
                book_title=book.title,
                overall_opinion="No review data available",
                confidence="low",
            )

        try:
            return ReviewResearch(
                book_title=data.get("book_title", book.title),
                common_praise=data.get("common_praise", []),
                common_complaints=data.get("common_complaints", []),
                positive_sentiment=data.get("positive_sentiment", ""),
                negative_sentiment=data.get("negative_sentiment", ""),
                overall_opinion=data.get("overall_opinion", ""),
                summary=data.get("summary", ""),
                confidence=data.get("confidence", "medium"),
                sources_used=data.get("sources_used", []),
            )
        except Exception as e:
            logger.error(f"[review] Failed to build ReviewResearch: {e}")
            return ReviewResearch(
                book_title=book.title,
                overall_opinion="Analysis failed",
                confidence="low",
            )
