"""
Trends API endpoints for TrendVest.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from ..models.schemas import TrendTopic, TopicStock

router = APIRouter(prefix="/api/trends", tags=["trends"])


@router.get("", response_model=list[TrendTopic])
async def get_trends(
    sector: Optional[str] = Query(None, description="Filter by sector"),
    limit: int = Query(20, le=50),
    pool=Depends(),
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
        for topic in topics:
            # Get stocks for this topic
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

        return results


@router.get("/{slug}", response_model=TrendTopic)
async def get_trend_by_slug(slug: str, pool=Depends()):
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
            stocks=[TopicStock(
                ticker=s["ticker"],
                company_name=s["company_name"],
                relevance_note=s["relevance_note"] or "",
            ) for s in stocks],
        )
