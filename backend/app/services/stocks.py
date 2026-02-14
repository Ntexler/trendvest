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

    def __init__(self):
        self._cache: dict[str, StockPrice] = {}

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

        # Batch download — single HTTP request for all tickers
        try:
            tickers_str = " ".join(uncached)
            data = yf.download(tickers_str, period="2d", progress=False, threads=True)

            if data.empty:
                logger.warning("Batch download returned empty data")
                return results

            for ticker in uncached:
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
            logger.warning("Batch download failed: %s", e)

        return results

    def clear_cache(self):
        """Clear the price cache."""
        self._cache.clear()
