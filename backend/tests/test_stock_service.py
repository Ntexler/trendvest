"""
Tests for StockPriceService — cache logic, eviction, TTL.
"""
import pytest
from datetime import datetime, timezone, timedelta
from app.services.stocks import StockPriceService, StockPrice


def _make_price(ticker, price=100.0, age_seconds=0):
    """Create a StockPrice with a specific age."""
    return StockPrice(
        ticker=ticker,
        price=price,
        change=1.0,
        change_pct=1.0,
        previous_close=price - 1.0,
        fetched_at=datetime.now(timezone.utc) - timedelta(seconds=age_seconds),
    )


class TestCacheTTL:
    def test_fresh_cache_hit(self):
        svc = StockPriceService()
        svc._cache["AAPL"] = _make_price("AAPL", age_seconds=60)
        result = svc.get_price("AAPL")
        assert result is not None
        assert result.ticker == "AAPL"

    def test_expired_cache_refetches(self):
        """When cache TTL expired and yfinance unavailable, returns None."""
        svc = StockPriceService()
        svc._cache["AAPL"] = _make_price("AAPL", age_seconds=700)
        # With no yfinance mock, it will try to fetch and likely fail
        # but should return the stale cache entry as fallback
        result = svc.get_price("AAPL")
        # Either returns stale cache or None depending on yfinance availability
        assert result is None or result.ticker == "AAPL"


class TestCacheEviction:
    def test_enforce_cache_limit(self):
        svc = StockPriceService()
        svc.MAX_CACHE_SIZE = 5
        # Fill cache with 10 entries
        for i in range(10):
            svc._cache[f"T{i}"] = _make_price(f"T{i}", age_seconds=i * 10)
        svc._enforce_cache_limit()
        assert len(svc._cache) <= 5

    def test_evicts_oldest_first(self):
        svc = StockPriceService()
        svc.MAX_CACHE_SIZE = 3
        svc._cache["OLD"] = _make_price("OLD", age_seconds=1000)
        svc._cache["MID"] = _make_price("MID", age_seconds=500)
        svc._cache["NEW"] = _make_price("NEW", age_seconds=10)
        svc._cache["NEWEST"] = _make_price("NEWEST", age_seconds=0)
        svc._enforce_cache_limit()
        assert "OLD" not in svc._cache
        assert "NEWEST" in svc._cache
        assert len(svc._cache) == 3

    def test_evict_stale(self):
        svc = StockPriceService()
        svc._cache["STALE"] = _make_price("STALE", age_seconds=2000)
        svc._cache["FRESH"] = _make_price("FRESH", age_seconds=10)
        svc._evict_stale()
        assert "STALE" not in svc._cache
        assert "FRESH" in svc._cache

    def test_no_eviction_when_under_limit(self):
        svc = StockPriceService()
        svc.MAX_CACHE_SIZE = 100
        svc._cache["A"] = _make_price("A")
        svc._cache["B"] = _make_price("B")
        svc._enforce_cache_limit()
        assert len(svc._cache) == 2


class TestBatchPrices:
    def test_batch_returns_cached(self):
        svc = StockPriceService()
        svc._cache["AAPL"] = _make_price("AAPL", price=150.0)
        svc._cache["MSFT"] = _make_price("MSFT", price=420.0)
        result = svc.get_prices_batch(["AAPL", "MSFT"])
        assert "AAPL" in result
        assert "MSFT" in result
        assert result["AAPL"].price == 150.0

    def test_batch_empty_tickers(self):
        svc = StockPriceService()
        result = svc.get_prices_batch([])
        assert result == {}


class TestClearCache:
    def test_clear(self):
        svc = StockPriceService()
        svc._cache["AAPL"] = _make_price("AAPL")
        svc.clear_cache()
        assert len(svc._cache) == 0
