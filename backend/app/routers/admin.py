"""
Admin Dashboard Router for TrendVest.

Back-office analytics and management for platform operators.
Provides overview of:
  - Platform health & user engagement metrics
  - AI Agent performance, trades, signal accuracy
  - ML model status and retraining controls
  - Breaking news alert history
  - User behavior patterns and trends
"""

from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from ..deps import get_db_pool, get_stock_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/overview")
async def get_admin_overview(
    pool=Depends(get_db_pool),
    stock_service=Depends(get_stock_service),
):
    """Complete admin overview — all metrics in one call."""
    async with pool.acquire() as conn:
        # ── Platform Metrics ──
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
        active_users_24h = await conn.fetchval("""
            SELECT COUNT(DISTINCT user_id) FROM user_interactions
            WHERE created_at >= NOW() - INTERVAL '24 hours'
        """) or 0
        active_users_7d = await conn.fetchval("""
            SELECT COUNT(DISTINCT user_id) FROM user_interactions
            WHERE created_at >= NOW() - INTERVAL '7 days'
        """) or 0
        total_interactions_24h = await conn.fetchval("""
            SELECT COUNT(*) FROM user_interactions
            WHERE created_at >= NOW() - INTERVAL '24 hours'
        """) or 0
        total_interactions_7d = await conn.fetchval("""
            SELECT COUNT(*) FROM user_interactions
            WHERE created_at >= NOW() - INTERVAL '7 days'
        """) or 0

        # ── Delta Comparisons (previous 24h window) ──
        prev_active_users_24h = await conn.fetchval("""
            SELECT COUNT(DISTINCT user_id) FROM user_interactions
            WHERE created_at >= NOW() - INTERVAL '48 hours'
              AND created_at < NOW() - INTERVAL '24 hours'
        """) or 0
        prev_interactions_24h = await conn.fetchval("""
            SELECT COUNT(*) FROM user_interactions
            WHERE created_at >= NOW() - INTERVAL '48 hours'
              AND created_at < NOW() - INTERVAL '24 hours'
        """) or 0

        # Interaction type breakdown (24h)
        interaction_breakdown = await conn.fetch("""
            SELECT interaction_type, COUNT(*) AS cnt
            FROM user_interactions
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            GROUP BY interaction_type
            ORDER BY cnt DESC
        """)

        # ── Agent Portfolio ──
        cash = await conn.fetchval("SELECT cash_balance FROM agent_portfolio LIMIT 1") or 100000
        holdings = await conn.fetch("SELECT ticker, quantity, avg_cost FROM agent_holdings")

        tickers = [h["ticker"] for h in holdings]
        prices = stock_service.get_prices_batch(tickers) if tickers else {}
        market_value = 0.0
        holdings_data = []
        for h in holdings:
            pd = prices.get(h["ticker"])
            current = pd.price if pd else h["avg_cost"]
            pnl_pct = (current / h["avg_cost"] - 1) * 100 if h["avg_cost"] > 0 else 0
            market_value += current * h["quantity"]
            holdings_data.append({
                "ticker": h["ticker"],
                "quantity": h["quantity"],
                "avg_cost": round(h["avg_cost"], 2),
                "current_price": round(current, 2),
                "pnl_pct": round(pnl_pct, 2),
                "market_value": round(current * h["quantity"], 2),
            })

        total_value = cash + market_value

        # ── Agent Trade Stats ──
        total_trades = await conn.fetchval("SELECT COUNT(*) FROM agent_trades") or 0
        open_trades = await conn.fetchval("SELECT COUNT(*) FROM agent_trades WHERE is_open = true") or 0
        closed_trades = await conn.fetchval("SELECT COUNT(*) FROM agent_trades WHERE is_open = false") or 0
        wins = await conn.fetchval(
            "SELECT COUNT(*) FROM agent_trades WHERE is_open = false AND exit_price > entry_price"
        ) or 0
        losses = await conn.fetchval(
            "SELECT COUNT(*) FROM agent_trades WHERE is_open = false AND exit_price <= entry_price"
        ) or 0

        # Avg outcome by timeframe
        avg_outcomes = await conn.fetchrow("""
            SELECT
                AVG(outcome_1d) AS avg_1d,
                AVG(outcome_7d) AS avg_7d,
                AVG(outcome_30d) AS avg_30d,
                COUNT(outcome_1d) AS count_1d,
                COUNT(outcome_7d) AS count_7d,
                COUNT(outcome_30d) AS count_30d
            FROM agent_trades
            WHERE outcome_1d IS NOT NULL OR outcome_7d IS NOT NULL OR outcome_30d IS NOT NULL
        """)

        # Recent trades
        recent_trades = await conn.fetch("""
            SELECT ticker, action, quantity, entry_price, exit_price,
                   confidence, is_open, opened_at, closed_at,
                   outcome_1d, outcome_7d, outcome_30d
            FROM agent_trades
            ORDER BY opened_at DESC LIMIT 30
        """)

        # ── Signal Weights ──
        weights = await conn.fetch("""
            SELECT signal_type, weight, accuracy, total_predictions, correct_predictions, updated_at
            FROM agent_signal_weights
            ORDER BY weight DESC
        """)

        # ── Performance History ──
        performance = await conn.fetch("""
            SELECT date, portfolio_value, daily_pnl, daily_pnl_pct,
                   cumulative_pnl_pct, benchmark_pnl_pct, win_rate, regime
            FROM agent_performance
            ORDER BY date DESC LIMIT 60
        """)

        # ── Breaking News History ──
        breaking_alerts = await conn.fetch("""
            SELECT ticker, headline, velocity_ratio, urgency_score, scan_triggered, created_at
            FROM agent_breaking_alerts
            ORDER BY created_at DESC LIMIT 30
        """)

        # ── ML Model Info ──
        ml_model = await conn.fetchrow(
            "SELECT model_key, metadata, trained_at FROM agent_ml_models WHERE model_key = 'user_behavior_v1'"
        )

        # ── Top Trending Topics ──
        trending = await conn.fetch("""
            SELECT t.slug, t.name_en, t.name_he, m.score, m.direction,
                   m.mention_count_today, m.mention_avg_7d
            FROM momentum_scores m
            JOIN topics t ON t.id = m.topic_id
            ORDER BY m.score DESC LIMIT 15
        """)

        # ── Top interacted topics (24h) ──
        top_topics = await conn.fetch("""
            SELECT target_slug, COUNT(*) AS cnt,
                   COUNT(DISTINCT session_id) AS unique_sessions
            FROM user_interactions
            WHERE created_at >= NOW() - INTERVAL '24 hours'
              AND target_slug IS NOT NULL
            GROUP BY target_slug
            ORDER BY cnt DESC LIMIT 15
        """)

        # ── Agent Activity Timeline ──
        timeline_trades = await conn.fetch("""
            SELECT 'trade' AS event_type, ticker, action AS detail,
                   confidence, opened_at AS event_time
            FROM agent_trades
            ORDER BY opened_at DESC LIMIT 10
        """)
        timeline_alerts = await conn.fetch("""
            SELECT 'breaking' AS event_type, ticker, headline AS detail,
                   urgency_score AS confidence, created_at AS event_time
            FROM agent_breaking_alerts
            ORDER BY created_at DESC LIMIT 10
        """)
        timeline_weights = await conn.fetch("""
            SELECT 'weight_update' AS event_type, signal_type AS ticker,
                   ROUND(weight::numeric, 3)::text AS detail,
                   accuracy AS confidence, updated_at AS event_time
            FROM agent_signal_weights
            WHERE updated_at IS NOT NULL
            ORDER BY updated_at DESC LIMIT 5
        """)
        # Merge and sort timeline
        raw_timeline = list(timeline_trades) + list(timeline_alerts) + list(timeline_weights)
        raw_timeline.sort(key=lambda x: x["event_time"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

        # ── Health Checks ──
        last_trade_at = await conn.fetchval(
            "SELECT MAX(opened_at) FROM agent_trades"
        )
        last_alert_at = await conn.fetchval(
            "SELECT MAX(created_at) FROM agent_breaking_alerts"
        )
        last_weight_update = await conn.fetchval(
            "SELECT MAX(updated_at) FROM agent_signal_weights"
        )
        now = datetime.now(timezone.utc)
        ml_freshness_hours = None
        if ml_model and ml_model["trained_at"]:
            ml_freshness_hours = round((now - ml_model["trained_at"]).total_seconds() / 3600, 1)

    return {
        "platform": {
            "total_users": total_users,
            "active_users_24h": active_users_24h,
            "active_users_7d": active_users_7d,
            "interactions_24h": total_interactions_24h,
            "interactions_7d": total_interactions_7d,
            "prev_active_users_24h": prev_active_users_24h,
            "prev_interactions_24h": prev_interactions_24h,
            "interaction_breakdown": [
                {"type": r["interaction_type"], "count": r["cnt"]}
                for r in interaction_breakdown
            ],
        },
        "agent": {
            "portfolio": {
                "cash": round(cash, 2),
                "market_value": round(market_value, 2),
                "total_value": round(total_value, 2),
                "pnl": round(total_value - 100000, 2),
                "pnl_pct": round((total_value / 100000 - 1) * 100, 2),
            },
            "holdings": holdings_data,
            "trades": {
                "total": total_trades,
                "open": open_trades,
                "closed": closed_trades,
                "wins": wins,
                "losses": losses,
                "win_rate": round(wins / max(wins + losses, 1) * 100, 1),
            },
            "outcomes": {
                "avg_1d": round(avg_outcomes["avg_1d"], 2) if avg_outcomes and avg_outcomes["avg_1d"] else None,
                "avg_7d": round(avg_outcomes["avg_7d"], 2) if avg_outcomes and avg_outcomes["avg_7d"] else None,
                "avg_30d": round(avg_outcomes["avg_30d"], 2) if avg_outcomes and avg_outcomes["avg_30d"] else None,
                "count_1d": avg_outcomes["count_1d"] if avg_outcomes else 0,
                "count_7d": avg_outcomes["count_7d"] if avg_outcomes else 0,
                "count_30d": avg_outcomes["count_30d"] if avg_outcomes else 0,
            },
            "recent_trades": [
                {
                    "ticker": t["ticker"],
                    "action": t["action"],
                    "quantity": t["quantity"],
                    "entry_price": t["entry_price"],
                    "exit_price": t["exit_price"],
                    "confidence": t["confidence"],
                    "is_open": t["is_open"],
                    "opened_at": t["opened_at"].isoformat() if t["opened_at"] else None,
                    "closed_at": t["closed_at"].isoformat() if t["closed_at"] else None,
                    "pnl_pct": round((t["exit_price"] / t["entry_price"] - 1) * 100, 2) if t["exit_price"] and t["entry_price"] else None,
                    "outcome_1d": t["outcome_1d"],
                    "outcome_7d": t["outcome_7d"],
                    "outcome_30d": t["outcome_30d"],
                }
                for t in recent_trades
            ],
        },
        "signals": {
            "weights": [
                {
                    "type": w["signal_type"],
                    "weight": round(w["weight"], 2),
                    "accuracy": round(w["accuracy"] * 100, 1),
                    "predictions": w["total_predictions"],
                    "correct": w["correct_predictions"],
                    "updated_at": w["updated_at"].isoformat() if w["updated_at"] else None,
                }
                for w in weights
            ],
        },
        "performance": [
            {
                "date": str(p["date"]),
                "value": p["portfolio_value"],
                "daily_pnl": p["daily_pnl"],
                "daily_pnl_pct": p["daily_pnl_pct"],
                "cumulative_pnl_pct": p["cumulative_pnl_pct"],
                "benchmark_pnl_pct": p["benchmark_pnl_pct"],
                "win_rate": p["win_rate"],
                "regime": p["regime"],
            }
            for p in performance
        ],
        "breaking_history": [
            {
                "ticker": a["ticker"],
                "headline": a["headline"],
                "velocity_ratio": a["velocity_ratio"],
                "urgency_score": a["urgency_score"],
                "scan_triggered": a["scan_triggered"],
                "created_at": a["created_at"].isoformat() if a["created_at"] else None,
            }
            for a in breaking_alerts
        ],
        "ml_model": {
            "status": "trained" if ml_model else "not_trained",
            "trained_at": ml_model["trained_at"].isoformat() if ml_model and ml_model["trained_at"] else None,
            "metadata": ml_model["metadata"] if ml_model else None,
        },
        "trending_topics": [
            {
                "slug": t["slug"],
                "name_en": t["name_en"],
                "name_he": t["name_he"],
                "score": t["score"],
                "direction": t["direction"],
                "mentions_today": t["mention_count_today"],
                "avg_7d": t["mention_avg_7d"],
            }
            for t in trending
        ],
        "top_user_topics": [
            {
                "slug": t["target_slug"],
                "interactions": t["cnt"],
                "unique_sessions": t["unique_sessions"],
            }
            for t in top_topics
        ],
        "health": {
            "last_trade_at": last_trade_at.isoformat() if last_trade_at else None,
            "last_alert_at": last_alert_at.isoformat() if last_alert_at else None,
            "last_weight_update": last_weight_update.isoformat() if last_weight_update else None,
            "ml_freshness_hours": ml_freshness_hours,
            "data_pipeline_ok": total_interactions_24h > 0 or active_users_24h > 0,
            "agent_active": last_trade_at is not None and (now - last_trade_at).total_seconds() < 86400 * 3,
        },
        "timeline": [
            {
                "event_type": e["event_type"],
                "ticker": e["ticker"],
                "detail": str(e["detail"]) if e["detail"] else None,
                "confidence": float(e["confidence"]) if e["confidence"] else None,
                "event_time": e["event_time"].isoformat() if e["event_time"] else None,
            }
            for e in raw_timeline[:20]
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
