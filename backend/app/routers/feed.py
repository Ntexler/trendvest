"""
Unified Feed API for TrendVest — combines trends, news (global + Israeli),
podcasts, SEC filings, macro data, institutional data, and stock data
into a single feed endpoint.
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional

from ..deps import get_db_pool, get_stock_service
from ..services.israeli_news import get_israeli_news, match_israeli_news_to_topics
from ..services.podcasts import get_podcast_episodes, transcribe_episode, analyze_transcript
from ..services.global_rss import get_global_news, match_global_news_to_topics
from ..services.finnhub import FinnhubCollector
from ..services.sec_edgar import get_company_filings, get_latest_filings
from ..services.fred import FredCollector
from ..services.israeli_institutional import get_institutional_data
from ..services.us_government import get_us_gov_data
from ..services.international_institutional import get_international_data
from ..services.blogs import get_blog_posts

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
    include_global: bool = Query(True, description="Include global financial news (Economist, FT, etc.)"),
    include_podcasts: bool = Query(True, description="Include podcast episodes"),
    include_sec: bool = Query(True, description="Include SEC filings"),
    limit: int = Query(20, le=50),
    pool=Depends(get_db_pool),
    stock_service=Depends(get_stock_service),
):
    """
    Get unified trend feed — each item is a topic with its top article,
    related stocks, SEC filings, and mention data combined.
    """
    cache_key = f"feed:{sector or 'all'}:{include_il}:{include_global}:{include_podcasts}:{include_sec}:{limit}"
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

    # 5. Fetch news per topic (parallel) — yfinance + Finnhub
    news_map: dict[str, list] = {}
    finnhub = FinnhubCollector()
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        for topic in topics:
            top_tickers = [s["ticker"] for s in stocks_map.get(topic["slug"], [])[:2]]
            for ticker in top_tickers:
                futures[executor.submit(_get_yfinance_news_for_topic, ticker, topic["slug"])] = topic["slug"]
                # Also fetch Finnhub company news
                if finnhub.api_key:
                    futures[executor.submit(finnhub.get_company_news, ticker, 3, 5)] = topic["slug"]

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
            title = item.get("title", "")
            if title and title not in seen:
                seen.add(title)
                unique.append(item)
        news_map[slug] = unique[:5]  # Top 5 articles per topic (more sources now)

    # 6. Israeli news (optional)
    il_news_items = []
    if include_il:
        try:
            il_news_items = get_israeli_news(limit=30)
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

    # 7. Global financial news (Economist, FT, Seeking Alpha, etc.)
    global_news_items = []
    global_news_by_topic: dict[str, list] = {}
    global_news_general: list = []
    if include_global:
        try:
            global_news_items = get_global_news(limit=30)
            keyword_map = _get_topic_keywords_map()
            global_news_items = match_global_news_to_topics(global_news_items, keyword_map)
        except Exception as e:
            print(f"Global news fetch error: {e}")

    for item in global_news_items:
        topic_slug = item.get("related_topic")
        if topic_slug:
            if topic_slug not in global_news_by_topic:
                global_news_by_topic[topic_slug] = []
            global_news_by_topic[topic_slug].append(item)
        else:
            global_news_general.append(item)

    # 8. SEC filings (optional)
    sec_by_topic: dict[str, list] = {}
    sec_general: list = []
    if include_sec:
        try:
            sec_general = get_latest_filings(filing_types=["10-K", "10-Q", "8-K"], limit=10)
        except Exception as e:
            print(f"SEC filings fetch error: {e}")

        # Fetch SEC filings for top tickers per topic
        with ThreadPoolExecutor(max_workers=6) as executor:
            sec_futures = {}
            for topic in topics:
                top_tickers = [s["ticker"] for s in stocks_map.get(topic["slug"], [])[:2]]
                for ticker in top_tickers:
                    sec_futures[executor.submit(get_company_filings, ticker, "", 3)] = topic["slug"]

            for future in as_completed(sec_futures):
                slug = sec_futures[future]
                try:
                    filings = future.result()
                    if filings:
                        if slug not in sec_by_topic:
                            sec_by_topic[slug] = []
                        sec_by_topic[slug].extend(filings[:2])
                except Exception:
                    pass

    # 9. Podcast episodes (optional)
    podcast_items = []
    if include_podcasts:
        try:
            podcast_items = get_podcast_episodes(limit=15)
        except Exception as e:
            print(f"Podcast fetch error: {e}")

    # 10. Build the unified feed
    feed = []
    for topic in topics:
        slug = topic["slug"]

        # Combine all news sources for this topic
        topic_news = news_map.get(slug, [])
        topic_il_news = il_news_by_topic.get(slug, [])
        topic_global_news = global_news_by_topic.get(slug, [])
        topic_sec = sec_by_topic.get(slug, [])

        # Pick the best article (prefer one with an image)
        all_articles = topic_news + topic_global_news + topic_il_news
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
            "articles": all_articles[:7],
            "il_news": topic_il_news[:3],
            "global_news": topic_global_news[:3],
            "sec_filings": topic_sec[:3],
        }
        feed.append(feed_item)

    result = {
        "feed": feed,
        "il_news_general": il_news_general[:10],
        "global_news_general": global_news_general[:10],
        "sec_filings_latest": sec_general[:5],
        "podcasts": podcast_items[:8],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    _feed_cache[cache_key] = {"time": now, "data": result}
    return result


@router.get("/il-news")
async def get_il_news_feed(
    source: Optional[str] = Query(None, description="Source key: globes, calcalist, geektime, themarker, bizportal, ice, ynet_calcala, tase"),
    limit: int = Query(30, le=50),
):
    """Get Israeli financial news from RSS feeds."""
    from ..services.israeli_news import ISRAELI_FEEDS
    items = get_israeli_news(source=source, limit=limit)
    return {"items": items, "sources": list(ISRAELI_FEEDS.keys())}


@router.get("/global-news")
async def get_global_news_feed(
    source: Optional[str] = Query(None, description="Source key: economist, ft, seeking_alpha, benzinga, reuters, cnbc"),
    limit: int = Query(30, le=50),
):
    """Get global financial news from major publications."""
    from ..services.global_rss import GLOBAL_FEEDS
    items = get_global_news(source=source, limit=limit)
    return {"items": items, "sources": list(GLOBAL_FEEDS.keys())}


@router.get("/sec-filings")
async def get_sec_filings_feed(
    ticker: Optional[str] = Query(None, description="Filter by stock ticker"),
    filing_type: Optional[str] = Query(None, description="Filing type: 10-K, 10-Q, 8-K, S-1"),
    limit: int = Query(20, le=50),
):
    """Get SEC EDGAR filings."""
    if ticker:
        items = get_company_filings(ticker, filing_type or "", limit)
    else:
        types = [filing_type] if filing_type else ["10-K", "10-Q", "8-K"]
        items = get_latest_filings(filing_types=types, limit=limit)
    return {"items": items}


@router.get("/macro")
async def get_macro_dashboard(
    series: Optional[str] = Query(None, description="Specific FRED series ID (e.g. GDP, FEDFUNDS, VIXCLS)"),
):
    """Get macroeconomic indicators from FRED (Federal Reserve)."""
    fred = FredCollector()
    if not fred.api_key:
        raise HTTPException(status_code=503, detail="FRED_API_KEY not configured")

    if series:
        data = fred.get_series_latest(series.upper(), count=10)
        if not data:
            raise HTTPException(status_code=404, detail=f"Series {series} not found")
        return data

    return {"indicators": fred.get_macro_dashboard()}


@router.get("/sentiment")
async def get_sentiment(
    ticker: Optional[str] = Query(None, description="Stock ticker for sentiment"),
    topic: Optional[str] = Query(None, description="Topic slug for aggregated sentiment"),
):
    """Get news sentiment analysis from Finnhub and Alpha Vantage."""
    finnhub = FinnhubCollector()
    results = {}

    if ticker:
        if finnhub.api_key:
            results["finnhub"] = finnhub.get_news_sentiment(ticker.upper())

        try:
            from ..services.alpha_vantage import AlphaVantageCollector
            av = AlphaVantageCollector()
            av_articles = av.get_news_sentiment(tickers=[ticker.upper()], limit=10)
            if av_articles:
                scores = [a["sentiment_score"] for a in av_articles if a.get("sentiment_score")]
                results["alpha_vantage"] = {
                    "articles": av_articles[:5],
                    "avg_sentiment": round(sum(scores) / len(scores), 3) if scores else 0,
                    "article_count": len(av_articles),
                }
        except Exception as e:
            print(f"Alpha Vantage sentiment error: {e}")

    if not ticker and not topic:
        raise HTTPException(status_code=400, detail="Provide ticker or topic parameter")

    return results


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


@router.get("/il-institutional")
async def get_il_institutional_feed(
    source: Optional[str] = Query(None, description="Source: boi, cbs, isa, tase_institutional, aaron_institute, taub_center, sp_maalot"),
    category: Optional[str] = Query(None, description="Category: monetary, macro, regulation, market, research, ratings"),
    limit: int = Query(30, le=50),
):
    """Get Israeli institutional data (Bank of Israel, CBS, ISA, etc.)."""
    from ..services.israeli_institutional import INSTITUTIONAL_FEEDS
    items = get_institutional_data(source=source, category=category, limit=limit)
    return {"items": items, "sources": list(INSTITUTIONAL_FEEDS.keys())}


@router.get("/us-gov")
async def get_us_gov_feed(
    source: Optional[str] = Query(None, description="Source: bea, bls, nber, treasury"),
    category: Optional[str] = Query(None, description="Category: macro, employment, research, fiscal"),
    limit: int = Query(30, le=50),
):
    """Get US government economic data (BEA, BLS, NBER, Treasury)."""
    from ..services.us_government import US_GOV_FEEDS
    items = get_us_gov_data(source=source, category=category, limit=limit)
    return {"items": items, "sources": list(US_GOV_FEEDS.keys())}


@router.get("/international")
async def get_international_feed(
    source: Optional[str] = Query(None, description="Source: ecb, eurostat, boe, oecd, boj, pboc, nikkei_asia, etc."),
    region: Optional[str] = Query(None, description="Region: europe, asia, international"),
    category: Optional[str] = Query(None, description="Category: monetary, macro, research, development, news"),
    limit: int = Query(30, le=50),
):
    """Get international institutional data (ECB, BOJ, OECD, IMF, etc.)."""
    from ..services.international_institutional import INTL_INSTITUTIONAL_FEEDS
    items = get_international_data(source=source, region=region, category=category, limit=limit)
    return {"items": items, "sources": list(INTL_INSTITUTIONAL_FEEDS.keys())}


@router.get("/blogs")
async def get_blogs_feed(
    blog: Optional[str] = Query(None, description="Blog key: calculated_risk, marginal_revolution, money_stuff, etc."),
    category: Optional[str] = Query(None, description="Category: macro, markets, energy, personal_finance"),
    language: Optional[str] = Query(None, description="Language: en, he"),
    limit: int = Query(30, le=50),
):
    """Get latest posts from financial blogs and newsletters."""
    from ..services.blogs import BLOG_FEEDS
    items = get_blog_posts(blog=blog, category=category, language=language, limit=limit)
    return {"items": items, "sources": list(BLOG_FEEDS.keys())}


@router.get("/sources")
async def get_all_sources():
    """List all available data sources and their status."""
    from ..services.israeli_news import ISRAELI_FEEDS
    from ..services.global_rss import GLOBAL_FEEDS
    from ..services.podcasts import PODCAST_FEEDS
    from ..services.israeli_institutional import INSTITUTIONAL_FEEDS
    from ..services.us_government import US_GOV_FEEDS
    from ..services.international_institutional import INTL_INSTITUTIONAL_FEEDS
    from ..services.blogs import BLOG_FEEDS
    from ..services.reddit import SUBREDDIT_CATEGORIES, ALL_SUBREDDITS

    finnhub = FinnhubCollector()
    from ..services.alpha_vantage import AlphaVantageCollector
    av = AlphaVantageCollector()
    fred = FredCollector()

    return {
        "israeli_news": {"count": len(ISRAELI_FEEDS), "sources": list(ISRAELI_FEEDS.keys())},
        "global_news": {"count": len(GLOBAL_FEEDS), "sources": list(GLOBAL_FEEDS.keys())},
        "podcasts": {"count": len(PODCAST_FEEDS), "sources": list(PODCAST_FEEDS.keys())},
        "blogs": {"count": len(BLOG_FEEDS), "sources": list(BLOG_FEEDS.keys())},
        "israeli_institutional": {"count": len(INSTITUTIONAL_FEEDS), "sources": list(INSTITUTIONAL_FEEDS.keys())},
        "us_government": {"count": len(US_GOV_FEEDS), "sources": list(US_GOV_FEEDS.keys())},
        "international": {"count": len(INTL_INSTITUTIONAL_FEEDS), "sources": list(INTL_INSTITUTIONAL_FEEDS.keys())},
        "reddit": {"subreddit_count": len(ALL_SUBREDDITS), "categories": list(SUBREDDIT_CATEGORIES.keys())},
        "api_services": {
            "finnhub": {"configured": bool(finnhub.api_key)},
            "alpha_vantage": {"configured": bool(av.api_key)},
            "fred": {"configured": bool(fred.api_key)},
            "sec_edgar": {"configured": True, "note": "No API key needed"},
            "newsapi": {"configured": bool(os.getenv("NEWS_API_KEY", ""))},
            "x_twitter": {"configured": bool(os.getenv("X_BEARER_TOKEN", ""))},
            "reddit": {"configured": bool(os.getenv("REDDIT_CLIENT_ID", ""))},
        },
    }
