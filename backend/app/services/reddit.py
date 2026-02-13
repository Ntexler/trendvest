"""
Reddit data collector for TrendVest.
Uses PRAW (Python Reddit API Wrapper) to count keyword mentions.
"""
import os
import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

try:
    import praw
except ImportError:
    praw = None
    print("⚠️  praw not installed. Run: pip install praw")


class RedditCollector:
    """Collects mention counts from Reddit for predefined topics."""

    def __init__(self):
        self.client_id = os.getenv("REDDIT_CLIENT_ID", "")
        self.client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
        self.user_agent = os.getenv("REDDIT_USER_AGENT", "TrendVest/1.0")
        self._reddit = None
        self._rate_limit_delay = 1.0  # seconds between requests

    @property
    def reddit(self):
        """Lazy init Reddit client."""
        if self._reddit is None:
            if not praw:
                raise RuntimeError("praw not installed")
            if not self.client_id or not self.client_secret:
                raise RuntimeError("Reddit credentials not set. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET")

            self._reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent,
            )
        return self._reddit

    def count_mentions(self, keywords: list[str], subreddits: list[str],
                       time_filter: str = "day", limit: int = 100) -> int:
        """
        Count mentions of keywords across subreddits.

        Args:
            keywords: List of keywords to search for
            subreddits: List of subreddit names to search in
            time_filter: 'hour', 'day', 'week', 'month', 'year', 'all'
            limit: Max posts per search query

        Returns:
            Total mention count
        """
        total = 0
        query = " OR ".join(f'"{kw}"' if " " in kw else kw for kw in keywords[:5])  # Top 5 keywords

        for sub_name in subreddits:
            try:
                subreddit = self.reddit.subreddit(sub_name)
                results = subreddit.search(
                    query=query,
                    time_filter=time_filter,
                    sort="new",
                    limit=limit
                )
                count = sum(1 for _ in results)
                total += count
                time.sleep(self._rate_limit_delay)  # Rate limiting

            except Exception as e:
                print(f"  ⚠️  Error searching r/{sub_name}: {e}")
                continue

        return total

    def collect_topic(self, topic: dict) -> dict:
        """
        Collect mention data for a single topic.

        Args:
            topic: Topic dict with 'slug', 'keywords', 'subreddits'

        Returns:
            Dict with topic_slug, source, mention_count, timestamps
        """
        now = datetime.now(timezone.utc)
        print(f"  📡 Collecting r/ data for: {topic['slug']}...")

        try:
            count = self.count_mentions(
                keywords=topic["keywords"],
                subreddits=topic.get("subreddits", ["wallstreetbets", "stocks", "investing"]),
                time_filter="day",
                limit=100
            )
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            count = 0

        print(f"  ✅ {topic['slug']}: {count} mentions")

        return {
            "topic_slug": topic["slug"],
            "source": "reddit",
            "mention_count": count,
            "collected_at": now,
            "period_start": now - timedelta(days=1),
            "period_end": now,
        }

    def collect_all(self, topics: list[dict]) -> list[dict]:
        """Collect data for all topics. Returns list of mention records."""
        print(f"\n{'='*50}")
        print(f"🔴 Reddit Collection — {len(topics)} topics")
        print(f"{'='*50}")

        results = []
        for topic in topics:
            result = self.collect_topic(topic)
            results.append(result)

        total = sum(r["mention_count"] for r in results)
        print(f"\n📊 Total mentions collected: {total}")
        return results
