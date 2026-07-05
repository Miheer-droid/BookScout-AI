"""
BookScout AI - Price Agent
Researches pricing and availability for a single book.
"""

import logging
from backend.services.llm_service import LLMService
from backend.tools import PriceScraperTool
from backend.models.schemas import BookCandidate, PriceResearch, PriceOption
from backend.agents.base_agent import BaseAgent

logger = logging.getLogger("bookscout")

SYSTEM_PROMPT = (
    "You are a book pricing analyst. You parse raw pricing data from "
    "multiple sources and structure it into a clear pricing comparison "
    "with format, price, store, and link for each option."
)


class PriceAgent(BaseAgent):
    """Researches pricing and availability for a single book."""

    def __init__(self, llm: LLMService, price_tool: PriceScraperTool) -> None:
        super().__init__(llm, "price")
        self.price_tool = price_tool

    async def research(self, book: BookCandidate) -> PriceResearch:
        """
        Research pricing for a specific book.

        Args:
            book: The book to price-check

        Returns:
            PriceResearch with structured pricing options
        """
        # Step 1: Gather raw pricing data
        try:
            raw_data = await self.price_tool.research_prices(
                title=book.title,
                author=book.author,
            )
        except Exception as e:
            logger.error(f"[price] Tool failed for '{book.title}': {e}")
            raw_data = {}

        # Step 2: Use LLM to structure pricing data
        raw_summary = str(raw_data) if raw_data else "No pricing data was found."

        prompt = f"""Analyze the following raw pricing data for a book and produce structured pricing information.

BOOK: "{book.title}" by {book.author}
ISBN: {book.isbn or 'unknown'}

RAW PRICING DATA:
{raw_summary[:4000]}

Return a JSON object with EXACTLY these keys:
{{
  "book_title": "{book.title}",
  "options": [
    {{
      "format": "paperback or hardcover or ebook or audiobook or free",
      "price": "$XX.XX or Free",
      "store": "Store name",
      "link": "URL if available, else empty string"
    }}
  ],
  "cheapest_purchase": "The cheapest way to buy/own this book (format + price + store)",
  "cheapest_reading": "The cheapest way to read this book (may include library, free options)",
  "free_options": ["Any free ways to access this book, e.g., 'Available on Project Gutenberg', 'Free with Kindle Unlimited trial'"],
  "sources_used": ["List of source names or URLs"]
}}

Rules:
- Include all formats found: paperback, hardcover, ebook, audiobook.
- If no pricing data was found, return an empty options list and note it.
- Prices should include currency symbol.
- Sort options from cheapest to most expensive within each format."""

        data = await self._ask_json(prompt, SYSTEM_PROMPT)

        if not data:
            logger.warning(f"[price] LLM returned no analysis for '{book.title}'")
            return PriceResearch(
                book_title=book.title,
                cheapest_purchase="Price data unavailable",
            )

        try:
            options: list[PriceOption] = []
            for opt in data.get("options", []):
                try:
                    options.append(PriceOption(
                        format=opt.get("format", ""),
                        price=opt.get("price", ""),
                        store=opt.get("store", ""),
                        link=opt.get("link", ""),
                    ))
                except Exception:
                    continue

            return PriceResearch(
                book_title=data.get("book_title", book.title),
                options=options,
                cheapest_purchase=data.get("cheapest_purchase", ""),
                cheapest_reading=data.get("cheapest_reading", ""),
                free_options=data.get("free_options", []),
                sources_used=data.get("sources_used", []),
            )
        except Exception as e:
            logger.error(f"[price] Failed to build PriceResearch: {e}")
            return PriceResearch(
                book_title=book.title,
                cheapest_purchase="Analysis failed",
            )
