"""
BookScout AI - Recommendation Agent
Combines all research data to produce a final, ranked recommendation.
"""

import logging
from backend.services.llm_service import LLMService
from backend.models.schemas import (
    UserIntent,
    BookCandidate,
    ReviewResearch,
    PriceResearch,
    ReadingAnalysis,
    BookRecommendation,
    FinalRecommendation,
)
from backend.agents.base_agent import BaseAgent

logger = logging.getLogger("bookscout")

SYSTEM_PROMPT = (
    "You are a book recommendation expert. Given comprehensive research "
    "data on multiple books — reviews, pricing, difficulty, and reader "
    "fit — you rank them and explain your reasoning. Be decisive: pick "
    "a clear winner and justify why."
)


class RecommendationAgent(BaseAgent):
    """Combines all data to produce a ranked final recommendation."""

    def __init__(self, llm: LLMService) -> None:
        super().__init__(llm, "recommendation")

    async def recommend(
        self, intent: UserIntent, books: list[dict]
    ) -> FinalRecommendation:
        """
        Rank books and produce a final recommendation.

        Args:
            intent: The user's original intent
            books: List of dicts, each with keys:
                   'book' (BookCandidate), 'reviews' (ReviewResearch),
                   'pricing' (PriceResearch), 'analysis' (ReadingAnalysis)

        Returns:
            FinalRecommendation with top_pick and alternatives
        """
        if not books:
            return FinalRecommendation(
                overall_confidence="low",
                reasoning="No books were available to evaluate.",
            )

        # Build a detailed summary of each book for the LLM
        books_summary = ""
        for i, entry in enumerate(books):
            book: BookCandidate = entry["book"]
            reviews: ReviewResearch = entry["reviews"]
            pricing: PriceResearch = entry["pricing"]
            analysis: ReadingAnalysis = entry["analysis"]

            books_summary += f"""
--- BOOK {i + 1}: "{book.title}" by {book.author} ---
Description: {book.description}
Year: {book.year or 'unknown'} | Edition: {book.edition or 'unknown'}

REVIEWS:
  Overall: {reviews.overall_opinion}
  Praise: {', '.join(reviews.common_praise) if reviews.common_praise else 'N/A'}
  Complaints: {', '.join(reviews.common_complaints) if reviews.common_complaints else 'N/A'}
  Confidence: {reviews.confidence}

PRICING:
  Cheapest purchase: {pricing.cheapest_purchase or 'unknown'}
  Cheapest reading: {pricing.cheapest_reading or 'unknown'}
  Free options: {', '.join(pricing.free_options) if pricing.free_options else 'none'}

READING ANALYSIS:
  Difficulty: {analysis.difficulty}
  Best for: {analysis.reading_level}
  Prerequisites: {', '.join(analysis.prerequisites) if analysis.prerequisites else 'none'}
  Writing style: {analysis.writing_style}
  Fits this reader: {analysis.fits_request} — {analysis.fit_explanation}
  Estimated reading time: {analysis.estimated_reading_time or 'unknown'}
"""

        prompt = f"""You have comprehensive research on {len(books)} candidate books for a reader.

READER INTENT:
- Goal: {intent.goal}
- Reading Level: {intent.reading_level}
- Interests: {', '.join(intent.interests) if intent.interests else 'not specified'}
- Likes: {', '.join(intent.likes) if intent.likes else 'not specified'}
- Dislikes: {', '.join(intent.dislikes) if intent.dislikes else 'not specified'}
- Learning Objectives: {', '.join(intent.learning_objectives) if intent.learning_objectives else 'not specified'}

BOOK DATA:
{books_summary}

Rank these books from best to worst fit for this specific reader. Return a JSON object:
{{
  "rankings": [
    {{
      "rank": 1,
      "title": "Book Title",
      "author": "Author",
      "score": 85,
      "match_reasons": [
        "2-4 specific reasons why this book matches the reader",
        "Reference the reader's stated goal, level, and preferences"
      ],
      "not_selected_reason": ""
    }},
    {{
      "rank": 2,
      "title": "Book Title",
      "author": "Author",
      "score": 72,
      "match_reasons": ["Why this book is also good"],
      "not_selected_reason": "Why this wasn't picked as #1 (be specific)"
    }}
  ],
  "overall_confidence": "low, medium, or high",
  "reasoning": "A 3-5 sentence explanation of why the #1 pick is the best choice for this reader. Be specific, reference data from reviews, difficulty, and pricing."
}}

Rules:
- Scores are 0-100. A perfect match for the reader's exact needs is 90-100.
- The #1 ranked book has an empty not_selected_reason.
- Every non-#1 book MUST have a not_selected_reason explaining why it lost.
- match_reasons should be specific to this reader, not generic praise.
- overall_confidence reflects your confidence in the recommendation:
  - "high" = strong data, clear winner
  - "medium" = decent data, reasonable choice
  - "low" = sparse data or very close call
- Be honest. If a book has clear problems, score it lower."""

        data = await self._ask_json(prompt, SYSTEM_PROMPT)

        if not data or "rankings" not in data:
            logger.warning("[recommendation] LLM returned no rankings")
            return self._fallback_recommendation(books)

        try:
            return self._build_recommendation(data, books)
        except Exception as e:
            logger.error(f"[recommendation] Failed to build recommendation: {e}")
            return self._fallback_recommendation(books)

    def _build_recommendation(
        self, data: dict, books: list[dict]
    ) -> FinalRecommendation:
        """Build a FinalRecommendation from LLM ranking data."""
        rankings = data.get("rankings", [])

        # Create a lookup from title → book entry
        book_lookup: dict[str, dict] = {}
        for entry in books:
            book: BookCandidate = entry["book"]
            book_lookup[book.title.lower()] = entry

        recommendations: list[BookRecommendation] = []
        for r in rankings:
            title = r.get("title", "")
            entry = book_lookup.get(title.lower())

            if entry is None:
                # Try fuzzy match: find a book whose title contains the ranked title
                for key, val in book_lookup.items():
                    if title.lower() in key or key in title.lower():
                        entry = val
                        break

            if entry is None:
                continue

            recommendations.append(BookRecommendation(
                rank=int(r.get("rank", 0)),
                book=entry["book"],
                reviews=entry["reviews"],
                pricing=entry["pricing"],
                analysis=entry["analysis"],
                match_reasons=r.get("match_reasons", []),
                not_selected_reason=r.get("not_selected_reason", ""),
                score=float(r.get("score", 0)),
            ))

        # Sort by rank
        recommendations.sort(key=lambda x: x.rank)

        top_pick = recommendations[0] if recommendations else None
        alternatives = recommendations[1:] if len(recommendations) > 1 else []

        return FinalRecommendation(
            top_pick=top_pick,
            alternatives=alternatives,
            overall_confidence=data.get("overall_confidence", "medium"),
            reasoning=data.get("reasoning", ""),
        )

    def _fallback_recommendation(self, books: list[dict]) -> FinalRecommendation:
        """Create a minimal recommendation when LLM fails."""
        if not books:
            return FinalRecommendation(
                overall_confidence="low",
                reasoning="Unable to generate recommendation — no data available.",
            )

        recommendations: list[BookRecommendation] = []
        for i, entry in enumerate(books):
            recommendations.append(BookRecommendation(
                rank=i + 1,
                book=entry["book"],
                reviews=entry["reviews"],
                pricing=entry["pricing"],
                analysis=entry["analysis"],
                match_reasons=["Matched search criteria"],
                not_selected_reason="" if i == 0 else "Lower ranked by default ordering",
                score=max(50 - (i * 10), 10),
            ))

        return FinalRecommendation(
            top_pick=recommendations[0],
            alternatives=recommendations[1:],
            overall_confidence="low",
            reasoning="Recommendation based on default ordering — LLM ranking was unavailable.",
        )
