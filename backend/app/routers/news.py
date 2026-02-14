"""
News feed router for TrendVest — aggregates news from yfinance and NewsAPI.
"""
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/api/news", tags=["news"])

# Simple cache
_news_cache: dict[str, dict] = {}
CACHE_TTL = 900  # 15 minutes


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
                "published_at": content.get("pubDate", ""),
                "image_url": image_url,
                "related_ticker": ticker,
                "related_topic": None,
            })
        return results
    except Exception as e:
        print(f"yfinance news error for {ticker}: {e}")
        return []


@router.get("")
async def get_news(
    topic: Optional[str] = Query(None),
    ticker: Optional[str] = Query(None),
    limit: int = Query(20, le=50),
):
    """Get latest news headlines. Filter by topic or ticker."""
    cache_key = f"{topic or ''}:{ticker or ''}:{limit}"
    now = time.time()

    if cache_key in _news_cache:
        cached = _news_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    results = []

    if ticker:
        results = _get_yfinance_news(ticker.upper())
    elif topic:
        # Get news for top stocks in the topic (use a few well-known tickers)
        topic_tickers = {
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
        tickers = topic_tickers.get(topic, [])
        for t in tickers[:2]:
            results.extend(_get_yfinance_news(t))
    else:
        # General: get news for major trending tickers
        for t in ["NVDA", "TSLA", "MSFT", "AAPL", "GOOGL"]:
            results.extend(_get_yfinance_news(t))

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
