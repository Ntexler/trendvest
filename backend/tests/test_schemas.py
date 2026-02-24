"""
Tests for Pydantic schema validation.
"""
import pytest
from pydantic import ValidationError
from app.models.schemas import (
    ChatRequest,
    TradeRequest,
    RegisterRequest,
    TrackRequest,
    ScreenerParams,
    TopicStock,
    TrendTopic,
    PortfolioResponse,
    HealthResponse,
)
from datetime import datetime, timezone


class TestChatRequest:
    def test_valid_request(self):
        req = ChatRequest(question="What is an ETF?")
        assert req.question == "What is an ETF?"
        assert req.language == "he"  # default
        assert req.context is None

    def test_with_context(self):
        req = ChatRequest(question="Tell me more", context="ai-chips", language="en")
        assert req.context == "ai-chips"
        assert req.language == "en"

    def test_question_too_short(self):
        with pytest.raises(ValidationError):
            ChatRequest(question="x")

    def test_question_too_long(self):
        with pytest.raises(ValidationError):
            ChatRequest(question="x" * 501)


class TestTradeRequest:
    def test_valid_buy(self):
        req = TradeRequest(session_id="sess123", ticker="AAPL", action="buy", quantity=10)
        assert req.action == "buy"
        assert req.quantity == 10

    def test_valid_sell(self):
        req = TradeRequest(session_id="sess123", ticker="NVDA", action="sell", quantity=5)
        assert req.action == "sell"

    def test_invalid_action(self):
        with pytest.raises(ValidationError):
            TradeRequest(session_id="sess123", ticker="AAPL", action="hold", quantity=10)

    def test_zero_quantity(self):
        with pytest.raises(ValidationError):
            TradeRequest(session_id="sess123", ticker="AAPL", action="buy", quantity=0)

    def test_negative_quantity(self):
        with pytest.raises(ValidationError):
            TradeRequest(session_id="sess123", ticker="AAPL", action="buy", quantity=-5)

    def test_empty_session_id(self):
        with pytest.raises(ValidationError):
            TradeRequest(session_id="", ticker="AAPL", action="buy", quantity=1)


class TestRegisterRequest:
    def test_valid(self):
        req = RegisterRequest(email="user@example.com", password="secure123")
        assert req.email == "user@example.com"
        assert req.display_name == ""

    def test_with_display_name(self):
        req = RegisterRequest(email="user@example.com", password="secure123", display_name="John")
        assert req.display_name == "John"

    def test_short_password(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="user@example.com", password="short")

    def test_short_email(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b", password="secure123")


class TestTrackRequest:
    def test_valid_types(self):
        for itype in ["topic_view", "stock_click", "search", "news_click", "watchlist_add", "chat_ask"]:
            req = TrackRequest(interaction_type=itype)
            assert req.interaction_type == itype

    def test_invalid_type(self):
        with pytest.raises(ValidationError):
            TrackRequest(interaction_type="invalid_type")


class TestScreenerParams:
    def test_defaults(self):
        params = ScreenerParams()
        assert params.sort_by == "change"
        assert params.limit == 50
        assert params.offset == 0

    def test_limit_cap(self):
        with pytest.raises(ValidationError):
            ScreenerParams(limit=200)


class TestTopicStock:
    def test_minimal(self):
        stock = TopicStock(ticker="AAPL", company_name="Apple Inc.")
        assert stock.current_price is None
        assert stock.relevance_note == ""

    def test_full(self):
        stock = TopicStock(
            ticker="AAPL",
            company_name="Apple Inc.",
            relevance_note="AI hardware",
            current_price=150.0,
            daily_change_pct=1.5,
            previous_close=147.5,
        )
        assert stock.current_price == 150.0


class TestTrendTopic:
    def test_defaults(self):
        topic = TrendTopic(slug="ai-chips", name_en="AI Chips", name_he="שבבי AI", sector="טכנולוגיה")
        assert topic.momentum_score == 0
        assert topic.direction == "stable"
        assert topic.stocks == []


class TestHealthResponse:
    def test_valid(self):
        resp = HealthResponse(
            status="ok",
            version="1.0.0",
            timestamp=datetime.now(timezone.utc),
            topics_count=33,
        )
        assert resp.status == "ok"
        assert resp.last_pipeline_run is None
