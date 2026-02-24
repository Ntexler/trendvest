"""
Unified Feed API for TrendVest — combines trends, news (global + Israeli),
podcasts, and stock data into a single feed endpoint.
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional

from ..deps import get_db_pool, get_stock_service
from ..services.israeli_news import get_israeli_news, match_israeli_news_to_topics
from ..services.podcasts import get_podcast_episodes, transcribe_episode, analyze_transcript

router = APIRouter(prefix="/api/feed", tags=["feed"])

# Cache
_feed_cache: dict[str, dict] = {}
CACHE_TTL = 300  # 5 minutes

# Load topics data
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


def _get_topic_keywords_map() -> dict[str, list[str]]:
    """Get keyword map for all topics: {slug: [keywords]}."""
    result = {}
    for topic in _load_topics():
        result[topic["slug"]] = topic.get("keywords", [])
    return result


def _get_yfinance_news_for_topic(ticker: str, topic_slug: str) -> list[dict]:
    """Get news for a specific stock from yfinance."""
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        news = stock.news or []
        results = []
        for item in news[:5]:
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
                "language": "en",
            })
        return results
    except Exception as e:
        print(f"yfinance feed error for {ticker}: {e}")
        return []


@router.get("")
async def get_unified_feed(
    sector: Optional[str] = Query(None, description="Filter by sector"),
    include_il: bool = Query(True, description="Include Israeli news"),
    include_podcasts: bool = Query(True, description="Include podcast episodes"),
    limit: int = Query(20, le=50),
    pool=Depends(get_db_pool),
    stock_service=Depends(get_stock_service),
):
    """
    Get unified trend feed — each item is a topic with its top article,
    related stocks, and mention data combined.
    """
    cache_key = f"feed:{sector or 'all'}:{include_il}:{include_podcasts}:{limit}"
    now = time.time()

    if cache_key in _feed_cache:
        cached = _feed_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    async with pool.acquire() as conn:
        # 1. Get all active topics with momentum
        query = """
            SELECT t.id, t.slug, t.name_en, t.name_he, t.sector, t.sector_en, t.keywords,
                   COALESCE(m.score, 0) as momentum_score,
                   COALESCE(m.direction, 'stable') as direction,
                   COALESCE(m.mention_count_today, 0) as mention_count_today,
                   COALESCE(m.mention_avg_7d, 0) as mention_avg_7d,
                   m.updated_at as momentum_updated_at
            FROM topics t
            LEFT JOIN momentum_scores m ON t.id = m.topic_id
            WHERE t.is_active = true
        """
        params = []
        if sector:
            query += " AND (t.sector = $1 OR t.sector_en = $1)"
            params.append(sector)
        query += " ORDER BY COALESCE(m.score, 0) DESC LIMIT $" + str(len(params) + 1)
        params.append(limit)
        topics = await conn.fetch(query, *params)

        # 2. Get momentum history (last 7 days) for sparklines
        history_map: dict[int, list] = {}
        for topic in topics:
            rows = await conn.fetch("""
                SELECT DATE(collected_at) as day, SUM(mention_count) as mentions
                FROM topic_mentions
                WHERE topic_id = $1 AND collected_at >= NOW() - INTERVAL '7 days'
                GROUP BY DATE(collected_at)
                ORDER BY day
            """, topic["id"])
            history_map[topic["id"]] = [
                {"date": r["day"].isoformat(), "mentions": r["mentions"]}
                for r in rows
            ]

        # 3. Get stocks for each topic
        stocks_map: dict[str, list] = {}
        all_tickers = []
        for topic in topics:
            stocks = await conn.fetch("""
                SELECT ticker, company_name, relevance_note
                FROM topic_stocks ts WHERE ts.topic_id = $1
                ORDER BY ts.priority LIMIT 5
            """, topic["id"])
            stock_list = [dict(s) for s in stocks]
            stocks_map[topic["slug"]] = stock_list
            all_tickers.extend([s["ticker"] for s in stock_list])

    # 4. Batch fetch stock prices
    all_tickers = list(set(all_tickers))
    prices = stock_service.get_prices_batch(all_tickers) if all_tickers else {}

    # Enrich stocks with prices
    for slug, stock_list in stocks_map.items():
        for stock in stock_list:
            price_data = prices.get(stock["ticker"])
            if price_data:
                stock["current_price"] = price_data.price
                stock["daily_change_pct"] = price_data.change_pct
            else:
                stock["current_price"] = None
                stock["daily_change_pct"] = None

    # 5. Fetch news per topic (parallel)
    news_map: dict[str, list] = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {}
        for topic in topics:
            top_tickers = [s["ticker"] for s in stocks_map.get(topic["slug"], [])[:2]]
            for ticker in top_tickers:
                futures[executor.submit(_get_yfinance_news_for_topic, ticker, topic["slug"])] = topic["slug"]

        for future in as_completed(futures):
            slug = futures[future]
            try:
                items = future.result()
                if slug not in news_map:
                    news_map[slug] = []
                news_map[slug].extend(items)
            except Exception:
                pass

    # Deduplicate news per topic
    for slug in news_map:
        seen = set()
        unique = []
        for item in news_map[slug]:
            if item["title"] and item["title"] not in seen:
                seen.add(item["title"])
                unique.append(item)
        news_map[slug] = unique[:3]  # Top 3 articles per topic

    # 6. Israeli news (optional)
    il_news_items = []
    if include_il:
        try:
            il_news_items = get_israeli_news(limit=20)
            keyword_map = _get_topic_keywords_map()
            il_news_items = match_israeli_news_to_topics(il_news_items, keyword_map)
        except Exception as e:
            print(f"Israeli news fetch error: {e}")

    # Group Israeli news by topic
    il_news_by_topic: dict[str, list] = {}
    il_news_general: list = []
    for item in il_news_items:
        topic_slug = item.get("related_topic")
        if topic_slug:
            if topic_slug not in il_news_by_topic:
                il_news_by_topic[topic_slug] = []
            il_news_by_topic[topic_slug].append(item)
        else:
            il_news_general.append(item)

    # 7. Podcast episodes (optional)
    podcast_items = []
    if include_podcasts:
        try:
            podcast_items = get_podcast_episodes(limit=10)
        except Exception as e:
            print(f"Podcast fetch error: {e}")

    # 8. Build the unified feed
    feed = []
    for topic in topics:
        slug = topic["slug"]

        # Combine global + Israeli news for this topic
        topic_news = news_map.get(slug, [])
        topic_il_news = il_news_by_topic.get(slug, [])

        # Pick the best article (prefer one with an image)
        all_articles = topic_news + topic_il_news
        top_article = None
        for article in all_articles:
            if article.get("image_url"):
                top_article = article
                break
        if not top_article and all_articles:
            top_article = all_articles[0]

        feed_item = {
            "topic": {
                "slug": slug,
                "name_en": topic["name_en"],
                "name_he": topic["name_he"],
                "sector": topic["sector"],
                "sector_en": topic["sector_en"],
                "momentum_score": topic["momentum_score"],
                "direction": topic["direction"],
                "mention_count_today": topic["mention_count_today"],
                "mention_avg_7d": float(topic["mention_avg_7d"]),
                "updated_at": topic["momentum_updated_at"].isoformat() if topic["momentum_updated_at"] else None,
            },
            "momentum_history": history_map.get(topic["id"], []),
            "stocks": stocks_map.get(slug, [])[:5],
            "top_article": top_article,
            "articles": all_articles[:5],
            "il_news": topic_il_news[:3],
        }
        feed.append(feed_item)

    result = {
        "feed": feed,
        "il_news_general": il_news_general[:10],
        "podcasts": podcast_items[:6],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    _feed_cache[cache_key] = {"time": now, "data": result}
    return result


@router.get("/il-news")
async def get_il_news_feed(
    source: Optional[str] = Query(None, description="Source key: globes, calcalist, geektime, themarker"),
    limit: int = Query(30, le=50),
):
    """Get Israeli financial news from RSS feeds."""
    items = get_israeli_news(source=source, limit=limit)
    return {"items": items, "sources": list(PODCAST_FEEDS.keys())}


@router.get("/podcasts")
async def get_podcasts_feed(
    podcast: Optional[str] = Query(None, description="Podcast key"),
    category: Optional[str] = Query(None, description="Category: finance, tech"),
    limit: int = Query(20, le=50),
):
    """Get podcast episodes from Israeli financial podcasts."""
    from ..services.podcasts import PODCAST_FEEDS as feeds
    episodes = get_podcast_episodes(podcast=podcast, category=category, limit=limit)
    return {
        "episodes": episodes,
        "available_podcasts": {
            k: {"name": v["name"], "name_en": v["name_en"], "description": v["description"], "category": v["category"]}
            for k, v in feeds.items()
        },
    }


@router.post("/podcasts/transcribe")
async def transcribe_podcast_episode(
    audio_url: str = Query(..., description="URL of the podcast audio file"),
    language: str = Query("he", description="Language code"),
):
    """Transcribe a podcast episode and analyze it for financial insights."""
    transcript = await transcribe_episode(audio_url, language)
    if not transcript:
        raise HTTPException(status_code=503, detail="Transcription service unavailable. Requires OPENAI_API_KEY.")

    analysis = await analyze_transcript(transcript["text"], language)

    return {
        "transcript": {
            "text": transcript["text"][:5000],  # Truncate for response size
            "language": transcript["language"],
            "segment_count": len(transcript.get("segments", [])),
        },
        "analysis": analysis,
    }
