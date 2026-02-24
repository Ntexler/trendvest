"""
API endpoint integration tests with mocked database and stock service.
"""
import pytest
from tests.conftest import FakePool, FakeConnection, FakeStockService, make_stock_price


# ── Root & Health ──

class TestRootEndpoint:
    @pytest.mark.asyncio
    async def test_root_returns_api_info(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "TrendVest AI API"
        assert data["version"] == "1.0.0"
        assert "docs" in data


# ── Trends ──

class TestTrendsEndpoints:
    @pytest.mark.asyncio
    async def test_get_trends_empty(self, client):
        resp = await client.get("/api/trends")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_get_trends_with_data(self, app_with_mocks):
        """Test trends endpoint with seeded topic data."""
        from app import deps
        from httpx import ASGITransport, AsyncClient

        topic_rows = [
            {
                "slug": "ai-chips",
                "name_en": "AI Chips",
                "name_he": "שבבי AI",
                "sector": "טכנולוגיה",
                "sector_en": "Technology",
                "momentum_score": 185.0,
                "direction": "rising",
                "mention_count_today": 42,
                "mention_avg_7d": 23.0,
            }
        ]
        stock_rows = [
            {"ticker": "NVDA", "company_name": "NVIDIA Corp", "relevance_note": "GPU leader"},
        ]

        call_count = {"fetch": 0}
        original_fetch = FakeConnection.fetch

        class TopicConnection(FakeConnection):
            async def fetch(self, query, *args):
                call_count["fetch"] += 1
                if call_count["fetch"] == 1:
                    return topic_rows
                return stock_rows

        pool = FakePool(TopicConnection())

        async def override_pool():
            return pool

        app_with_mocks.dependency_overrides[deps.get_db_pool] = override_pool

        transport = ASGITransport(app=app_with_mocks)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/trends")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["slug"] == "ai-chips"
        assert data[0]["momentum_score"] == 185.0
        assert len(data[0]["stocks"]) == 1
        assert data[0]["stocks"][0]["ticker"] == "NVDA"

    @pytest.mark.asyncio
    async def test_get_trend_not_found(self, client):
        resp = await client.get("/api/trends/nonexistent-topic")
        assert resp.status_code == 404


# ── Stocks ──

class TestStocksEndpoints:
    @pytest.mark.asyncio
    async def test_screener_empty(self, client):
        resp = await client.get("/api/stocks")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_stock_not_found(self, client):
        resp = await client.get("/api/stocks/ZZZZ")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_screener_with_data(self, app_with_mocks):
        """Test screener with seeded stock data."""
        from app import deps
        from httpx import ASGITransport, AsyncClient

        stock_rows = [
            {
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "relevance_note": "iPhone maker",
                "sector": "טכנולוגיה",
                "sector_en": "Technology",
                "topic": "סמארטפונים",
                "topic_slug": "smartphones",
            },
            {
                "ticker": "NVDA",
                "company_name": "NVIDIA Corp",
                "relevance_note": "GPU leader",
                "sector": "טכנולוגיה",
                "sector_en": "Technology",
                "topic": "שבבי AI",
                "topic_slug": "ai-chips",
            },
        ]

        class StockConnection(FakeConnection):
            async def fetch(self, query, *args):
                return stock_rows

        pool = FakePool(StockConnection())

        async def override_pool():
            return pool

        app_with_mocks.dependency_overrides[deps.get_db_pool] = override_pool

        transport = ASGITransport(app=app_with_mocks)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/stocks")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        tickers = [s["ticker"] for s in data]
        assert "AAPL" in tickers
        assert "NVDA" in tickers

    @pytest.mark.asyncio
    async def test_screener_search_filter(self, app_with_mocks):
        """Test screener with search query."""
        from app import deps
        from httpx import ASGITransport, AsyncClient

        stock_rows = [
            {
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "relevance_note": "",
                "sector": "טכנולוגיה",
                "sector_en": "Technology",
                "topic": "סמארטפונים",
                "topic_slug": "smartphones",
            },
            {
                "ticker": "NVDA",
                "company_name": "NVIDIA Corp",
                "relevance_note": "",
                "sector": "טכנולוגיה",
                "sector_en": "Technology",
                "topic": "שבבי AI",
                "topic_slug": "ai-chips",
            },
        ]

        class StockConnection(FakeConnection):
            async def fetch(self, query, *args):
                return stock_rows

        pool = FakePool(StockConnection())

        async def override_pool():
            return pool

        app_with_mocks.dependency_overrides[deps.get_db_pool] = override_pool

        transport = ASGITransport(app=app_with_mocks)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/stocks?search=apple")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["ticker"] == "AAPL"

    @pytest.mark.asyncio
    async def test_get_single_stock(self, app_with_mocks):
        """Test getting a single stock by ticker."""
        from app import deps
        from httpx import ASGITransport, AsyncClient

        class StockConnection(FakeConnection):
            async def fetchrow(self, query, *args):
                return {
                    "ticker": "AAPL",
                    "company_name": "Apple Inc.",
                    "relevance_note": "iPhone maker",
                    "sector": "טכנולוגיה",
                    "topic": "סמארטפונים",
                    "topic_slug": "smartphones",
                }

        pool = FakePool(StockConnection())

        async def override_pool():
            return pool

        app_with_mocks.dependency_overrides[deps.get_db_pool] = override_pool

        transport = ASGITransport(app=app_with_mocks)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/stocks/AAPL")

        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert data["company_name"] == "Apple Inc."
        assert data["current_price"] == 150.0


# ── Chat ──

class TestChatEndpoints:
    @pytest.mark.asyncio
    async def test_chat_remaining(self, client):
        resp = await client.get("/api/chat/remaining")
        assert resp.status_code == 200
        data = resp.json()
        assert "remaining" in data
        assert "daily_limit" in data
        assert data["daily_limit"] == 3

    @pytest.mark.asyncio
    async def test_chat_ask_no_api_key(self, client):
        resp = await client.post("/api/chat", json={
            "question": "What is a stock?",
            "language": "en",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "suggested_questions" in data
        assert isinstance(data["suggested_questions"], list)

    @pytest.mark.asyncio
    async def test_chat_invalid_question(self, client):
        resp = await client.post("/api/chat", json={"question": "x"})
        assert resp.status_code == 422  # validation error

    @pytest.mark.asyncio
    async def test_explain_term_no_api_key(self, client):
        resp = await client.post("/api/chat/explain-term", json={
            "term": "Market Cap",
            "language": "en",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["term"] == "Market Cap"


# ── Stock Insight ──

class TestStockInsight:
    @pytest.mark.asyncio
    async def test_stock_insight_fallback(self, client):
        resp = await client.get("/api/trends/ai-chips/stock-insight/NVDA?language=en")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "NVDA"
        assert data["slug"] == "ai-chips"


# ── Related Stocks ──

class TestRelatedStocks:
    @pytest.mark.asyncio
    async def test_related_stocks_empty(self, client):
        resp = await client.get("/api/stocks/AAPL/related")
        assert resp.status_code == 200
        assert resp.json() == []
