"""
BookScout AI - Intent Agent
Understands the user's query and extracts structured intent.
"""

import logging
from backend.services.llm_service import LLMService
from backend.models.schemas import UserIntent
from backend.agents.base_agent import BaseAgent

logger = logging.getLogger("bookscout")

SYSTEM_PROMPT = (
    "You are an expert librarian AI. Your job is to deeply understand "
    "what a reader is looking for based on their natural-language request. "
    "Extract structured intent from the query."
)


class IntentAgent(BaseAgent):
    """Analyzes a user's free-text query to extract structured intent."""

    def __init__(self, llm: LLMService) -> None:
        super().__init__(llm, "intent")

    async def analyze(self, query: str) -> UserIntent:
        """
        Parse a user's natural-language book request into structured intent.

        Args:
            query: The user's raw text query

        Returns:
            A UserIntent object with all extracted fields
        """
        prompt = f"""Analyze the following book request from a user. Extract their intent into a structured JSON object.

USER QUERY: "{query}"

Return a JSON object with EXACTLY these keys:
{{
  "goal": "What the user ultimately wants to achieve (e.g., 'learn Python', 'find a thriller novel')",
  "reading_level": "One of: beginner, intermediate, advanced, unknown",
  "interests": ["list", "of", "topics", "or", "genres", "they", "care", "about"],
  "previous_books": ["any", "books", "they", "mentioned", "having", "read"],
  "likes": ["things", "they", "enjoy", "in", "books"],
  "dislikes": ["things", "they", "dislike", "or", "want", "to", "avoid"],
  "learning_objectives": ["specific", "skills", "or", "knowledge", "they", "want"],
  "preferred_style": "Their preferred writing style (e.g., 'practical with examples', 'academic', 'conversational', or empty string if not stated)"
}}

Rules:
- If information is not mentioned in the query, use empty strings or empty lists.
- For reading_level, infer from context clues (e.g., "I'm new to..." → beginner).
- Be thorough but do not invent information not implied by the query.
- interests and learning_objectives may overlap — that's fine.
- The query may contain a tag like "[Reading level: beginner]", "[Reading level: intermediate]", or "[Reading level: advanced]". This is a hint the app appended, not the user's own wording. If present, set reading_level to EXACTLY that value — do not guess or override it, even if the rest of the query suggests otherwise.
- The query may also contain a tag like "[Goal: Learn from scratch]", "[Goal: Go deeper]", "[Goal: Just for fun]", or "[Goal: Reference material]". Use its meaning to shape the 'goal' and 'learning_objectives' fields naturally — do not quote the tag text literally, and never treat either tag as a book title, interest, or genre."""

        data = await self._ask_json(prompt, SYSTEM_PROMPT)

        if not data:
            logger.warning("[intent] LLM returned no data, using defaults")
            return UserIntent(goal=query)

        try:
            return UserIntent(
                goal=data.get("goal", query),
                reading_level=data.get("reading_level", "unknown"),
                interests=data.get("interests", []),
                previous_books=data.get("previous_books", []),
                likes=data.get("likes", []),
                dislikes=data.get("dislikes", []),
                learning_objectives=data.get("learning_objectives", []),
                preferred_style=data.get("preferred_style", ""),
            )
        except Exception as e:
            logger.error(f"[intent] Failed to build UserIntent: {e}")
            return UserIntent(goal=query)
