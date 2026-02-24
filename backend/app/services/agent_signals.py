"""
Signal extraction engine for TrendVest AI Agent.

Gathers signals from 6 sources and normalizes them into a unified format:
    direction: bullish | bearish | neutral
    strength:  0.0 → 1.0

Honest note: These signals are noisy. No single signal reliably predicts
the market. The value comes from *combining* them and tracking which ones
actually work over time (see agent_brain.py for weight learning).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ── 1. Momentum Signal ──

async def extract_momentum_signal(pool, topic_slug: str) -> Optional[dict]:
    """
    Uses existing momentum_scores table.
    Rising momentum = bullish, falling = bearish.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT m.score, m.direction, m.mention_count_today, m.mention_avg_7d
            FROM momentum_scores m
            JOIN topics t ON t.id = m.topic_id
            WHERE t.slug = $1
        """, topic_slug)

    if not row:
        return None

    score = row["score"]
    if row["direction"] == "rising":
        direction = "bullish"
        strength = min(0.9, score / 300)  # 300+ = max strength
    elif row["direction"] == "falling":
        direction = "bearish"
        strength = min(0.9, (100 - score) / 100)
    else:
        direction = "neutral"
        strength = 0.2

    return {
        "signal_type": "momentum",
        "direction": direction,
        "strength": round(strength, 2),
        "raw_data": {
            "score": score,
            "direction": row["direction"],
            "mentions_today": row["mention_count_today"],
            "avg_7d": row["mention_avg_7d"],
        },
    }


# ── 2. Sentiment Signal ──

def extract_sentiment_signal(
    alpha_vantage_collector,
    tickers: list[str],
    topic_slug: str,
) -> Optional[dict]:
    """
    Uses Alpha Vantage sentiment API (the only real sentiment source we have).
    Returns aggregated sentiment for tickers related to a topic.

    Honest note: This is limited to ~23 API calls/day. For topics without
    Alpha Vantage data, we return None (no signal is better than fake signal).
    """
    try:
        sentiment = alpha_vantage_collector.get_topic_sentiment(
            topic_slug=topic_slug,
            av_topics=[],
            tickers=tickers[:3],
        )
    except Exception as e:
        logger.warning("Sentiment extraction failed: %s", e)
        return None

    if not sentiment:
        return None

    avg = sentiment["avg_sentiment"]
    if avg > 0.15:
        direction = "bullish"
        strength = min(0.9, avg * 2)  # 0.5 sentiment → 1.0 strength
    elif avg < -0.15:
        direction = "bearish"
        strength = min(0.9, abs(avg) * 2)
    else:
        direction = "neutral"
        strength = 0.2

    return {
        "signal_type": "sentiment",
        "direction": direction,
        "strength": round(strength, 2),
        "raw_data": sentiment,
    }


# ── 3. User Herd Signal ──

async def extract_user_herd_signal(pool, topic_slug: str) -> Optional[dict]:
    """
    Counts user interactions in the last 24h and 7d for a topic.
    A spike in user activity = potential signal.

    Honest note: On a small platform, this is noisy. With <100 DAU,
    one power user can skew this entirely. We dampen accordingly.
    """
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    async with pool.acquire() as conn:
        # Count interactions in last 24h
        count_24h = await conn.fetchval("""
            SELECT COUNT(*) FROM user_interactions
            WHERE target_slug = $1 AND created_at >= $2
        """, topic_slug, day_ago) or 0

        # Count in last 7 days (for baseline)
        count_7d = await conn.fetchval("""
            SELECT COUNT(*) FROM user_interactions
            WHERE target_slug = $1 AND created_at >= $2
        """, topic_slug, week_ago) or 0

        # Count high-intent actions (watchlist adds, stock clicks)
        high_intent_24h = await conn.fetchval("""
            SELECT COUNT(*) FROM user_interactions
            WHERE target_slug = $1
              AND created_at >= $2
              AND interaction_type IN ('watchlist_add', 'stock_click', 'chat_ask')
        """, topic_slug, day_ago) or 0

    daily_avg_7d = count_7d / 7 if count_7d > 0 else 0

    # Need minimum activity to consider this meaningful
    if count_7d < 5:
        return None  # Not enough data — don't guess

    # Calculate spike ratio
    if daily_avg_7d > 0:
        spike_ratio = count_24h / daily_avg_7d
    elif count_24h > 0:
        spike_ratio = 3.0  # New activity where there was none
    else:
        spike_ratio = 0

    # High-intent boost
    intent_boost = min(0.2, high_intent_24h * 0.05)

    if spike_ratio > 2.0:
        direction = "bullish"  # Users are suddenly very interested
        strength = min(0.7, 0.3 + (spike_ratio - 2) * 0.1 + intent_boost)
    elif spike_ratio < 0.3 and count_24h < 2:
        direction = "bearish"  # Users lost interest
        strength = 0.3
    else:
        direction = "neutral"
        strength = 0.15

    return {
        "signal_type": "user_herd",
        "direction": direction,
        "strength": round(strength, 2),
        "raw_data": {
            "interactions_24h": count_24h,
            "interactions_7d": count_7d,
            "daily_avg_7d": round(daily_avg_7d, 1),
            "spike_ratio": round(spike_ratio, 2),
            "high_intent_24h": high_intent_24h,
        },
    }


# ── 4. Technical Signal ──

def extract_technical_signal(ticker: str) -> Optional[dict]:
    """
    Wraps agent_technical.py — calculates RSI, SMA, etc.
    This is the most "honest" signal: pure math on price data.
    """
    from .agent_technical import get_technical_signals

    tech = get_technical_signals(ticker)
    if not tech:
        return None

    return {
        "signal_type": "technical",
        "direction": tech["direction"],
        "strength": tech["strength"],
        "raw_data": {
            "rsi": tech["rsi"],
            "sma_20": tech["sma_20"],
            "sma_50": tech["sma_50"],
            "price": tech["price"],
            "price_vs_sma20_pct": tech.get("price_vs_sma20_pct"),
            "change_5d": tech["change_5d"],
            "change_20d": tech["change_20d"],
            "volume_ratio": tech["volume_ratio"],
            "score": tech["score"],
        },
    }


# ── 5. Macro Signal ──

def extract_macro_signal(fred_collector) -> Optional[dict]:
    """
    Uses FRED data to determine macro regime.
    VIX high = fear → bearish. Fed cutting rates = generally bullish.

    Honest note: Macro signals are very slow-moving. They don't predict
    daily moves — they set the backdrop (bull/bear/volatile market).
    """
    try:
        vix_data = fred_collector.get_series_latest("VIXCLS", count=5)
        fed_data = fred_collector.get_series_latest("FEDFUNDS", count=5)
    except Exception as e:
        logger.warning("FRED data fetch failed: %s", e)
        return None

    if not vix_data:
        return None

    vix = vix_data["latest_value"]
    vix_change = vix_data.get("change", 0)
    fed_rate = fed_data["latest_value"] if fed_data else None

    # VIX-based regime
    if vix > 30:
        direction = "bearish"
        strength = min(0.8, 0.4 + (vix - 30) * 0.02)
        regime = "volatile"
    elif vix > 20:
        direction = "neutral"
        strength = 0.3
        regime = "normal"
    else:
        direction = "bullish"
        strength = min(0.6, 0.3 + (20 - vix) * 0.02)
        regime = "bull"

    # VIX spike in last reading = extra bearish
    if vix_change > 3:
        if direction != "bearish":
            direction = "bearish"
        strength = min(0.9, strength + 0.2)

    return {
        "signal_type": "macro",
        "direction": direction,
        "strength": round(strength, 2),
        "raw_data": {
            "vix": vix,
            "vix_change": round(vix_change, 2),
            "fed_rate": fed_rate,
            "regime": regime,
        },
    }


# ── 6. Cross-Reference Signal ──

def extract_cross_reference_signal(topic_slug: str, cross_ref_data: Optional[dict]) -> Optional[dict]:
    """
    Uses existing cross_reference.py trending topics.
    If a topic appears in cross-referenced trending → bullish signal.

    Honest note: This is basically "is the topic in the news from multiple
    sources?" — a weak but useful confirmation signal.
    """
    if not cross_ref_data:
        return None

    trending_topics = cross_ref_data.get("topics", [])

    # Check if our topic appears in trending
    match = None
    for t in trending_topics:
        topic_name = t.get("topic", "").lower().replace(" ", "_")
        if topic_slug in topic_name or topic_name in topic_slug:
            match = t
            break

    if not match:
        return {
            "signal_type": "cross_reference",
            "direction": "neutral",
            "strength": 0.1,
            "raw_data": {"found_in_trending": False},
        }

    source_count = match.get("source_count", 1)
    mention_count = match.get("mention_count", 0)

    if source_count >= 4:
        direction = "bullish"
        strength = min(0.7, 0.3 + source_count * 0.08)
    elif source_count >= 2:
        direction = "bullish"
        strength = 0.3
    else:
        direction = "neutral"
        strength = 0.15

    return {
        "signal_type": "cross_reference",
        "direction": direction,
        "strength": round(strength, 2),
        "raw_data": {
            "found_in_trending": True,
            "source_count": source_count,
            "mention_count": mention_count,
        },
    }
