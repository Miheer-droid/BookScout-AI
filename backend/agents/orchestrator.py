"""
BookScout AI - Agent Orchestrator
Coordinates the existing agents into the end-to-end research workflow.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from backend.agents.discovery_agent import DiscoveryAgent
from backend.agents.intent_agent import IntentAgent
from backend.agents.planner_agent import PlannerAgent
from backend.agents.price_agent import PriceAgent
from backend.agents.reading_agent import ReadingAgent
from backend.agents.recommendation_agent import RecommendationAgent
from backend.agents.review_agent import ReviewAgent
from backend.models.schemas import (
    AgentStatus,
    BookCandidate,
    FinalRecommendation,
    PriceResearch,
    ReadingAnalysis,
    ReviewResearch,
)
from backend.services.llm_service import LLMService
from backend.services.scraper_service import ScraperService
from backend.tools import (
    BookDiscoveryTool,
    PriceScraperTool,
    ReadingAnalysisTool,
    ReviewScraperTool,
)

logger = logging.getLogger("bookscout")

StatusCallback = Callable[[AgentStatus], Awaitable[None]]


class AgentOrchestrator:
    """Wires all agents and runs the BookScout research workflow."""

    def __init__(self) -> None:
        self.llm = LLMService()
        self.scraper = ScraperService()

        self.intent_agent = IntentAgent(self.llm)
        self.planner_agent = PlannerAgent(self.llm)
        self.discovery_agent = DiscoveryAgent(
            self.llm,
            BookDiscoveryTool(self.scraper),
        )
        self.review_agent = ReviewAgent(
            self.llm,
            ReviewScraperTool(self.scraper),
        )
        self.price_agent = PriceAgent(
            self.llm,
            PriceScraperTool(self.scraper),
        )
        self.reading_agent = ReadingAgent(
            self.llm,
            ReadingAnalysisTool(self.scraper),
        )
        self.recommendation_agent = RecommendationAgent(self.llm)

    async def run(
        self,
        query: str,
        status_callback: StatusCallback | None = None,
    ) -> FinalRecommendation:
        """Run the full research workflow for a user query."""
        logger.info("[pipeline] user query input=%r candidate_count=0", query)
        await self._emit(
            status_callback,
            "understanding",
            "started",
            "Understanding your request.",
            "brain",
        )
        logger.info("[intent] input=%r candidate_count=0", query)
        intent = await self.intent_agent.analyze(query)
        logger.info(
            "[intent] output=%s candidate_count=0",
            self._summarize_model(intent),
        )
        await self._emit(
            status_callback,
            "understanding",
            "completed",
            "Intent understood.",
            "check",
            data={"intent": self._safe_dump(intent)},
        )

        logger.info(
            "[planner] input=%s candidate_count=0",
            self._summarize_model(intent),
        )
        await self._emit(
            status_callback,
            "planning",
            "started",
            "Planning the research strategy.",
            "search",
        )
        plan = await self.planner_agent.plan(intent)
        logger.info(
            "[planner] output=%s candidate_count=%s",
            self._summarize_model(plan),
            plan.target_count,
        )
        await self._emit(
            status_callback,
            "planning",
            "completed",
            "Research plan ready.",
            "check",
            data={"plan": self._safe_dump(plan)},
        )

        logger.info(
            "[discovery] input=%s candidate_count=0",
            self._summarize_model(plan),
        )
        await self._emit(
            status_callback,
            "search",
            "started",
            "Finding candidate books.",
            "books",
        )
        books = await self.discovery_agent.discover(plan)
        logger.info(
            "[discovery] output=%s candidate_count=%d",
            self._summarize_books(books),
            len(books),
        )
        await self._emit(
            status_callback,
            "search",
            "completed",
            f"Found {len(books)} candidate books.",
            "check",
            data={
                "books": [
                    {"title": b.title, "author": b.author}
                    for b in books
                ]
            },
        )

        logger.info(
            "[review] input=%s candidate_count=%d",
            self._summarize_books(books),
            len(books),
        )
        logger.info(
            "[price] input=%s candidate_count=%d",
            self._summarize_books(books),
            len(books),
        )
        logger.info(
            "[reading] input=%s candidate_count=%d",
            self._summarize_books(books),
            len(books),
        )
        researched_books = await self._research_books(
            books,
            intent,
            status_callback,
        )
        logger.info(
            "[review] output=%s candidate_count=%d",
            self._summarize_researched_books(researched_books, "reviews"),
            len(researched_books),
        )
        logger.info(
            "[price] output=%s candidate_count=%d",
            self._summarize_researched_books(researched_books, "pricing"),
            len(researched_books),
        )
        logger.info(
            "[reading] output=%s candidate_count=%d",
            self._summarize_researched_books(researched_books, "analysis"),
            len(researched_books),
        )

        logger.info(
            "[recommendation] input=%s candidate_count=%d",
            self._summarize_books([entry["book"] for entry in researched_books]),
            len(researched_books),
        )
        await self._emit(
            status_callback,
            "recommendation",
            "started",
            "Ranking recommendations.",
            "trophy",
        )
        recommendation = await self.recommendation_agent.recommend(
            intent,
            researched_books,
        )
        recommendation_count = (
            (1 if recommendation.top_pick else 0)
            + len(recommendation.alternatives)
        )
        logger.info(
            "[recommendation] output=%s candidate_count=%d",
            self._summarize_model(recommendation),
            recommendation_count,
        )
        await self._emit(
            status_callback,
            "recommendation",
            "completed",
            "Recommendations ranked.",
            "check",
        )

        return recommendation

    async def _research_books(
        self,
        books: list[BookCandidate],
        intent,
        status_callback: StatusCallback | None,
    ) -> list[dict]:
        """
        Run review, price, and reading analysis for each book.

        Review/price/reading run together as ONE task per book (see
        _research_single_book), so they cannot finish independently of
        each other — reviews/pricing/analysis genuinely complete in
        lockstep per book. This reports live progress honestly: the
        same per-book status list is broadcast to all three steps as
        each book finishes, rather than faking three separate lanes.

        Timing is unchanged from before: every book still starts
        immediately and runs fully in parallel. This only changes when
        we report progress, not how fast the work actually happens.
        """
        if not books:
            logger.warning("[research] skipped because candidate_count=0")
            return []

        book_progress = [{"title": b.title, "status": "researching"} for b in books]

        await self._emit(
            status_callback,
            "reviews",
            "started",
            "Researching reviews and ratings.",
            "star",
            data={"books": [dict(e) for e in book_progress]},
        )
        await self._emit(
            status_callback,
            "pricing",
            "started",
            "Comparing prices and free options.",
            "money",
            data={"books": [dict(e) for e in book_progress]},
        )
        await self._emit(
            status_callback,
            "analysis",
            "started",
            "Analyzing reading difficulty.",
            "book",
            data={"books": [dict(e) for e in book_progress]},
        )

        task_to_book = {
            asyncio.create_task(self._research_single_book(book, intent)): book
            for book in books
        }
        pending = set(task_to_book.keys())
        results_by_id: dict[int, dict] = {}
        total = len(books)
        completed = 0

        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                book = task_to_book[task]
                try:
                    result = task.result()
                except Exception as e:
                    logger.error(
                        "Research failed for '%s': %s",
                        book.title,
                        e,
                        exc_info=e,
                    )
                    result = self._empty_research_entry(book)
                results_by_id[id(book)] = result
                completed += 1

                for entry in book_progress:
                    if entry["title"] == book.title and entry["status"] != "done":
                        entry["status"] = "done"
                        break

                progress_message = f"{completed}/{total} books researched"
                snapshot = [dict(e) for e in book_progress]
                await self._emit(
                    status_callback, "reviews", "progress",
                    progress_message, "star", data={"books": snapshot},
                )
                await self._emit(
                    status_callback, "pricing", "progress",
                    progress_message, "money", data={"books": snapshot},
                )
                await self._emit(
                    status_callback, "analysis", "progress",
                    progress_message, "book", data={"books": snapshot},
                )

        # Preserve original discovery order regardless of completion order,
        # matching the previous zip()-based behavior exactly.
        researched_books = [results_by_id[id(book)] for book in books]

        await self._emit(
            status_callback,
            "reviews",
            "completed",
            f"Reviewed {len(researched_books)} books.",
            "check",
            data={"books": [dict(e) for e in book_progress]},
        )
        await self._emit(
            status_callback,
            "pricing",
            "completed",
            f"Priced {len(researched_books)} books.",
            "check",
            data={"books": [dict(e) for e in book_progress]},
        )
        await self._emit(
            status_callback,
            "analysis",
            "completed",
            f"Analyzed {len(researched_books)} books.",
            "check",
            data={"books": [dict(e) for e in book_progress]},
        )
        return researched_books

    async def _research_single_book(self, book: BookCandidate, intent) -> dict:
        """Research one book using the three parallel research agents."""
        reviews_task = self.review_agent.research(book, intent)
        price_task = self.price_agent.research(book)
        reading_task = self.reading_agent.analyze(book, intent)

        reviews, pricing, analysis = await asyncio.gather(
            reviews_task,
            price_task,
            reading_task,
        )

        return {
            "book": book,
            "reviews": reviews,
            "pricing": pricing,
            "analysis": analysis,
        }

    @staticmethod
    def _safe_dump(model) -> dict:
        """
        Convert a pydantic model to a plain dict for the live UI.
        Defensive on purpose: this only feeds the display, so any
        failure here must never break the actual pipeline.
        """
        try:
            if hasattr(model, "model_dump"):
                return model.model_dump()
            if isinstance(model, dict):
                return model
            return {"value": str(model)}
        except Exception as e:
            logger.warning("[_safe_dump] failed to serialize %s: %s", type(model), e)
            return {}

    @staticmethod
    def _summarize_model(model) -> str:
        """Compact model output for logs."""
        if hasattr(model, "model_dump"):
            data = model.model_dump()
        else:
            data = model
        text = repr(data)
        return text[:1200]

    @staticmethod
    def _summarize_books(books: list[BookCandidate]) -> str:
        """Compact book list output for logs."""
        return repr([
            {
                "title": book.title,
                "author": book.author,
            }
            for book in books
        ])[:1200]

    @staticmethod
    def _summarize_researched_books(researched_books: list[dict], key: str) -> str:
        """Compact researched book output for logs."""
        summary = []
        for entry in researched_books:
            book = entry["book"]
            value = entry[key]
            summary.append({
                "title": book.title,
                key: value.model_dump() if hasattr(value, "model_dump") else value,
            })
        return repr(summary)[:1200]

    @staticmethod
    def _empty_research_entry(book: BookCandidate) -> dict:
        """Fallback entry used when research fails for one book."""
        return {
            "book": book,
            "reviews": ReviewResearch(book_title=book.title),
            "pricing": PriceResearch(book_title=book.title),
            "analysis": ReadingAnalysis(book_title=book.title),
        }

    @staticmethod
    async def _emit(
        status_callback: StatusCallback | None,
        agent: str,
        status: str,
        message: str,
        emoji: str,
        data: dict | None = None,
    ) -> None:
        """Send a status update if a callback was provided."""
        if status_callback is None:
            return
        await status_callback(
            AgentStatus(
                agent=agent,
                status=status,
                message=message,
                emoji=emoji,
                data=data,
            )
        )
