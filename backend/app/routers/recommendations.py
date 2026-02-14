"""
User tracking and recommendations router for TrendVest.
"""
import json
from fastapi import APIRouter, Depends, Query
from typing import Optional
from ..models.schemas import TrackRequest
from ..deps import get_db_pool

router = APIRouter(prefix="/api", tags=["recommendations"])

# Scoring weights
SCORE_WEIGHTS = {
    "topic_view": 1.0,
    "stock_click": 2.0,
    "watchlist_add": 3.0,
    "news_click": 1.5,
    "chat_ask": 2.0,
    "search": 0.5,
}


@router.post("/track")
async def track_interaction(
    body: TrackRequest,
    session_id: Optional[str] = Query(None),
    pool=Depends(get_db_pool),
):
    """Log a user interaction (fire-and-forget from frontend)."""
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO user_interactions (session_id, interaction_type, target_slug, metadata)
            VALUES ($1, $2, $3, $4)
        """, session_id, body.interaction_type,
           body.target_slug,
           json.dumps(body.metadata) if body.metadata else None)

        # Update interest score if there's a target slug
        if body.target_slug and session_id:
            weight = SCORE_WEIGHTS.get(body.interaction_type, 1.0)
            # We use session_id as a pseudo-user for anonymous users
            # In a real app, this would be user_id from JWT
            # For now, just log it
    return {"status": "tracked"}


@router.get("/recommendations")
async def get_recommendations(
    session_id: Optional[str] = Query(None),
    limit: int = Query(5, le=20),
    pool=Depends(get_db_pool),
):
    """Get personalized topic recommendations based on user interactions."""
    if not session_id:
        # Return default popular topics
        async with pool.acquire() as conn:
            topics = await conn.fetch("""
                SELECT t.slug, t.name_en, t.name_he, t.sector_en,
                       COALESCE(m.score, 0) as momentum_score,
                       COALESCE(m.direction, 'stable') as direction
                FROM topics t
                LEFT JOIN momentum_scores m ON t.id = m.topic_id
                WHERE t.is_active = true
                ORDER BY COALESCE(m.score, 0) DESC
                LIMIT $1
            """, limit)
        return [dict(t) for t in topics]

    async with pool.acquire() as conn:
        # Get user's most interacted-with topics
        interactions = await conn.fetch("""
            SELECT target_slug, interaction_type, COUNT(*) as cnt
            FROM user_interactions
            WHERE session_id = $1 AND target_slug IS NOT NULL
            GROUP BY target_slug, interaction_type
        """, session_id)

        # Calculate scores
        scores: dict[str, float] = {}
        for row in interactions:
            slug = row["target_slug"]
            weight = SCORE_WEIGHTS.get(row["interaction_type"], 1.0)
            scores[slug] = scores.get(slug, 0) + weight * row["cnt"]

        if not scores:
            # Fallback to popular topics
            topics = await conn.fetch("""
                SELECT t.slug, t.name_en, t.name_he, t.sector_en,
                       COALESCE(m.score, 0) as momentum_score,
                       COALESCE(m.direction, 'stable') as direction
                FROM topics t
                LEFT JOIN momentum_scores m ON t.id = m.topic_id
                WHERE t.is_active = true
                ORDER BY COALESCE(m.score, 0) DESC
                LIMIT $1
            """, limit)
            return [dict(t) for t in topics]

        # Sort by interest score and get topic details
        sorted_slugs = sorted(scores.keys(), key=lambda s: scores[s], reverse=True)[:limit]

        topics = await conn.fetch("""
            SELECT t.slug, t.name_en, t.name_he, t.sector_en,
                   COALESCE(m.score, 0) as momentum_score,
                   COALESCE(m.direction, 'stable') as direction
            FROM topics t
            LEFT JOIN momentum_scores m ON t.id = m.topic_id
            WHERE t.slug = ANY($1) AND t.is_active = true
        """, sorted_slugs)

        # Preserve score order
        topic_map = {t["slug"]: dict(t) for t in topics}
        result = []
        for slug in sorted_slugs:
            if slug in topic_map:
                t = topic_map[slug]
                t["interest_score"] = round(scores[slug], 1)
                result.append(t)

        return result
