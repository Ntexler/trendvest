"""
Alpha Vantage news sentiment service for TrendVest.
Free tier: 25 requests/day. Provides news with AI-powered sentiment analysis.
Get API key: https://www.alphavantage.co/support/#api-key
"""
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests

# Cache
_av_cache: dict[str, dict] = {}
CACHE_TTL = 1800  # 30 minutes (conserve 25/day limit)


class AlphaVantageCollector:
    """Collects news sentiment data from Alpha Vantage API."""

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self):
        self.api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
        self._daily_requests = 0
        self._max_daily = 23  # Buffer from 25 limit
        self._rate_limit_delay = 1.0

    def get_news_sentiment(
        self,
        tickers: Optional[list[str]] = None,
        topics: Optional[list[str]] = None,
        limit: int = 20,
    ) -> list[dict]:
        """
        Get news articles with sentiment scores.

        Args:
            tickers: Stock tickers (e.g. ["NVDA", "AAPL"])
            topics: Topic labels from Alpha Vantage: technology, earnings,
                    ipo, mergers_and_acquisitions, financial_markets,
                    economy_fiscal, economy_monetary, economy_macro,
                    energy_transportation, finance, life_sciences,
                    manufacturing, real_estate, retail_wholesale
            limit: Max articles (up to 200)
        """
        cache_key = f"av:sentiment:{','.join(tickers or [])}:{','.join(topics or [])}:{limit}"
        now = time.time()
        if cache_key in _av_cache:
            cached = _av_cache[cache_key]
            if now - cached["time"] < CACHE_TTL:
                return cached["data"]

        if not self.api_key:
            return []

        if self._daily_requests >= self._max_daily:
            print("  ⚠️  Alpha Vantage daily limit reached")
            return []

        params = {
            "function": "NEWS_SENTIMENT",
            "apikey": self.api_key,
            "limit": min(limit, 200),
            "sort": "LATEST",
        }
        if tickers:
            params["tickers"] = ",".join(tickers[:5])
        if topics:
            params["topics"] = ",".join(topics[:3])

        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=15)
            self._daily_requests += 1
            time.sleep(self._rate_limit_delay)

            if resp.status_code != 200:
                return []

            data = resp.json()
            feed = data.get("feed", [])

            results = []
            for item in feed[:limit]:
                # Extract overall sentiment
                sentiment_score = float(item.get("overall_sentiment_score", 0))
                sentiment_label = item.get("overall_sentiment_label", "Neutral")

                # Extract ticker-specific sentiment
                ticker_sentiments = {}
                for ts in item.get("ticker_sentiment", []):
                    ticker_sentiments[ts.get("ticker", "")] = {
                        "relevance": float(ts.get("relevance_score", 0)),
                        "sentiment_score": float(ts.get("ticker_sentiment_score", 0)),
                        "sentiment_label": ts.get("ticker_sentiment_label", "Neutral"),
                    }

                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "source": item.get("source", ""),
                    "source_type": "alpha_vantage",
                    "published_at": _parse_av_time(item.get("time_published", "")),
                    "image_url": item.get("banner_image", "") or "",
                    "summary": item.get("summary", "")[:300],
                    "sentiment_score": sentiment_score,
                    "sentiment_label": sentiment_label,
                    "ticker_sentiments": ticker_sentiments,
                    "topics": [t.get("topic", "") for t in item.get("topics", [])],
                    "related_ticker": None,
                    "related_topic": None,
                    "language": "en",
                })

            _av_cache[cache_key] = {"time": now, "data": results}
            return results

        except Exception as e:
            print(f"Alpha Vantage error: {e}")
            return []

    def get_topic_sentiment(self, topic_slug: str, av_topics: list[str], tickers: list[str]) -> Optional[dict]:
        """
        Get aggregated sentiment for a topic.
        Returns average sentiment score and breakdown.
        """
        articles = self.get_news_sentiment(tickers=tickers[:3], topics=av_topics[:2], limit=20)
        if not articles:
            return None

        scores = [a["sentiment_score"] for a in articles if a.get("sentiment_score")]
        if not scores:
            return None

        avg_score = sum(scores) / len(scores)
        bullish = sum(1 for s in scores if s > 0.15)
        bearish = sum(1 for s in scores if s < -0.15)
        neutral = len(scores) - bullish - bearish

        return {
            "topic_slug": topic_slug,
            "avg_sentiment": round(avg_score, 3),
            "sentiment_label": "Bullish" if avg_score > 0.15 else "Bearish" if avg_score < -0.15 else "Neutral",
            "article_count": len(articles),
            "bullish_count": bullish,
            "bearish_count": bearish,
            "neutral_count": neutral,
        }


def _parse_av_time(time_str: str) -> str:
    """Parse Alpha Vantage time format (20240101T120000) to ISO format."""
    if not time_str:
        return ""
    try:
        dt = datetime.strptime(time_str, "%Y%m%dT%H%M%S")
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except (ValueError, TypeError):
        return time_str
