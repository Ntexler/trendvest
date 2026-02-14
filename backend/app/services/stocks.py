"""
Stock price service for TrendVest.
Uses yfinance for free stock data with in-memory caching.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    import yfinance as yf
except ImportError:
    yf = None
    logger.warning("yfinance not installed. Run: pip install yfinance")


@dataclass
class StockPrice:
    ticker: str
    price: float
    change: float
    change_pct: float
    previous_close: float
    fetched_at: datetime


class StockPriceService:
    """Fetches and caches stock prices."""

    CACHE_TTL = 300  # 5 minutes
    MAX_CACHE_SIZE = 200
    STALE_TTL = 900  # 15 min — evict entries older than 3x TTL
    BATCH_CHUNK_SIZE = 30

    def __init__(self):
        self._cache: dict[str, StockPrice] = {}

    def _evict_stale(self):
        """Remove cache entries older than STALE_TTL."""
        now = datetime.now(timezone.utc)
        stale_keys = [
            k for k, v in self._cache.items()
            if (now - v.fetched_at).total_seconds() > self.STALE_TTL
        ]
        for k in stale_keys:
            del self._cache[k]

    def _enforce_cache_limit(self):
        """Evict oldest entries if cache exceeds MAX_CACHE_SIZE."""
        if len(self._cache) <= self.MAX_CACHE_SIZE:
            return
        sorted_entries = sorted(self._cache.items(), key=lambda x: x[1].fetched_at)
        to_remove = len(self._cache) - self.MAX_CACHE_SIZE
        for k, _ in sorted_entries[:to_remove]:
            del self._cache[k]

    def get_price(self, ticker: str) -> Optional[StockPrice]:
        """Get current stock price with caching."""
        # Check cache
        if ticker in self._cache:
            cached = self._cache[ticker]
            age = (datetime.now(timezone.utc) - cached.fetched_at).total_seconds()
            if age < self.CACHE_TTL:
                return cached

        if not yf:
            return None

        try:
            stock = yf.Ticker(ticker)
            info = stock.fast_info

            price = info.get("lastPrice", 0) or info.get("last_price", 0)
            prev_close = info.get("previousClose", 0) or info.get("previous_close", 0)

            if price and prev_close:
                change = price - prev_close
                change_pct = (change / prev_close) * 100
            else:
                change = 0
                change_pct = 0

            result = StockPrice(
                ticker=ticker,
                price=round(price, 2),
                change=round(change, 2),
                change_pct=round(change_pct, 2),
                previous_close=round(prev_close, 2),
                fetched_at=datetime.now(timezone.utc),
            )

            self._cache[ticker] = result
            self._enforce_cache_limit()
            return result

        except Exception as e:
            logger.warning("yfinance error for %s: %s", ticker, e)
            if ticker in self._cache:
                return self._cache[ticker]
            return None

    def get_prices_batch(self, tickers: list[str]) -> dict[str, Optional[StockPrice]]:
        """
        Get prices for multiple tickers.
        Uses yfinance batch download for efficiency.
        """
        results = {}

        # Check cache first
        uncached = []
        for ticker in tickers:
            if ticker in self._cache:
                cached = self._cache[ticker]
                age = (datetime.now(timezone.utc) - cached.fetched_at).total_seconds()
                if age < self.CACHE_TTL:
                    results[ticker] = cached
                    continue
            uncached.append(ticker)

        if not uncached or not yf:
            return results

        # Batch download in chunks to limit peak RAM usage
        for i in range(0, len(uncached), self.BATCH_CHUNK_SIZE):
            chunk = uncached[i : i + self.BATCH_CHUNK_SIZE]
            try:
                tickers_str = " ".join(chunk)
                data = yf.download(tickers_str, period="2d", progress=False, threads=True)

                if data.empty:
                    logger.warning("Batch download returned empty data for chunk %d", i)
                    continue

                for ticker in chunk:
                    try:
                        # yfinance 1.1.0+ always uses MultiIndex columns
                        close_data = data["Close"][ticker]

                        if len(close_data.dropna()) >= 2:
                            price = float(close_data.dropna().iloc[-1])
                            prev_close = float(close_data.dropna().iloc[-2])
                            change = price - prev_close
                            change_pct = (change / prev_close) * 100 if prev_close else 0
                        elif len(close_data.dropna()) == 1:
                            price = float(close_data.dropna().iloc[-1])
                            prev_close = price
                            change = 0
                            change_pct = 0
                        else:
                            continue

                        sp = StockPrice(
                            ticker=ticker,
                            price=round(price, 2),
                            change=round(change, 2),
                            change_pct=round(change_pct, 2),
                            previous_close=round(prev_close, 2),
                            fetched_at=datetime.now(timezone.utc),
                        )
                        self._cache[ticker] = sp
                        results[ticker] = sp

                    except Exception as e:
                        logger.warning("Error parsing price for %s: %s", ticker, e)

            except Exception as e:
                logger.warning("Batch download failed for chunk %d: %s", i, e)

        self._evict_stale()
        self._enforce_cache_limit()
        return results

    def clear_cache(self):
        """Clear the price cache."""
        self._cache.clear()
