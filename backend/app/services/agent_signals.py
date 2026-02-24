"""
Signal extraction engine for TrendVest AI Agent — v2.

v2 additions over v1:
  - NLP sentiment (agent_nlp.py) as primary + Alpha Vantage as premium
  - Timing signal: user clicks *before* vs *after* price move
  - Finnhub sentiment integration
  - Earnings blackout detection
  - Signal age / decay metadata (consumed by agent_brain)

Gathers signals from 8 sources and normalizes them:
    direction: bullish | bearish | neutral
    strength:  0.0 → 1.0
    created_at: ISO timestamp (for decay calculation in brain)
"""

from __future__ import annotations

import logging
import math
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
        strength = min(0.9, score / 300)
    elif row["direction"] == "falling":
        direction = "bearish"
        strength = min(0.9, (100 - score) / 100)
    else:
        direction = "neutral"
        strength = 0.2

    return _make_signal("momentum", direction, strength, {
        "score": score,
        "direction": row["direction"],
        "mentions_today": row["mention_count_today"],
        "avg_7d": row["mention_avg_7d"],
    })


# ── 2. Sentiment Signal (upgraded: NLP primary + Alpha Vantage premium) ──

def extract_sentiment_signal(
    alpha_vantage_collector,
    tickers: list[str],
    topic_slug: str,
    finnhub_collector=None,
    news_texts: Optional[list[str]] = None,
) -> Optional[dict]:
    """
    Multi-source sentiment fusion:
    1. Alpha Vantage (best quality, limited to ~23 calls/day)
    2. Finnhub news sentiment (per-ticker, good quality)
    3. NLP on provided news/blog texts (unlimited, lower quality)

    Falls through gracefully: if AV is exhausted, uses Finnhub.
    If Finnhub unavailable, uses NLP. If no text, returns None.
    """
    from .agent_nlp import analyze_texts_batch

    sources_used = []
    scores = []

    # Source 1: Alpha Vantage (premium)
    try:
        av_sentiment = alpha_vantage_collector.get_topic_sentiment(
            topic_slug=topic_slug, av_topics=[], tickers=tickers[:3],
        )
        if av_sentiment and av_sentiment.get("article_count", 0) > 0:
            scores.append(av_sentiment["avg_sentiment"])
            sources_used.append("alpha_vantage")
    except Exception as e:
        logger.debug("Alpha Vantage sentiment unavailable: %s", e)

    # Source 2: Finnhub (per-ticker sentiment)
    if finnhub_collector and tickers:
        try:
            for ticker in tickers[:2]:
                fh = finnhub_collector.get_news_sentiment(ticker)
                if fh and fh.get("sentiment"):
                    # Finnhub returns {bullishPercent, bearishPercent}
                    bullish_pct = fh["sentiment"].get("bullishPercent", 0.5)
                    # Convert to -1..+1 scale
                    fh_score = (bullish_pct - 0.5) * 2
                    scores.append(fh_score)
                    sources_used.append("finnhub")
        except Exception as e:
            logger.debug("Finnhub sentiment failed: %s", e)

    # Source 3: NLP on raw text (always available)
    if news_texts:
        nlp_result = analyze_texts_batch(news_texts)
        if nlp_result["count"] > 0:
            scores.append(nlp_result["avg_score"])
            sources_used.append(f"nlp({nlp_result['count']} texts)")

    if not scores:
        return None

    # Weight: AV and Finnhub count more than NLP
    # Simple average for now; AV naturally contributes more accuracy
    avg_score = sum(scores) / len(scores)

    if avg_score > 0.15:
        direction = "bullish"
        strength = min(0.9, abs(avg_score) * 2)
    elif avg_score < -0.15:
        direction = "bearish"
        strength = min(0.9, abs(avg_score) * 2)
    else:
        direction = "neutral"
        strength = 0.2

    return _make_signal("sentiment", direction, strength, {
        "avg_score": round(avg_score, 3),
        "sources": sources_used,
        "source_count": len(sources_used),
        "individual_scores": [round(s, 3) for s in scores],
    })


# ── 3. User Herd Signal (upgraded: timing analysis) ──

async def extract_user_herd_signal(pool, topic_slug: str, stock_service=None) -> Optional[dict]:
    """
    User behavior signal with timing analysis.

    NEW: Compares when users clicked vs when prices moved.
    If users clicked BEFORE the price rose → strong leading signal.
    If users clicked AFTER → lagging (FOMO), weaker signal.
    """
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    async with pool.acquire() as conn:
        count_24h = await conn.fetchval("""
            SELECT COUNT(*) FROM user_interactions
            WHERE target_slug = $1 AND created_at >= $2
        """, topic_slug, day_ago) or 0

        count_7d = await conn.fetchval("""
            SELECT COUNT(*) FROM user_interactions
            WHERE target_slug = $1 AND created_at >= $2
        """, topic_slug, week_ago) or 0

        high_intent_24h = await conn.fetchval("""
            SELECT COUNT(*) FROM user_interactions
            WHERE target_slug = $1
              AND created_at >= $2
              AND interaction_type IN ('watchlist_add', 'stock_click', 'chat_ask')
        """, topic_slug, day_ago) or 0

        # NEW: Timing — get the top ticker for this topic
        top_ticker = await conn.fetchval("""
            SELECT ts.ticker FROM topic_stocks ts
            JOIN topics t ON t.id = ts.topic_id
            WHERE t.slug = $1
            ORDER BY ts.priority ASC LIMIT 1
        """, topic_slug)

    daily_avg_7d = count_7d / 7 if count_7d > 0 else 0

    if count_7d < 5:
        return None

    if daily_avg_7d > 0:
        spike_ratio = count_24h / daily_avg_7d
    elif count_24h > 0:
        spike_ratio = 3.0
    else:
        spike_ratio = 0

    intent_boost = min(0.2, high_intent_24h * 0.05)

    # NEW: Timing analysis — did user activity lead or lag price?
    timing_factor = 1.0  # Default: neutral timing
    timing_label = "unknown"
    if top_ticker and stock_service and spike_ratio > 1.5:
        try:
            from .agent_technical import get_technical_signals
            tech = get_technical_signals(top_ticker)
            if tech:
                # If price rose in last 5 days AND users are clicking now
                # → likely lagging (FOMO). Dampen.
                if tech["change_5d"] > 5:
                    timing_factor = 0.6  # Already rose a lot → FOMO
                    timing_label = "lagging_fomo"
                elif tech["change_5d"] < -2 and spike_ratio > 2:
                    # Price dropped but users are clicking → contrarian interest
                    timing_factor = 1.3
                    timing_label = "leading_contrarian"
                elif -2 <= tech["change_5d"] <= 2 and spike_ratio > 2:
                    # Price flat but users are surging → potential leading signal
                    timing_factor = 1.2
                    timing_label = "leading_flat"
                else:
                    timing_label = "neutral"
        except Exception:
            pass

    if spike_ratio > 2.0:
        direction = "bullish"
        raw_strength = 0.3 + (spike_ratio - 2) * 0.1 + intent_boost
        strength = min(0.7, raw_strength * timing_factor)
    elif spike_ratio < 0.3 and count_24h < 2:
        direction = "bearish"
        strength = 0.3
    else:
        direction = "neutral"
        strength = 0.15

    return _make_signal("user_herd", direction, strength, {
        "interactions_24h": count_24h,
        "interactions_7d": count_7d,
        "daily_avg_7d": round(daily_avg_7d, 1),
        "spike_ratio": round(spike_ratio, 2),
        "high_intent_24h": high_intent_24h,
        "timing_factor": round(timing_factor, 2),
        "timing_label": timing_label,
    })


# ── 4. Technical Signal ──

def extract_technical_signal(ticker: str) -> Optional[dict]:
    """
    RSI, SMA crossover, volume ratio — pure math on price data.
    """
    from .agent_technical import get_technical_signals

    tech = get_technical_signals(ticker)
    if not tech:
        return None

    return _make_signal("technical", tech["direction"], tech["strength"], {
        "rsi": tech["rsi"],
        "sma_20": tech["sma_20"],
        "sma_50": tech["sma_50"],
        "price": tech["price"],
        "price_vs_sma20_pct": tech.get("price_vs_sma20_pct"),
        "change_5d": tech["change_5d"],
        "change_20d": tech["change_20d"],
        "volume_ratio": tech["volume_ratio"],
        "score": tech["score"],
    })


# ── 5. Macro Signal ──

def extract_macro_signal(fred_collector) -> Optional[dict]:
    """
    VIX + Fed rate → market regime.
    Macro signals don't predict daily moves; they set the backdrop.
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

    if vix_change > 3:
        if direction != "bearish":
            direction = "bearish"
        strength = min(0.9, strength + 0.2)

    result = _make_signal("macro", direction, strength, {
        "vix": vix,
        "vix_change": round(vix_change, 2),
        "fed_rate": fed_rate,
        "regime": regime,
    })
    return result


# ── 6. Cross-Reference Signal ──

def extract_cross_reference_signal(topic_slug: str, cross_ref_data: Optional[dict]) -> Optional[dict]:
    """If a topic appears in multi-source trending → bullish confirmation."""
    if not cross_ref_data:
        return None

    trending_topics = cross_ref_data.get("topics", [])
    match = None
    for t in trending_topics:
        topic_name = t.get("topic", "").lower().replace(" ", "_")
        if topic_slug in topic_name or topic_name in topic_slug:
            match = t
            break

    if not match:
        return _make_signal("cross_reference", "neutral", 0.1, {"found_in_trending": False})

    source_count = match.get("source_count", 1)
    if source_count >= 4:
        direction = "bullish"
        strength = min(0.7, 0.3 + source_count * 0.08)
    elif source_count >= 2:
        direction = "bullish"
        strength = 0.3
    else:
        direction = "neutral"
        strength = 0.15

    return _make_signal("cross_reference", direction, strength, {
        "found_in_trending": True,
        "source_count": source_count,
        "mention_count": match.get("mention_count", 0),
    })


# ── 7. Earnings Blackout Detection ──

def detect_earnings_blackout(ticker: str) -> Optional[dict]:
    """
    Check if a ticker has earnings within ±3 days.
    If so, return a warning signal that dampens confidence.

    Uses yfinance calendar data. Not always available.
    """
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        cal = stock.calendar
        if cal is None or cal.empty:
            return None

        now = datetime.now(timezone.utc)
        earnings_date = None

        # calendar can be a dict or DataFrame depending on yfinance version
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            if ed:
                earnings_date = ed[0] if isinstance(ed, list) else ed
        else:
            if "Earnings Date" in cal.index:
                vals = cal.loc["Earnings Date"]
                if hasattr(vals, "iloc") and len(vals) > 0:
                    earnings_date = vals.iloc[0]

        if earnings_date is None:
            return None

        # Make timezone-aware if needed
        if hasattr(earnings_date, "tzinfo") and earnings_date.tzinfo is None:
            from datetime import timezone as tz
            earnings_date = earnings_date.replace(tzinfo=tz.utc)
        elif isinstance(earnings_date, str):
            from datetime import datetime as dt
            earnings_date = dt.fromisoformat(earnings_date).replace(tzinfo=timezone.utc)

        days_until = (earnings_date - now).days

        if -2 <= days_until <= 3:
            return {
                "is_blackout": True,
                "days_until_earnings": days_until,
                "earnings_date": str(earnings_date.date()) if hasattr(earnings_date, "date") else str(earnings_date),
                "reason": f"Earnings in {days_until}d — high volatility risk",
            }

        return None

    except Exception as e:
        logger.debug("Earnings check failed for %s: %s", ticker, e)
        return None


# ── 8. NLP Sentiment on Raw Texts ──

def extract_nlp_sentiment_signal(texts: list[str], source_label: str = "mixed") -> Optional[dict]:
    """
    Run NLP sentiment on a list of texts (headlines, descriptions, etc.).
    Can be used standalone for Reddit titles, blog headlines, etc.
    """
    if not texts:
        return None

    from .agent_nlp import analyze_texts_batch
    result = analyze_texts_batch(texts)

    if result["count"] == 0:
        return None

    avg = result["avg_score"]
    if avg > 0.1:
        direction = "bullish"
        strength = min(0.7, abs(avg) * 1.5)
    elif avg < -0.1:
        direction = "bearish"
        strength = min(0.7, abs(avg) * 1.5)
    else:
        direction = "neutral"
        strength = 0.15

    # NLP is capped at 0.7 — it's less reliable than API sentiment
    return _make_signal("sentiment", direction, strength, {
        "avg_score": result["avg_score"],
        "source": f"nlp_{source_label}",
        "sources": [f"nlp_{source_label}"],
        "source_count": 1,
        "count": result["count"],
        "bullish_count": result["bullish_count"],
        "bearish_count": result["bearish_count"],
        "neutral_count": result["neutral_count"],
    })


# ── Signal Decay ──

def apply_signal_decay(signal: dict, half_life_hours: float = 48.0) -> dict:
    """
    Apply exponential time decay to a signal's strength.

    A signal from 48 hours ago has half the strength of a fresh one.
    A signal from 96 hours ago has 25% strength.

    Formula: decayed_strength = strength * exp(-age_hours * ln(2) / half_life)
    """
    created = signal.get("created_at")
    if not created:
        return signal

    try:
        if isinstance(created, str):
            created_dt = datetime.fromisoformat(created)
        else:
            created_dt = created
        age_hours = (datetime.now(timezone.utc) - created_dt).total_seconds() / 3600
    except (ValueError, TypeError):
        return signal

    if age_hours <= 0:
        return signal

    decay_factor = math.exp(-age_hours * math.log(2) / half_life_hours)
    signal["strength"] = round(signal["strength"] * decay_factor, 3)
    signal["_decay_factor"] = round(decay_factor, 3)
    signal["_age_hours"] = round(age_hours, 1)

    return signal


# ── Helpers ──

def _make_signal(signal_type: str, direction: str, strength: float, raw_data: dict) -> dict:
    """Create a standardized signal dict with timestamp."""
    return {
        "signal_type": signal_type,
        "direction": direction,
        "strength": round(min(strength, 0.95), 3),
        "raw_data": raw_data,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
