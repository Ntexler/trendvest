"""
News feed router for TrendVest — aggregates news from yfinance, X (Twitter),
and Google Trends related queries.
"""
import os
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/api/news", tags=["news"])

# Simple cache
_news_cache: dict[str, dict] = {}
CACHE_TTL = 900  # 15 minutes

# Load topics from JSON to build mappings dynamically
_topics_data: list[dict] = []

def _load_topics():
    global _topics_data
    if _topics_data:
        return _topics_data
    topics_file = Path(__file__).parent.parent / "data" / "topics.json"
    try:
        with open(topics_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        _topics_data = data.get("topics", [])
    except Exception:
        _topics_data = []
    return _topics_data


def _get_topic_tickers(slug: str) -> list[str]:
    """Get top tickers for a topic from topics.json."""
    for topic in _load_topics():
        if topic["slug"] == slug:
            return [s["ticker"] for s in topic.get("stocks", [])[:3]]
    return []


def _get_topic_keywords(slug: str) -> list[str]:
    """Get keywords for a topic from topics.json."""
    for topic in _load_topics():
        if topic["slug"] == slug:
            return topic.get("keywords", [])[:5]
    return []


def _get_topic_name(slug: str) -> str:
    """Get English name for a topic."""
    for topic in _load_topics():
        if topic["slug"] == slug:
            return topic.get("name_en", slug)
    return slug


def _get_all_topic_slugs() -> list[str]:
    return [t["slug"] for t in _load_topics()]


def _get_yfinance_news(ticker: str, topic_slug: str | None = None) -> list[dict]:
    """Get news for a specific stock from yfinance."""
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        news = stock.news or []
        results = []
        for item in news[:10]:
            content = item.get("content", {})
            thumbnail = content.get("thumbnail")
            image_url = ""
            if thumbnail and thumbnail.get("resolutions"):
                image_url = thumbnail["resolutions"][0].get("url", "")

            results.append({
                "title": content.get("title", ""),
                "url": content.get("canonicalUrl", {}).get("url", ""),
                "source": content.get("provider", {}).get("displayName", ""),
                "source_type": "news",
                "published_at": content.get("pubDate", ""),
                "image_url": image_url,
                "related_ticker": ticker,
                "related_topic": topic_slug,
            })
        return results
    except Exception as e:
        print(f"yfinance news error for {ticker}: {e}")
        return []


def _get_newsapi_articles(keywords: list[str], topic_slug: str | None = None) -> list[dict]:
    """Get news from NewsAPI.org (requires NEWS_API_KEY in .env)."""
    api_key = os.getenv("NEWS_API_KEY", "")
    if not api_key:
        return []
    try:
        import requests
        query = " OR ".join(keywords[:3])
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "sortBy": "publishedAt",
                "pageSize": 10,
                "language": "en",
                "apiKey": api_key,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        articles = resp.json().get("articles", [])
        results = []
        for a in articles:
            results.append({
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "source": a.get("source", {}).get("name", ""),
                "source_type": "news",
                "published_at": a.get("publishedAt", ""),
                "image_url": a.get("urlToImage", "") or "",
                "related_ticker": None,
                "related_topic": topic_slug,
            })
        return results
    except Exception as e:
        print(f"NewsAPI error: {e}")
        return []


def _get_stock_news_combined(ticker: str, topic_slug: str | None = None) -> list[dict]:
    """Try yfinance first, fall back to NewsAPI for a stock."""
    results = _get_yfinance_news(ticker, topic_slug)
    if not results:
        # yfinance failed, try NewsAPI with the ticker as keyword
        results = _get_newsapi_articles([ticker], topic_slug)
    return results


def _get_x_tweets(keywords: list[str], topic_slug: str | None = None, max_results: int = 5) -> list[dict]:
    """Get recent tweets from X for the news feed."""
    try:
        from ..services.x_twitter import XTwitterCollector
        collector = XTwitterCollector()
        tweets = collector.get_recent_tweets(keywords, max_results=max_results)
        results = []
        for tweet in tweets:
            results.append({
                "title": tweet["text"][:200],
                "url": tweet.get("url", ""),
                "source": f"@{tweet['username']}" if tweet.get("username") else "X",
                "source_type": "x",
                "published_at": tweet.get("created_at", ""),
                "image_url": "",
                "related_ticker": None,
                "related_topic": topic_slug,
                "likes": tweet.get("likes", 0),
                "retweets": tweet.get("retweets", 0),
            })
        return results
    except Exception as e:
        print(f"X tweets error: {e}")
        return []


def _get_google_trends_queries(keywords: list[str], topic_slug: str | None = None) -> list[dict]:
    """Get rising related queries from Google Trends for a specific topic."""
    try:
        from ..services.google_trends import GoogleTrendsCollector
        collector = GoogleTrendsCollector()
        # Use the first keyword which is the most specific for the topic
        related = collector.get_related_queries(keywords[0])
        results = []
        for query in related[:5]:
            topic_label = _get_topic_name(topic_slug) if topic_slug else "Market"
            results.append({
                "title": f"\U0001F4C8 Trending: \"{query}\"",
                "url": f"https://trends.google.com/trends/explore?q={query.replace(' ', '+')}",
                "source": "Google Trends",
                "source_type": "google_trends",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "image_url": "",
                "related_ticker": None,
                "related_topic": topic_slug,
            })
        return results
    except Exception as e:
        print(f"Google Trends queries error: {e}")
        return []


@router.get("")
async def get_news(
    topic: Optional[str] = Query(None),
    ticker: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None, description="Filter by source: news, x, google_trends"),
    limit: int = Query(30, le=50),
):
    """Get latest news headlines. Filter by topic, ticker, or source type."""
    cache_key = f"{topic or ''}:{ticker or ''}:{source_type or ''}:{limit}"
    now = time.time()

    if cache_key in _news_cache:
        cached = _news_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    results = []

    if ticker:
        # Single stock: get news + X tweets about that ticker
        if source_type in (None, "news"):
            results.extend(_get_stock_news_combined(ticker.upper()))
        if source_type in (None, "x"):
            results.extend(_get_x_tweets([ticker.upper()], max_results=5))
    elif topic:
        # Topic: use actual topic data from topics.json
        tickers = _get_topic_tickers(topic)
        keywords = _get_topic_keywords(topic)

        if source_type in (None, "news"):
            # Try yfinance for stock-specific news — parallel
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [
                    executor.submit(_get_stock_news_combined, t, topic_slug=topic)
                    for t in tickers[:3]
                ]
                for future in as_completed(futures):
                    try:
                        results.extend(future.result())
                    except Exception:
                        pass
            # Also try NewsAPI for broader topic news
            if keywords:
                results.extend(_get_newsapi_articles(keywords, topic_slug=topic))
        if source_type in (None, "x") and keywords:
            results.extend(_get_x_tweets(keywords[:3], topic_slug=topic, max_results=5))
        if source_type in (None, "google_trends") and keywords:
            results.extend(_get_google_trends_queries(keywords, topic_slug=topic))
    else:
        # General feed: mix news from multiple topics for variety
        if source_type in (None, "news"):
            # Get news from top tickers across different topics — parallel
            featured_tickers = [
                ("NVDA", "ai"), ("TSLA", "ev"), ("MSFT", "ai"),
                ("CCJ", "nuclear"), ("LLY", "glp1"), ("CRWD", "cyber"),
                ("IONQ", "quantum"), ("COIN", "crypto"),
            ]
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = {
                    executor.submit(_get_stock_news_combined, t, topic_slug=s): t
                    for t, s in featured_tickers
                }
                for future in as_completed(futures):
                    try:
                        results.extend(future.result())
                    except Exception:
                        pass
            # Broad market news via NewsAPI
            results.extend(_get_newsapi_articles(["stock market", "investing", "wall street"]))

        if source_type in (None, "x"):
            # Get tweets about specific trending topics, not generic "stocks"
            results.extend(_get_x_tweets(
                ["artificial intelligence stocks", "NVDA", "Tesla"],
                topic_slug="ai", max_results=3
            ))
            results.extend(_get_x_tweets(
                ["nuclear energy", "uranium"],
                topic_slug="nuclear", max_results=3
            ))

        if source_type in (None, "google_trends"):
            # Get trends for specific topics, not generic "stock market"
            for slug in ["ai", "nuclear", "ev"]:
                kw = _get_topic_keywords(slug)
                if kw:
                    results.extend(_get_google_trends_queries(kw, topic_slug=slug))

    # Deduplicate by title
    seen_titles = set()
    unique = []
    for item in results:
        if item["title"] and item["title"] not in seen_titles:
            seen_titles.add(item["title"])
            unique.append(item)

    unique = unique[:limit]

    _news_cache[cache_key] = {"time": now, "data": unique}
    return unique
