"""
Breaking News Detector for TrendVest AI Agent.

Monitors news velocity across sources and triggers urgent scans
when abnormal activity is detected for a ticker or topic.

How it works:
  1. Collects recent headlines from yfinance, Finnhub, and NewsAPI
  2. Counts articles per ticker in the last 2 hours vs 24-hour baseline
  3. If 2h count > 3× the hourly average → "breaking" alert
  4. Returns a priority-sorted list of affected tickers for immediate scanning

This ensures the agent doesn't miss major events:
  - Earnings surprises
  - FDA approvals/rejections
  - M&A announcements
  - Regulatory actions
  - Market crashes / flash events
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ── Cache to avoid hammering APIs ──
_breaking_cache: dict[str, dict] = {}
CACHE_TTL = 300  # 5 minutes — breaking news needs freshness


# ── Breaking keywords that indicate high-impact events ──
URGENCY_KEYWORDS = [
    # English
    "breaking", "urgent", "flash", "just in", "alert",
    "surges", "plunges", "crashes", "soars", "plummets",
    "halted", "suspended", "bankruptcy", "default", "fraud",
    "FDA approval", "FDA reject", "acquisition", "merger",
    "dividend cut", "earnings miss", "earnings beat",
    "guidance cut", "downgrade", "upgrade", "recall",
    "indictment", "investigation", "sanctions", "tariff",
    "rate hike", "rate cut", "recession", "inflation",
    # Hebrew
    "דחוף", "חדשות חמות", "קריסה", "זינוק", "פשיטת רגל",
    "אישור FDA", "רכישה", "מיזוג", "דיבידנד",
]


def detect_breaking_news(
    watchlist_tickers: list[str],
    finnhub_collector=None,
) -> dict:
    """
    Scan for breaking news across a watchlist of tickers.

    Returns:
      {
        "has_breaking": bool,
        "alerts": [
          {
            "ticker": "NVDA",
            "headline": "...",
            "source": "yfinance",
            "velocity_ratio": 4.2,
            "urgency_score": 0.8,
            "published_at": "...",
          },
          ...
        ],
        "scanned_at": "...",
        "tickers_scanned": 10,
      }
    """
    cache_key = "breaking:" + ",".join(sorted(watchlist_tickers[:20]))
    now = time.time()
    if cache_key in _breaking_cache:
        cached = _breaking_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    alerts = []
    all_articles: list[dict] = []

    # ── Collect from yfinance (per ticker) ──
    for ticker in watchlist_tickers[:15]:  # Limit to avoid slowdowns
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            news = stock.news or []
            for item in news[:10]:
                content = item.get("content", {})
                title = content.get("title", "")
                pub_date = content.get("pubDate", "")
                if title:
                    all_articles.append({
                        "ticker": ticker,
                        "title": title,
                        "source": "yfinance",
                        "published_at": pub_date,
                    })
        except Exception:
            pass

    # ── Collect from Finnhub (market news) ──
    if finnhub_collector:
        try:
            market_news = finnhub_collector.get_market_news(limit=50)
            for item in market_news:
                title = item.get("headline", "") or item.get("title", "")
                summary = item.get("summary", "")
                pub_ts = item.get("datetime", 0)
                # Try to match to our watchlist tickers
                text_lower = (title + " " + summary).lower()
                for ticker in watchlist_tickers:
                    if ticker.lower() in text_lower:
                        all_articles.append({
                            "ticker": ticker,
                            "title": title,
                            "source": "finnhub",
                            "published_at": datetime.fromtimestamp(pub_ts, tz=timezone.utc).isoformat() if pub_ts else "",
                        })
                        break
        except Exception as e:
            logger.debug("Finnhub market news failed: %s", e)

    # ── Analyze velocity per ticker ──
    now_dt = datetime.now(timezone.utc)
    two_hours_ago = now_dt - timedelta(hours=2)
    twenty_four_hours_ago = now_dt - timedelta(hours=24)

    # Group articles by ticker
    by_ticker: dict[str, list[dict]] = defaultdict(list)
    for article in all_articles:
        by_ticker[article["ticker"]].append(article)

    for ticker, articles in by_ticker.items():
        # Parse timestamps and classify into time buckets
        recent_2h = []
        recent_24h = []
        for a in articles:
            pub = a.get("published_at", "")
            if not pub:
                # No timestamp — assume recent
                recent_2h.append(a)
                recent_24h.append(a)
                continue
            try:
                if isinstance(pub, str):
                    pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                else:
                    pub_dt = pub
                if pub_dt >= two_hours_ago:
                    recent_2h.append(a)
                if pub_dt >= twenty_four_hours_ago:
                    recent_24h.append(a)
            except (ValueError, TypeError):
                recent_24h.append(a)

        # Calculate velocity ratio
        hourly_avg_24h = len(recent_24h) / 24 if recent_24h else 0.1
        count_2h = len(recent_2h)
        velocity_ratio = count_2h / max(hourly_avg_24h * 2, 0.1)  # Compare 2h window to baseline

        # Calculate urgency based on keywords
        urgency_score = 0.0
        hottest_headline = ""
        for a in recent_2h:
            title_lower = a["title"].lower()
            keyword_hits = sum(1 for kw in URGENCY_KEYWORDS if kw.lower() in title_lower)
            article_urgency = min(1.0, keyword_hits * 0.3)
            if article_urgency > urgency_score:
                urgency_score = article_urgency
                hottest_headline = a["title"]

        # If no super-urgent keyword but high velocity, still flag
        if velocity_ratio >= 3.0 and urgency_score < 0.3:
            urgency_score = max(urgency_score, 0.3)
            if not hottest_headline and recent_2h:
                hottest_headline = recent_2h[0]["title"]

        # Threshold: velocity > 3× normal OR urgency keyword detected
        if velocity_ratio >= 3.0 or urgency_score >= 0.5:
            alerts.append({
                "ticker": ticker,
                "headline": hottest_headline,
                "source": recent_2h[0]["source"] if recent_2h else "mixed",
                "articles_2h": count_2h,
                "articles_24h": len(recent_24h),
                "velocity_ratio": round(velocity_ratio, 1),
                "urgency_score": round(urgency_score, 2),
            })

    # Sort by urgency × velocity
    alerts.sort(key=lambda a: a["urgency_score"] * a["velocity_ratio"], reverse=True)

    result = {
        "has_breaking": len(alerts) > 0,
        "alerts": alerts[:10],  # Top 10 most urgent
        "scanned_at": now_dt.isoformat(),
        "tickers_scanned": len(watchlist_tickers),
        "articles_analyzed": len(all_articles),
    }

    _breaking_cache[cache_key] = {"time": now, "data": result}
    return result


async def get_agent_watchlist(pool) -> list[str]:
    """
    Get the tickers the agent should monitor for breaking news.
    Combines: active holdings + recently analyzed + trending topics' top tickers.
    """
    tickers = set()

    async with pool.acquire() as conn:
        # Active holdings
        rows = await conn.fetch("SELECT ticker FROM agent_holdings")
        for r in rows:
            tickers.add(r["ticker"])

        # Recently analyzed/traded tickers (last 7 days)
        rows = await conn.fetch("""
            SELECT DISTINCT ticker FROM agent_trades
            WHERE opened_at >= NOW() - INTERVAL '7 days'
            LIMIT 20
        """)
        for r in rows:
            tickers.add(r["ticker"])

        # Top trending topics' primary tickers
        rows = await conn.fetch("""
            SELECT DISTINCT ts.ticker
            FROM topic_stocks ts
            JOIN topics t ON t.id = ts.topic_id
            JOIN momentum_scores m ON m.topic_id = t.id
            WHERE ts.priority <= 2
            ORDER BY ts.ticker
            LIMIT 30
        """)
        for r in rows:
            tickers.add(r["ticker"])

    return list(tickers)[:30]  # Cap at 30 for API limits
