"""
Google Trends data collector for TrendVest.
Uses pytrends (unofficial Google Trends API) to get interest-over-time data.
No API key needed — free but rate-limited.
"""
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

try:
    from pytrends.request import TrendReq
except ImportError:
    TrendReq = None


class GoogleTrendsCollector:
    """Collects interest scores from Google Trends for predefined topics."""

    def __init__(self):
        self._pytrends = None
        self._rate_limit_delay = 2.0  # Google rate-limits aggressively

    @property
    def pytrends(self):
        if self._pytrends is None:
            if not TrendReq:
                raise RuntimeError("pytrends not installed. Run: pip install pytrends")
            self._pytrends = TrendReq(hl="en-US", tz=360)
        return self._pytrends

    def get_interest(self, keywords: list[str], timeframe: str = "now 7-d") -> int:
        """
        Get average interest score for keywords from Google Trends.

        Args:
            keywords: Keywords to search (max 5 per request)
            timeframe: 'now 1-d', 'now 7-d', 'today 1-m', 'today 3-m'

        Returns:
            Average interest score (0-100)
        """
        if not TrendReq:
            return 0

        # Google Trends accepts max 5 keywords per request
        kw_list = keywords[:5]

        try:
            self.pytrends.build_payload(kw_list, timeframe=timeframe, geo="")
            data = self.pytrends.interest_over_time()

            if data.empty:
                return 0

            # Drop 'isPartial' column if present
            if "isPartial" in data.columns:
                data = data.drop(columns=["isPartial"])

            # Average interest across all keywords and time points
            avg = data.values.mean()
            return int(round(avg))

        except Exception as e:
            print(f"  Google Trends error: {e}")
            return 0

    def get_related_queries(self, keyword: str) -> list[str]:
        """Get rising related queries for a keyword."""
        if not TrendReq:
            return []

        try:
            self.pytrends.build_payload([keyword], timeframe="now 7-d", geo="")
            related = self.pytrends.related_queries()

            rising = related.get(keyword, {}).get("rising")
            if rising is not None and not rising.empty:
                return rising["query"].tolist()[:10]
            return []

        except Exception:
            return []

    def collect_topic(self, topic: dict) -> dict:
        """Collect Google Trends data for a single topic."""
        now = datetime.now(timezone.utc)
        print(f"  Google Trends for: {topic['slug']}...")

        try:
            # Use top 3 keywords for interest score
            score = self.get_interest(topic["keywords"][:3], timeframe="now 7-d")
            time.sleep(self._rate_limit_delay)
        except Exception as e:
            print(f"  Failed: {e}")
            score = 0

        print(f"  {topic['slug']}: interest={score}")

        return {
            "topic_slug": topic["slug"],
            "source": "google_trends",
            "mention_count": score,  # Using interest score as "mention_count"
            "collected_at": now,
            "period_start": now - timedelta(days=7),
            "period_end": now,
        }

    def collect_all(self, topics: list[dict]) -> list[dict]:
        """Collect Google Trends data for all topics."""
        if not TrendReq:
            print("pytrends not installed, skipping Google Trends collection")
            return []

        print(f"\n{'='*50}")
        print(f"Google Trends Collection - {len(topics)} topics")
        print(f"{'='*50}")

        results = []
        for topic in topics:
            result = self.collect_topic(topic)
            results.append(result)

        total = sum(r["mention_count"] for r in results)
        print(f"\nTotal interest score: {total}")
        return results
