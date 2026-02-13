"""
Pydantic models for TrendVest API request/response schemas.
"""
from pydantic import BaseModel, Field
from datetime import datetime


# ── Stock Models ──

class TopicStock(BaseModel):
    ticker: str
    company_name: str
    relevance_note: str = ""
    current_price: float | None = None
    daily_change_pct: float | None = None
    previous_close: float | None = None


class StockDetail(BaseModel):
    ticker: str
    company_name: str
    sector: str
    topic: str
    topic_slug: str
    relevance_note: str = ""
    current_price: float | None = None
    daily_change_pct: float | None = None
    previous_close: float | None = None


# ── Trend Models ──

class TrendTopic(BaseModel):
    slug: str
    name_en: str
    name_he: str
    sector: str
    sector_en: str = ""
    momentum_score: float = 0
    direction: str = "stable"  # rising | stable | falling
    mention_count_today: int = 0
    mention_avg_7d: float = 0
    stocks: list[TopicStock] = []


class TrendTopicBrief(BaseModel):
    """Lightweight version for list views."""
    slug: str
    name_he: str
    sector: str
    momentum_score: float = 0
    direction: str = "stable"
    mention_count_today: int = 0
    top_ticker: str | None = None
    top_ticker_change: float | None = None


# ── Chat Models ──

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)
    context: str | None = None  # optional topic slug for context


class ChatResponse(BaseModel):
    answer: str
    suggested_questions: list[str] = []
    questions_remaining: int = 0


# ── Screener Models ──

class ScreenerParams(BaseModel):
    sector: str | None = None
    max_price: float | None = None
    min_change: float | None = None
    sort_by: str = "change"  # change | price | name
    search: str | None = None
    limit: int = Field(default=50, le=100)
    offset: int = 0


# ── General ──

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
    topics_count: int = 0
    last_pipeline_run: datetime | None = None
