"""
BookScout AI - Reading Agent
Analyzes reading difficulty and fit for a single book.
"""

import logging
from backend.services.llm_service import LLMService
from backend.tools import ReadingAnalysisTool
from backend.models.schemas import BookCandidate, UserIntent, ReadingAnalysis
from backend.agents.base_agent import BaseAgent

logger = logging.getLogger("bookscout")

SYSTEM_PROMPT = (
    "You are a reading difficulty analyst. You assess books for their "
    "difficulty level, prerequisites, writing style, and how well they "
    "fit a specific reader's needs and level."
)


class ReadingAgent(BaseAgent):
    """Analyzes reading difficulty and fit for a single book."""

    def __init__(self, llm: LLMService, reading_tool: ReadingAnalysisTool) -> None:
        super().__init__(llm, "reading")
        self.reading_tool = reading_tool

    async def analyze(self, book: BookCandidate, intent: UserIntent) -> ReadingAnalysis:
        """
        Analyze reading difficulty and fit for a specific book.

        Args:
            book: The book to analyze
            intent: The user's intent (for fit assessment)

        Returns:
            ReadingAnalysis with difficulty, prerequisites, and fit assessment
        """
        # Step 1: Gather raw analysis data
        try:
            raw_data = await self.reading_tool.analyze_reading(
                title=book.title,
                author=book.author,
            )
        except Exception as e:
            logger.error(f"[reading] Tool failed for '{book.title}': {e}")
            raw_data = {}

        # Step 2: Use LLM to produce structured analysis
        raw_summary = str(raw_data) if raw_data else "No analysis data was found."

        prompt = f"""Analyze the reading difficulty and reader-fit for this book.

BOOK: "{book.title}" by {book.author}
DESCRIPTION: {book.description}
EDITION: {book.edition or 'unknown'}

READER PROFILE:
- Goal: {intent.goal}
- Reading Level: {intent.reading_level}
- Interests: {', '.join(intent.interests) if intent.interests else 'not specified'}
- Likes: {', '.join(intent.likes) if intent.likes else 'not specified'}
- Dislikes: {', '.join(intent.dislikes) if intent.dislikes else 'not specified'}
- Learning Objectives: {', '.join(intent.learning_objectives) if intent.learning_objectives else 'not specified'}
- Preferred Style: {intent.preferred_style or 'not specified'}

RAW ANALYSIS DATA:
{raw_summary[:4000]}

Return a JSON object with EXACTLY these keys:
{{
  "book_title": "{book.title}",
  "difficulty": "One of: easy, moderate, challenging, advanced",
  "reading_level": "Who this book is best suited for (e.g., 'beginners with some programming experience')",
  "prerequisites": ["List of things the reader should know before reading this book"],
  "writing_style": "Describe the writing style (e.g., 'conversational with many code examples', 'academic and dense')",
  "fits_request": true or false,
  "fit_explanation": "Why this book does or does not fit this specific reader (2-3 sentences, reference their stated goal and level)",
  "edition_notes": "Any notes about editions — is this the latest? Is an older edition fine? Empty string if not relevant.",
  "estimated_reading_time": "Rough estimate (e.g., '15-20 hours', '2-3 weeks at 1hr/day')"
}}

Rules:
- Be honest about difficulty — don't sugarcoat a challenging book.
- fits_request should be false if there's a clear mismatch (e.g., advanced book for a beginner, unless the reader explicitly wants a challenge).
- prerequisites should be specific, not vague (e.g., 'basic Python syntax' not just 'programming knowledge').
- If no data is available, use your general knowledge of the book."""

        data = await self._ask_json(prompt, SYSTEM_PROMPT)

        if not data:
            logger.warning(f"[reading] LLM returned no analysis for '{book.title}'")
            return ReadingAnalysis(
                book_title=book.title,
                difficulty="unknown",
                fits_request=True,
                fit_explanation="Unable to assess fit — insufficient data",
            )

        try:
            return ReadingAnalysis(
                book_title=data.get("book_title", book.title),
                difficulty=data.get("difficulty", "unknown"),
                reading_level=data.get("reading_level", ""),
                prerequisites=data.get("prerequisites", []),
                writing_style=data.get("writing_style", ""),
                fits_request=bool(data.get("fits_request", True)),
                fit_explanation=data.get("fit_explanation", ""),
                edition_notes=data.get("edition_notes", ""),
                estimated_reading_time=data.get("estimated_reading_time", ""),
            )
        except Exception as e:
            logger.error(f"[reading] Failed to build ReadingAnalysis: {e}")
            return ReadingAnalysis(
                book_title=book.title,
                difficulty="unknown",
                fits_request=True,
                fit_explanation="Analysis failed",
            )
