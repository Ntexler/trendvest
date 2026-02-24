"""
Shared fixtures for TrendVest test suite.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from httpx import ASGITransport, AsyncClient

from app.services.stocks import StockPrice, StockPriceService
from app import deps


class FakeConnection:
    """Lightweight mock for asyncpg connection."""

    def __init__(self, data=None):
        self._data = data or {}

    async def fetch(self, query, *args):
        return self._data.get("fetch", [])

    async def fetchrow(self, query, *args):
        rows = self._data.get("fetchrow", None)
        return rows

    async def fetchval(self, query, *args):
        return self._data.get("fetchval", 0)

    async def execute(self, query, *args):
        return None


class FakePool:
    """Lightweight mock for asyncpg pool that works as async context manager."""

    def __init__(self, conn=None):
        self._conn = conn or FakeConnection()

    def acquire(self):
        return self

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *args):
        pass


def make_stock_price(ticker="AAPL", price=150.0, change=2.5, change_pct=1.69, previous_close=147.5):
    return StockPrice(
        ticker=ticker,
        price=price,
        change=change,
        change_pct=change_pct,
        previous_close=previous_close,
        fetched_at=datetime.now(timezone.utc),
    )


class FakeStockService:
    """Fake stock service that returns predetermined prices."""

    def __init__(self, prices=None):
        self._prices = prices or {}

    def get_price(self, ticker):
        return self._prices.get(ticker)

    def get_prices_batch(self, tickers):
        return {t: self._prices[t] for t in tickers if t in self._prices}


@pytest.fixture
def fake_pool():
    return FakePool()


@pytest.fixture
def fake_stock_service():
    return FakeStockService({
        "AAPL": make_stock_price("AAPL", 150.0, 2.5, 1.69, 147.5),
        "NVDA": make_stock_price("NVDA", 800.0, 15.0, 1.91, 785.0),
        "MSFT": make_stock_price("MSFT", 420.0, -3.0, -0.71, 423.0),
    })


@pytest.fixture
def app_with_mocks(fake_pool, fake_stock_service):
    """Create a FastAPI app with mocked dependencies for testing endpoints."""
    deps.set_db_pool(None)
    deps.set_stock_service(None)

    from app.main import app

    async def override_pool():
        return fake_pool

    async def override_stock_service():
        return fake_stock_service

    app.dependency_overrides[deps.get_db_pool] = override_pool
    app.dependency_overrides[deps.get_stock_service] = override_stock_service

    yield app

    app.dependency_overrides.clear()


@pytest.fixture
async def client(app_with_mocks):
    transport = ASGITransport(app=app_with_mocks)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
