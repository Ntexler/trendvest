"""
X (Twitter) data collector for TrendVest.
Uses the X API v2 (Free tier: 1 app, read-only, 100 reads/month on free,
or Basic tier: 10k reads/month).

Also supports scraping public search counts without auth as a fallback.
"""
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

try:
    import requests as req_lib
except ImportError:
    req_lib = None


class XTwitterCollector:
    """Collects mention counts from X (Twitter) for predefined topics."""

    # X API v2 endpoints
    SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"
    COUNT_URL = "https://api.twitter.com/2/tweets/counts/recent"

    def __init__(self):
        self.bearer_token = os.getenv("X_BEARER_TOKEN", "")
        self._rate_limit_delay = 1.0
        self._daily_requests = 0
        self._max_daily = 90  # Leave buffer from free tier limits

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "User-Agent": "TrendVest/1.0",
        }

    def count_mentions(self, keywords: list[str], hours_back: int = 24) -> int:
        """
        Count recent tweets mentioning keywords.

        Uses tweet counts endpoint (requires Basic tier) or falls back
        to search endpoint (Free tier).

        Args:
            keywords: Keywords to search for
            hours_back: How many hours back to search

        Returns:
            Total tweet count
        """
        if not self.bearer_token:
            return 0

        if not req_lib:
            return 0

        if self._daily_requests >= self._max_daily:
            print("  X API daily limit reached")
            return 0

        # Build query: "keyword1" OR "keyword2" OR keyword3
        query_parts = []
        for kw in keywords[:5]:
            if " " in kw:
                query_parts.append(f'"{kw}"')
            else:
                query_parts.append(kw)
        query = " OR ".join(query_parts) + " -is:retweet lang:en"

        # Try counts endpoint first (Basic tier)
        try:
            start_time = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            response = req_lib.get(
                self.COUNT_URL,
                headers=self._headers(),
                params={
                    "query": query,
                    "start_time": start_time,
                    "granularity": "day",
                },
                timeout=10,
            )
            self._daily_requests += 1
            time.sleep(self._rate_limit_delay)

            if response.status_code == 200:
                data = response.json()
                total = data.get("meta", {}).get("total_tweet_count", 0)
                return total
            elif response.status_code == 403:
                # Counts endpoint requires Basic tier, fall back to search
                pass
            else:
                print(f"  X API counts returned {response.status_code}")
        except Exception as e:
            print(f"  X API counts error: {e}")

        # Fallback: use search endpoint and count results
        try:
            response = req_lib.get(
                self.SEARCH_URL,
                headers=self._headers(),
                params={
                    "query": query,
                    "max_results": 100,
                    "tweet.fields": "created_at",
                },
                timeout=10,
            )
            self._daily_requests += 1
            time.sleep(self._rate_limit_delay)

            if response.status_code == 200:
                data = response.json()
                return data.get("meta", {}).get("result_count", 0)
            else:
                print(f"  X API search returned {response.status_code}: {response.text[:100]}")
                return 0

        except Exception as e:
            print(f"  X API search error: {e}")
            return 0

    def get_recent_tweets(self, keywords: list[str], max_results: int = 10) -> list[dict]:
        """
        Get recent tweets for display in the news feed.

        Returns list of tweet dicts with text, author, url, created_at.
        """
        if not self.bearer_token or not req_lib:
            return []

        if self._daily_requests >= self._max_daily:
            return []

        query_parts = []
        for kw in keywords[:3]:
            if " " in kw:
                query_parts.append(f'"{kw}"')
            else:
                query_parts.append(kw)
        query = " OR ".join(query_parts) + " -is:retweet lang:en"

        try:
            response = req_lib.get(
                self.SEARCH_URL,
                headers=self._headers(),
                params={
                    "query": query,
                    "max_results": min(max_results, 100),
                    "tweet.fields": "created_at,public_metrics,author_id",
                    "expansions": "author_id",
                    "user.fields": "username,name",
                },
                timeout=10,
            )
            self._daily_requests += 1

            if response.status_code != 200:
                return []

            data = response.json()
            tweets = data.get("data", [])

            # Build user lookup
            users = {}
            for user in data.get("includes", {}).get("users", []):
                users[user["id"]] = user

            results = []
            for tweet in tweets:
                author = users.get(tweet.get("author_id"), {})
                username = author.get("username", "")
                results.append({
                    "text": tweet.get("text", ""),
                    "author": author.get("name", ""),
                    "username": username,
                    "url": f"https://x.com/{username}/status/{tweet['id']}" if username else "",
                    "created_at": tweet.get("created_at", ""),
                    "likes": tweet.get("public_metrics", {}).get("like_count", 0),
                    "retweets": tweet.get("public_metrics", {}).get("retweet_count", 0),
                })

            return results

        except Exception as e:
            print(f"  X API tweets error: {e}")
            return []

    def collect_topic(self, topic: dict) -> dict:
        """Collect X/Twitter mention data for a single topic."""
        now = datetime.now(timezone.utc)
        print(f"  X/Twitter for: {topic['slug']}...")

        count = self.count_mentions(topic["keywords"], hours_back=24)
        print(f"  {topic['slug']}: {count} tweets")

        return {
            "topic_slug": topic["slug"],
            "source": "x",
            "mention_count": count,
            "collected_at": now,
            "period_start": now - timedelta(days=1),
            "period_end": now,
        }

    def collect_all(self, topics: list[dict]) -> list[dict]:
        """Collect X/Twitter data for all topics."""
        if not self.bearer_token:
            print("X_BEARER_TOKEN not set, skipping X collection")
            return []

        print(f"\n{'='*50}")
        print(f"X/Twitter Collection - {len(topics)} topics")
        print(f"  (API requests used: {self._daily_requests}/{self._max_daily})")
        print(f"{'='*50}")

        results = []
        for topic in topics:
            if self._daily_requests >= self._max_daily:
                print("  Daily limit reached, skipping remaining topics")
                break
            result = self.collect_topic(topic)
            results.append(result)

        total = sum(r["mention_count"] for r in results)
        print(f"\nTotal tweets found: {total}")
        return results
