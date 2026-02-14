"""
Trends API endpoints for TrendVest.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from ..models.schemas import TrendTopic, TopicStock
from ..deps import get_db_pool, get_stock_service
from ..services.topic_insights import get_topic_insight, get_all_insights, generate_ai_insight

router = APIRouter(prefix="/api/trends", tags=["trends"])


@router.get("", response_model=list[TrendTopic])
async def get_trends(
    sector: Optional[str] = Query(None, description="Filter by sector"),
    limit: int = Query(20, le=50),
    pool=Depends(get_db_pool),
    stock_service=Depends(get_stock_service),
):
    """Get all topics sorted by momentum score."""
    async with pool.acquire() as conn:
        query = """
            SELECT t.slug, t.name_en, t.name_he, t.sector, t.sector_en,
                   COALESCE(m.score, 0) as momentum_score,
                   COALESCE(m.direction, 'stable') as direction,
                   COALESCE(m.mention_count_today, 0) as mention_count_today,
                   COALESCE(m.mention_avg_7d, 0) as mention_avg_7d
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

        results = []
        all_stocks_raw = []
        for topic in topics:
            stocks = await conn.fetch("""
                SELECT ticker, company_name, relevance_note
                FROM topic_stocks ts
                JOIN topics t ON ts.topic_id = t.id
                WHERE t.slug = $1
                ORDER BY ts.priority
            """, topic["slug"])

            stock_list = [
                TopicStock(
                    ticker=s["ticker"],
                    company_name=s["company_name"],
                    relevance_note=s["relevance_note"] or "",
                )
                for s in stocks
            ]
            all_stocks_raw.extend(stock_list)

            results.append(TrendTopic(
                slug=topic["slug"],
                name_en=topic["name_en"],
                name_he=topic["name_he"],
                sector=topic["sector"],
                sector_en=topic["sector_en"],
                momentum_score=topic["momentum_score"],
                direction=topic["direction"],
                mention_count_today=topic["mention_count_today"],
                mention_avg_7d=topic["mention_avg_7d"],
                stocks=stock_list,
            ))

        # Fetch prices for all tickers in one batch
        all_tickers = list(set(s.ticker for s in all_stocks_raw))
        if all_tickers:
            prices = stock_service.get_prices_batch(all_tickers)
            for topic_result in results:
                for stock in topic_result.stocks:
                    price_data = prices.get(stock.ticker)
                    if price_data:
                        stock.current_price = price_data.price
                        stock.daily_change_pct = price_data.change_pct
                        stock.previous_close = price_data.previous_close

        return results


@router.get("/{slug}", response_model=TrendTopic)
async def get_trend_by_slug(
    slug: str,
    pool=Depends(get_db_pool),
    stock_service=Depends(get_stock_service),
):
    """Get a single topic by slug with full details."""
    async with pool.acquire() as conn:
        topic = await conn.fetchrow("""
            SELECT t.slug, t.name_en, t.name_he, t.sector, t.sector_en,
                   COALESCE(m.score, 0) as momentum_score,
                   COALESCE(m.direction, 'stable') as direction,
                   COALESCE(m.mention_count_today, 0) as mention_count_today,
                   COALESCE(m.mention_avg_7d, 0) as mention_avg_7d
            FROM topics t
            LEFT JOIN momentum_scores m ON t.id = m.topic_id
            WHERE t.slug = $1 AND t.is_active = true
        """, slug)

        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")

        stocks = await conn.fetch("""
            SELECT ticker, company_name, relevance_note
            FROM topic_stocks ts
            JOIN topics t ON ts.topic_id = t.id
            WHERE t.slug = $1
            ORDER BY ts.priority
        """, slug)

        stock_list = [TopicStock(
            ticker=s["ticker"],
            company_name=s["company_name"],
            relevance_note=s["relevance_note"] or "",
        ) for s in stocks]

        # Fetch prices
        tickers = [s.ticker for s in stock_list]
        if tickers:
            prices = stock_service.get_prices_batch(tickers)
            for stock in stock_list:
                price_data = prices.get(stock.ticker)
                if price_data:
                    stock.current_price = price_data.price
                    stock.daily_change_pct = price_data.change_pct
                    stock.previous_close = price_data.previous_close

        return TrendTopic(
            slug=topic["slug"],
            name_en=topic["name_en"],
            name_he=topic["name_he"],
            sector=topic["sector"],
            sector_en=topic["sector_en"],
            momentum_score=topic["momentum_score"],
            direction=topic["direction"],
            mention_count_today=topic["mention_count_today"],
            mention_avg_7d=topic["mention_avg_7d"],
            stocks=stock_list,
        )


@router.get("/{slug}/insight")
async def get_trend_insight(
    slug: str,
    language: str = Query("en", description="Language: en or he"),
    pool=Depends(get_db_pool),
):
    """Get AI-powered insight for a topic: why it's trending and stock connections."""
    # First try to generate a fresh AI insight if API key is available
    async with pool.acquire() as conn:
        topic = await conn.fetchrow(
            "SELECT name_en FROM topics WHERE slug = $1 AND is_active = true", slug
        )
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")

        stocks = await conn.fetch("""
            SELECT ticker, company_name FROM topic_stocks ts
            JOIN topics t ON ts.topic_id = t.id
            WHERE t.slug = $1 ORDER BY ts.priority LIMIT 5
        """, slug)

        momentum = await conn.fetchrow(
            "SELECT score FROM momentum_scores ms JOIN topics t ON ms.topic_id = t.id WHERE t.slug = $1",
            slug,
        )

    # Try AI generation first
    ai_result = await generate_ai_insight(
        slug=slug,
        topic_name=topic["name_en"],
        stocks=[dict(s) for s in stocks],
        language=language,
        momentum_score=momentum["score"] if momentum else 0,
    )
    if ai_result:
        return ai_result

    # Fall back to curated insights
    curated = get_topic_insight(slug, language)
    if curated:
        return curated

    # No insight available
    return {
        "slug": slug,
        "why_trending": "No insight available for this topic yet." if language == "en" else "אין מידע זמין על נושא זה עדיין.",
        "stock_connections": {},
    }


@router.get("/{slug}/stock-insight/{ticker}")
async def get_stock_insight(
    slug: str,
    ticker: str,
    language: str = Query("en", description="Language: en or he"),
):
    """Get insight about how a specific stock connects to a trending topic."""
    curated = get_topic_insight(slug, language)
    if curated and ticker.upper() in curated.get("stock_connections", {}):
        return {
            "slug": slug,
            "ticker": ticker.upper(),
            "connection": curated["stock_connections"][ticker.upper()],
        }

    fallback = (
        f"No specific insight available for {ticker.upper()} in this trend."
        if language == "en"
        else f"אין מידע ספציפי על {ticker.upper()} בטרנד הזה."
    )
    return {
        "slug": slug,
        "ticker": ticker.upper(),
        "connection": fallback,
    }
