"""
Pydantic models for TrendVest API request/response schemas.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


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
    direction: str = "stable"
    mention_count_today: int = 0
    mention_avg_7d: float = 0
    stocks: list[TopicStock] = []


class TrendTopicBrief(BaseModel):
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
    context: str | None = None
    language: str = "he"


class ChatResponse(BaseModel):
    answer: str
    suggested_questions: list[str] = []
    questions_remaining: int = 0


# ── Screener Models ──

class ScreenerParams(BaseModel):
    sector: str | None = None
    max_price: float | None = None
    min_change: float | None = None
    sort_by: str = "change"
    search: str | None = None
    limit: int = Field(default=50, le=100)
    offset: int = 0


# ── Auth Models ──

class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=100)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserProfile(BaseModel):
    id: str
    email: str
    display_name: str
    tier: str
    created_at: datetime


# ── Paper Trading Models ──

class TradeRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    ticker: str = Field(..., min_length=1, max_length=10)
    action: str = Field(..., pattern="^(buy|sell)$")
    quantity: int = Field(..., gt=0)


class HoldingResponse(BaseModel):
    ticker: str
    quantity: int
    avg_cost: float
    current_price: float | None = None
    market_value: float | None = None
    pnl: float | None = None
    pnl_pct: float | None = None


class PortfolioResponse(BaseModel):
    session_id: str
    cash_balance: float
    total_value: float
    total_pnl: float
    holdings: list[HoldingResponse] = []


class TradeHistoryItem(BaseModel):
    ticker: str
    action: str
    quantity: int
    price: float
    total: float
    executed_at: datetime


# ── Stock Profile Models ──

class CompanyOfficer(BaseModel):
    name: str
    title: str
    age: int | None = None
    total_pay: float | None = None
    bio: str = ""


class StockProfileResponse(BaseModel):
    ticker: str
    name: str
    summary: str = ""
    sector: str = ""
    industry: str = ""
    employees: int | None = None
    website: str = ""
    market_cap: float | None = None
    pe_ratio: float | None = None
    dividend_yield: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    country: str = ""
    city: str = ""
    # New fields
    exchange: str = ""
    quote_type: str = ""
    officers: list[CompanyOfficer] = []
    profit_margins: float | None = None
    operating_margins: float | None = None
    return_on_equity: float | None = None
    free_cashflow: float | None = None
    total_debt: float | None = None
    total_cash: float | None = None
    beta: float | None = None
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    recommendation_key: str | None = None
    target_mean_price: float | None = None
    number_of_analysts: int | None = None


# ── Explain Models ──

class ExplainTermRequest(BaseModel):
    term: str = Field(..., min_length=1, max_length=200)
    language: str = "he"


class ExplainTermResponse(BaseModel):
    term: str
    explanation: str


class ExplainSectionRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)
    section: str = Field(..., min_length=1, max_length=50)
    data: dict
    language: str = "he"


class ExplainSectionResponse(BaseModel):
    ticker: str
    section: str
    explanation: str


# ── Peer Comparison Models ──

class PeerStock(BaseModel):
    ticker: str
    company_name: str
    current_price: float | None = None
    daily_change_pct: float | None = None
    market_cap: float | None = None
    pe_ratio: float | None = None
    beta: float | None = None
    dividend_yield: float | None = None
    profit_margins: float | None = None
    revenue_growth: float | None = None
    institutional_pct: float | None = None
    short_ratio: float | None = None


# ── Research Models ──

class ResearchRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)
    language: str = "en"


class ResearchResponse(BaseModel):
    ticker: str
    analysis: str
    citations: list[dict] = []
    generated_at: datetime


# ── Tracking Models ──

class TrackRequest(BaseModel):
    interaction_type: str = Field(..., pattern="^(topic_view|stock_click|search|news_click|watchlist_add|chat_ask)$")
    target_slug: str | None = None
    metadata: dict | None = None


# ── Expense Receipt Models ──

class ReceiptScanRequest(BaseModel):
    image_data: str = Field(..., min_length=10)
    media_type: str = Field(default="image/jpeg", pattern="^image/(jpeg|png|gif|webp)$")
    source_type: str = Field(default="upload", pattern="^(screenshot|upload|manual)$")
    original_filename: str = ""

class ReceiptManualEntry(BaseModel):
    vendor_name: str = Field(..., min_length=1, max_length=255)
    amount: float = Field(..., gt=0)
    currency: str = Field(default="ILS", max_length=10)
    receipt_date: str | None = None
    receipt_number: str = ""
    description: str = ""
    category: str = "other"
    tax_deductible: bool = False
    deduction_category: str | None = None

class ReceiptResponse(BaseModel):
    id: int
    vendor_name: str
    amount: float
    currency: str
    receipt_date: str | None = None
    receipt_number: str = ""
    description: str = ""
    category: str
    tax_deductible: bool
    deduction_category: str | None = None
    confidence_score: float = 0
    source_type: str
    status: str
    created_at: datetime
    has_image: bool = False

class ReceiptExportResponse(BaseModel):
    total_receipts: int
    total_amount: float
    tax_deductible_amount: float
    by_category: dict[str, float]
    receipts: list[ReceiptResponse]

class EmailConfigRequest(BaseModel):
    email_address: str = Field(..., min_length=5, max_length=255)
    imap_server: str = Field(default="imap.gmail.com", max_length=255)
    imap_port: int = Field(default=993)
    password: str = Field(..., min_length=1)

class ScanScheduleRequest(BaseModel):
    scan_interval_hours: int = Field(default=24, ge=1, le=168)
    scan_screenshots: bool = True
    scan_emails: bool = True
    screenshot_folder: str = ""
    is_active: bool = True

class ReceiptUpdateRequest(BaseModel):
    vendor_name: str | None = None
    amount: float | None = None
    currency: str | None = None
    receipt_date: str | None = None
    receipt_number: str | None = None
    description: str | None = None
    category: str | None = None
    tax_deductible: bool | None = None
    deduction_category: str | None = None
    status: str | None = None


# ── General ──

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
    topics_count: int = 0
    last_pipeline_run: datetime | None = None
