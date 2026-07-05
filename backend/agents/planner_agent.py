"""
BookScout AI - Planner Agent
Creates a research plan from the user's intent.
"""

import logging
from backend.services.llm_service import LLMService
from backend.models.schemas import UserIntent, ResearchPlan
from backend.agents.base_agent import BaseAgent

logger = logging.getLogger("bookscout")

SYSTEM_PROMPT = (
    "You are a strategic book research planner. Given a reader's intent, "
    "you create an optimal research plan: what to search for, how many "
    "candidates to evaluate, and what aspects to focus on."
)


class PlannerAgent(BaseAgent):
    """Creates a research strategy from the user's intent."""

    def __init__(self, llm: LLMService) -> None:
        super().__init__(llm, "planner")

    async def plan(self, intent: UserIntent) -> ResearchPlan:
        """
        Build a research plan from structured user intent.

        Args:
            intent: The parsed UserIntent

        Returns:
            A ResearchPlan with search queries and focus areas
        """
        prompt = f"""Create a book research plan based on this reader's intent.

READER INTENT:
- Goal: {intent.goal}
- Reading Level: {intent.reading_level}
- Interests: {', '.join(intent.interests) if intent.interests else 'not specified'}
- Previous Books: {', '.join(intent.previous_books) if intent.previous_books else 'none mentioned'}
- Likes: {', '.join(intent.likes) if intent.likes else 'not specified'}
- Dislikes: {', '.join(intent.dislikes) if intent.dislikes else 'not specified'}
- Learning Objectives: {', '.join(intent.learning_objectives) if intent.learning_objectives else 'not specified'}
- Preferred Style: {intent.preferred_style or 'not specified'}

Return a JSON object with EXACTLY these keys:
{{
  "book_type": "The category/type of books to search for (e.g., 'technical programming book', 'literary fiction novel', 'self-help guide')",
  "target_count": 5,
  "editions_matter": true or false (whether specific editions are important for this type of book),
  "level_filter": "One of: beginner, intermediate, advanced, any",
  "search_queries": [
    "3 to 5 specific search query strings optimized for finding relevant books",
    "Each query should approach the topic from a different angle",
    "Include author names, series, or specific titles if the user hinted at them"
  ],
  "focus_areas": [
    "Key aspects to evaluate when comparing books",
    "e.g., 'practical exercises', 'up-to-date content', 'readability for beginners'"
  ]
}}

Rules:
- Generate 3 to 5 diverse search queries that will find different but relevant books.
- search_queries should be real web-search-style queries, not descriptions.
- target_count should be between 3 and 5.
- focus_areas should reflect what matters most given the reader's intent.
- If level_filter is unknown, set it to "any"."""

        data = await self._ask_json(prompt, SYSTEM_PROMPT)

        if not data:
            logger.warning("[planner] LLM returned no data, using fallback plan")
            return ResearchPlan(
                book_type="book",
                target_count=5,
                search_queries=[f"best books about {intent.goal}"],
                focus_areas=["relevance", "quality"],
            )

        try:
            # Clamp target_count to 3-5
            target = data.get("target_count", 5)
            target = max(3, min(5, int(target)))

            return ResearchPlan(
                book_type=data.get("book_type", "book"),
                target_count=target,
                editions_matter=bool(data.get("editions_matter", False)),
                level_filter=data.get("level_filter", "any"),
                search_queries=data.get("search_queries", [f"best books about {intent.goal}"]),
                focus_areas=data.get("focus_areas", ["relevance", "quality"]),
            )
        except Exception as e:
            logger.error(f"[planner] Failed to build ResearchPlan: {e}")
            return ResearchPlan(
                book_type="book",
                target_count=5,
                search_queries=[f"best books about {intent.goal}"],
                focus_areas=["relevance", "quality"],
            )
