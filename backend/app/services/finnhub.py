"""
Finnhub news + sentiment service for TrendVest.
Free tier: 60 API calls/minute. Provides market news with sentiment scores.
Get API key: https://finnhub.io/register
"""
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests

# Cache
_finnhub_cache: dict[str, dict] = {}
CACHE_TTL = 900  # 15 minutes


class FinnhubCollector:
    """Collects news and sentiment data from Finnhub API."""

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self):
        self.api_key = os.getenv("FINNHUB_API_KEY", "")
        self._rate_limit_delay = 1.0  # Stay safe under 60/min

    def _get(self, endpoint: str, params: dict) -> Optional[dict]:
        if not self.api_key:
            return None
        params["token"] = self.api_key
        try:
            resp = requests.get(
                f"{self.BASE_URL}/{endpoint}",
                params=params,
                timeout=10,
            )
            time.sleep(self._rate_limit_delay)
            if resp.status_code == 200:
                return resp.json()
            print(f"Finnhub {endpoint} returned {resp.status_code}")
            return None
        except Exception as e:
            print(f"Finnhub error ({endpoint}): {e}")
            return None

    def get_market_news(self, category: str = "general", limit: int = 20) -> list[dict]:
        """
        Get general market news.
        Categories: general, forex, crypto, merger
        """
        cache_key = f"finnhub:market:{category}:{limit}"
        now = time.time()
        if cache_key in _finnhub_cache:
            cached = _finnhub_cache[cache_key]
            if now - cached["time"] < CACHE_TTL:
                return cached["data"]

        data = self._get("news", {"category": category, "minId": 0})
        if not data:
            return []

        results = []
        for item in data[:limit]:
            results.append({
                "title": item.get("headline", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "source_type": "finnhub",
                "published_at": datetime.fromtimestamp(
                    item.get("datetime", 0), tz=timezone.utc
                ).isoformat() if item.get("datetime") else "",
                "image_url": item.get("image", ""),
                "summary": item.get("summary", "")[:300],
                "related_ticker": None,
                "related_topic": None,
                "language": "en",
            })

        _finnhub_cache[cache_key] = {"time": now, "data": results}
        return results

    def get_company_news(self, ticker: str, days_back: int = 3, limit: int = 10) -> list[dict]:
        """Get news for a specific company/ticker."""
        cache_key = f"finnhub:company:{ticker}:{days_back}"
        now = time.time()
        if cache_key in _finnhub_cache:
            cached = _finnhub_cache[cache_key]
            if now - cached["time"] < CACHE_TTL:
                return cached["data"]

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        from_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")

        data = self._get("company-news", {
            "symbol": ticker.upper(),
            "from": from_date,
            "to": today,
        })
        if not data:
            return []

        results = []
        for item in data[:limit]:
            results.append({
                "title": item.get("headline", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "source_type": "finnhub",
                "published_at": datetime.fromtimestamp(
                    item.get("datetime", 0), tz=timezone.utc
                ).isoformat() if item.get("datetime") else "",
                "image_url": item.get("image", ""),
                "summary": item.get("summary", "")[:300],
                "related_ticker": ticker.upper(),
                "related_topic": None,
                "language": "en",
            })

        _finnhub_cache[cache_key] = {"time": now, "data": results}
        return results

    def get_news_sentiment(self, ticker: str) -> Optional[dict]:
        """
        Get news sentiment for a ticker.
        Returns buzz, sentiment scores, and article counts.
        """
        cache_key = f"finnhub:sentiment:{ticker}"
        now = time.time()
        if cache_key in _finnhub_cache:
            cached = _finnhub_cache[cache_key]
            if now - cached["time"] < CACHE_TTL:
                return cached["data"]

        data = self._get("news-sentiment", {"symbol": ticker.upper()})
        if not data:
            return None

        result = {
            "ticker": ticker.upper(),
            "buzz": data.get("buzz", {}),
            "sentiment": data.get("sentiment", {}),
            "company_news_score": data.get("companyNewsScore", 0),
            "sector_avg_bullish": data.get("sectorAverageBullishPercent", 0),
            "sector_avg_news_score": data.get("sectorAverageNewsScore", 0),
        }

        _finnhub_cache[cache_key] = {"time": now, "data": result}
        return result

    def count_mentions(self, keywords: list[str], days_back: int = 1) -> int:
        """Count news mentions — uses market news search."""
        news = self.get_market_news(limit=50)
        count = 0
        for item in news:
            text = (item.get("title", "") + " " + item.get("summary", "")).lower()
            for kw in keywords:
                if kw.lower() in text:
                    count += 1
                    break
        return count

    def collect_topic(self, topic: dict) -> dict:
        """Collect Finnhub data for a single topic."""
        now = datetime.now(timezone.utc)
        print(f"  📊 Finnhub for: {topic['slug']}...")

        count = self.count_mentions(topic["keywords"])
        print(f"  ✅ {topic['slug']}: {count} articles")

        return {
            "topic_slug": topic["slug"],
            "source": "finnhub",
            "mention_count": count,
            "collected_at": now,
            "period_start": now - timedelta(days=1),
            "period_end": now,
        }
