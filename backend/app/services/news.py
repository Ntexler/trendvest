"""
News data collector for TrendVest.
Uses NewsAPI.org free tier (100 requests/day).
"""
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

try:
    import requests
except ImportError:
    requests = None


class NewsCollector:
    """Collects mention counts from news articles via NewsAPI."""

    BASE_URL = "https://newsapi.org/v2/everything"

    def __init__(self):
        self.api_key = os.getenv("NEWS_API_KEY", "")
        self._rate_limit_delay = 1.0
        self._daily_requests = 0
        self._max_daily = 95  # Leave buffer from 100 limit

    def count_mentions(self, keywords: list[str], days_back: int = 1) -> int:
        """
        Count news articles mentioning keywords.

        Args:
            keywords: List of keywords to search
            days_back: How many days back to search

        Returns:
            Total article count
        """
        if not self.api_key:
            print("  ⚠️  NEWS_API_KEY not set")
            return 0

        if self._daily_requests >= self._max_daily:
            print("  ⚠️  NewsAPI daily limit reached")
            return 0

        # Use top 3 keywords to save query length
        query = " OR ".join(keywords[:3])
        from_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")

        try:
            response = requests.get(self.BASE_URL, params={
                "q": query,
                "from": from_date,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 1,  # We only need totalResults
                "apiKey": self.api_key,
            }, timeout=10)

            self._daily_requests += 1
            time.sleep(self._rate_limit_delay)

            if response.status_code == 200:
                data = response.json()
                return data.get("totalResults", 0)
            else:
                print(f"  ⚠️  NewsAPI returned {response.status_code}: {response.text[:100]}")
                return 0

        except Exception as e:
            print(f"  ❌ NewsAPI error: {e}")
            return 0

    def collect_topic(self, topic: dict) -> dict:
        """Collect news mention data for a single topic."""
        now = datetime.now(timezone.utc)
        print(f"  📰 Collecting news for: {topic['slug']}...")

        count = self.count_mentions(topic["keywords"])
        print(f"  ✅ {topic['slug']}: {count} articles")

        return {
            "topic_slug": topic["slug"],
            "source": "news",
            "mention_count": count,
            "collected_at": now,
            "period_start": now - timedelta(days=1),
            "period_end": now,
        }

    def collect_all(self, topics: list[dict]) -> list[dict]:
        """Collect news data for all topics."""
        print(f"\n{'='*50}")
        print(f"📰 News Collection — {len(topics)} topics")
        print(f"   (API requests used: {self._daily_requests}/{self._max_daily})")
        print(f"{'='*50}")

        results = []
        for topic in topics:
            if self._daily_requests >= self._max_daily:
                print(f"  ⛔ Daily limit reached, skipping remaining topics")
                break
            result = self.collect_topic(topic)
            results.append(result)

        total = sum(r["mention_count"] for r in results)
        print(f"\n📊 Total articles found: {total}")
        return results
