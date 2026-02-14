"""
News feed router for TrendVest — aggregates news from yfinance, X (Twitter),
and Google Trends related queries.
"""
import os
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/api/news", tags=["news"])

# Simple cache
_news_cache: dict[str, dict] = {}
CACHE_TTL = 900  # 15 minutes

# Topic → keywords mapping (for X and Google Trends lookups)
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "ai": ["artificial intelligence", "AI", "ChatGPT", "LLM"],
    "nuclear": ["nuclear energy", "uranium", "nuclear power"],
    "ev": ["electric vehicles", "EV", "Tesla"],
    "crypto": ["cryptocurrency", "Bitcoin", "blockchain"],
    "cyber": ["cybersecurity", "data breach", "cyber attack"],
    "quantum": ["quantum computing", "quantum"],
    "space": ["space exploration", "SpaceX", "rocket launch"],
    "glp1": ["GLP-1", "Ozempic", "weight loss drug"],
    "semi": ["semiconductors", "chip shortage", "TSMC"],
    "solar": ["solar energy", "solar panels", "renewable"],
}

# Topic → tickers mapping (for yfinance news)
TOPIC_TICKERS: dict[str, list[str]] = {
    "ai": ["NVDA", "MSFT", "GOOGL"],
    "nuclear": ["CCJ", "LEU"],
    "ev": ["TSLA", "RIVN"],
    "crypto": ["MSTR", "COIN"],
    "cyber": ["CRWD", "PANW"],
    "quantum": ["IONQ", "RGTI"],
    "space": ["RKLB"],
    "glp1": ["LLY", "NVO"],
    "semi": ["TSM", "AVGO"],
    "solar": ["ENPH", "FSLR"],
}


def _get_yfinance_news(ticker: str) -> list[dict]:
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
                "related_topic": None,
            })
        return results
    except Exception as e:
        print(f"yfinance news error for {ticker}: {e}")
        return []


def _get_x_tweets(keywords: list[str], max_results: int = 5) -> list[dict]:
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
                "related_topic": None,
                "likes": tweet.get("likes", 0),
                "retweets": tweet.get("retweets", 0),
            })
        return results
    except Exception as e:
        print(f"X tweets error: {e}")
        return []


def _get_google_trends_queries(keywords: list[str]) -> list[dict]:
    """Get rising related queries from Google Trends."""
    try:
        from ..services.google_trends import GoogleTrendsCollector
        collector = GoogleTrendsCollector()
        related = collector.get_related_queries(keywords[0])
        results = []
        for query in related[:5]:
            results.append({
                "title": f"Trending search: \"{query}\"",
                "url": f"https://trends.google.com/trends/explore?q={query.replace(' ', '+')}",
                "source": "Google Trends",
                "source_type": "google_trends",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "image_url": "",
                "related_ticker": None,
                "related_topic": None,
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
    limit: int = Query(20, le=50),
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
        if source_type in (None, "news"):
            results.extend(_get_yfinance_news(ticker.upper()))
        if source_type in (None, "x"):
            results.extend(_get_x_tweets([ticker.upper()], max_results=5))
    elif topic:
        tickers = TOPIC_TICKERS.get(topic, [])
        keywords = TOPIC_KEYWORDS.get(topic, [])

        if source_type in (None, "news"):
            for t in tickers[:2]:
                results.extend(_get_yfinance_news(t))
        if source_type in (None, "x") and keywords:
            results.extend(_get_x_tweets(keywords, max_results=5))
        if source_type in (None, "google_trends") and keywords:
            results.extend(_get_google_trends_queries(keywords))
    else:
        # General feed: mix of all sources
        if source_type in (None, "news"):
            for t in ["NVDA", "TSLA", "MSFT", "AAPL", "GOOGL"]:
                results.extend(_get_yfinance_news(t))
        if source_type in (None, "x"):
            results.extend(_get_x_tweets(["stocks", "investing", "market"], max_results=5))
        if source_type in (None, "google_trends"):
            results.extend(_get_google_trends_queries(["stock market"]))

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
