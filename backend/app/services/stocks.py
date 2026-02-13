"""
Stock price service for TrendVest.
Uses yfinance for free stock data with in-memory caching.
"""
import time
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass

try:
    import yfinance as yf
except ImportError:
    yf = None
    print("⚠️  yfinance not installed. Run: pip install yfinance")


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
        """
        Get current stock price with caching.

        Args:
            ticker: Stock ticker symbol (e.g., 'NVDA')

        Returns:
            StockPrice or None if fetch fails
        """
        # Check cache
        if ticker in self._cache:
            cached = self._cache[ticker]
            age = (datetime.now(timezone.utc) - cached.fetched_at).total_seconds()
            if age < self.CACHE_TTL:
                return cached

        # Fetch from yfinance
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
            print(f"  ⚠️  yfinance error for {ticker}: {e}")
            # Return stale cache if available
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

        # Batch fetch uncached
        if uncached and yf:
            try:
                tickers_str = " ".join(uncached)
                data = yf.download(tickers_str, period="2d", progress=False, threads=True)

                for ticker in uncached:
                    try:
                        if len(uncached) == 1:
                            close_data = data["Close"]
                        else:
                            close_data = data["Close"][ticker]

                        if len(close_data) >= 2:
                            price = float(close_data.iloc[-1])
                            prev_close = float(close_data.iloc[-2])
                            change = price - prev_close
                            change_pct = (change / prev_close) * 100 if prev_close else 0
                        elif len(close_data) == 1:
                            price = float(close_data.iloc[-1])
                            prev_close = price
                            change = 0
                            change_pct = 0
                        else:
                            results[ticker] = None
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

                    except Exception:
                        results[ticker] = self.get_price(ticker)  # Fallback to individual

            except Exception as e:
                print(f"  ⚠️  Batch download failed: {e}")
                for ticker in uncached:
                    results[ticker] = self.get_price(ticker)

        return results

    def clear_cache(self):
        """Clear the price cache."""
        self._cache.clear()
