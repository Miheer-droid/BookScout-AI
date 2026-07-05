"""
BookScout AI - Pydantic Schemas
All data models used across agents and tools.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ─── User Input ───────────────────────────────────────────────

class UserQuery(BaseModel):
    """Raw user input from the frontend."""
    query: str = Field(..., description="The user's free-text book request")


# ─── Agent 1: Intent ─────────────────────────────────────────

class UserIntent(BaseModel):
    """Structured understanding of what the user wants."""
    goal: str = Field(default="", description="What the user wants to achieve")
    reading_level: str = Field(default="unknown", description="beginner / intermediate / advanced / unknown")
    interests: list[str] = Field(default_factory=list, description="Topics or genres of interest")
    previous_books: list[str] = Field(default_factory=list, description="Books the user has read")
    likes: list[str] = Field(default_factory=list, description="Things the user enjoys in books")
    dislikes: list[str] = Field(default_factory=list, description="Things the user dislikes in books")
    learning_objectives: list[str] = Field(default_factory=list, description="Specific things the user wants to learn")
    preferred_style: str = Field(default="", description="Preferred writing style or format")


# ─── Agent 2: Research Plan ──────────────────────────────────

class ResearchPlan(BaseModel):
    """Strategy for researching books."""
    book_type: str = Field(default="", description="Type of books to search for")
    target_count: int = Field(default=5, description="How many candidate books to find")
    editions_matter: bool = Field(default=False, description="Whether edition info is important")
    level_filter: str = Field(default="any", description="Difficulty filter to apply")
    search_queries: list[str] = Field(default_factory=list, description="Search queries to execute")
    focus_areas: list[str] = Field(default_factory=list, description="Key areas to focus research on")


# ─── Agent 3: Book Discovery ─────────────────────────────────

class BookCandidate(BaseModel):
    """A discovered candidate book."""
    title: str = Field(default="Unknown", description="Book title")
    author: str = Field(default="Unknown", description="Book author")
    description: str = Field(default="", description="Brief description of the book")
    cover_image: str = Field(default="", description="URL to cover image")
    publisher: str = Field(default="", description="Publisher name")
    edition: str = Field(default="", description="Edition information")
    year: str = Field(default="", description="Publication year")
    isbn: str = Field(default="", description="ISBN if found")


# ─── Parallel Agent: Review Research ─────────────────────────

class ReviewResearch(BaseModel):
    """Review research results for a single book."""
    book_title: str = Field(default="")
    common_praise: list[str] = Field(default_factory=list)
    common_complaints: list[str] = Field(default_factory=list)
    positive_sentiment: str = Field(default="")
    negative_sentiment: str = Field(default="")
    overall_opinion: str = Field(default="")
    summary: str = Field(default="")
    confidence: str = Field(default="medium", description="low / medium / high")
    sources_used: list[str] = Field(default_factory=list)


# ─── Parallel Agent: Price Research ──────────────────────────

class PriceOption(BaseModel):
    """A single price option."""
    format: str = Field(default="", description="paperback / hardcover / ebook / free")
    price: str = Field(default="")
    store: str = Field(default="")
    link: str = Field(default="")

class PriceResearch(BaseModel):
    """Price research results for a single book."""
    book_title: str = Field(default="")
    options: list[PriceOption] = Field(default_factory=list)
    cheapest_purchase: str = Field(default="")
    cheapest_reading: str = Field(default="")
    free_options: list[str] = Field(default_factory=list)
    sources_used: list[str] = Field(default_factory=list)


# ─── Parallel Agent: Reading Analysis ────────────────────────

class ReadingAnalysis(BaseModel):
    """Reading difficulty and fit analysis for a single book."""
    book_title: str = Field(default="")
    difficulty: str = Field(default="unknown", description="easy / moderate / challenging / advanced")
    reading_level: str = Field(default="")
    prerequisites: list[str] = Field(default_factory=list)
    writing_style: str = Field(default="")
    fits_request: bool = Field(default=True)
    fit_explanation: str = Field(default="")
    edition_notes: str = Field(default="")
    estimated_reading_time: str = Field(default="")


# ─── Final Agent: Recommendation ─────────────────────────────

class BookRecommendation(BaseModel):
    """Complete recommendation for a single book."""
    rank: int = Field(default=0)
    book: BookCandidate = Field(default_factory=BookCandidate)
    reviews: ReviewResearch = Field(default_factory=ReviewResearch)
    pricing: PriceResearch = Field(default_factory=PriceResearch)
    analysis: ReadingAnalysis = Field(default_factory=ReadingAnalysis)
    match_reasons: list[str] = Field(default_factory=list, description="Why this book matches the user")
    not_selected_reason: str = Field(default="", description="Why this wasn't the top pick (for non-top books)")
    score: float = Field(default=0.0, description="Overall score 0-100")


class FinalRecommendation(BaseModel):
    """Final output from the recommendation agent."""
    top_pick: Optional[BookRecommendation] = None
    alternatives: list[BookRecommendation] = Field(default_factory=list)
    overall_confidence: str = Field(default="medium")
    reasoning: str = Field(default="", description="Why the top pick was chosen")


# ─── Agent Status (for live workflow) ────────────────────────

class AgentStatus(BaseModel):
    """Status update from an agent for the live workflow display."""
    agent: str = Field(..., description="Agent name")
    status: str = Field(..., description="started / working / completed / error")
    message: str = Field(default="", description="Human-readable status message")
    emoji: str = Field(default="🔄", description="Status emoji")
    data: Optional[dict] = Field(default=None, description="Optional result data")
