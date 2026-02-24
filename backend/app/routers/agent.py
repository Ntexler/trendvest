"""
AI Agent router for TrendVest.

Exposes the agent's dashboard, manual trigger for analysis,
and performance data to the frontend.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from ..deps import get_db_pool, get_stock_service

router = APIRouter(prefix="/api/agent", tags=["ai-agent"])


def _get_brain(pool, stock_service):
    from ..services.agent_brain import AgentBrain
    return AgentBrain(pool=pool, stock_service=stock_service)


@router.get("/dashboard")
async def get_agent_dashboard(
    pool=Depends(get_db_pool),
    stock_service=Depends(get_stock_service),
):
    """Get complete agent dashboard: portfolio, trades, performance, signal weights."""
    brain = _get_brain(pool, stock_service)
    return await brain.get_dashboard()


@router.post("/analyze/{ticker}")
async def analyze_ticker(
    ticker: str,
    pool=Depends(get_db_pool),
    stock_service=Depends(get_stock_service),
):
    """
    Run full signal analysis on a ticker.
    Returns all signals and the fused decision — but does NOT execute a trade.
    """
    ticker = ticker.upper()

    from ..services.agent_signals import (
        extract_momentum_signal,
        extract_sentiment_signal,
        extract_technical_signal,
        extract_macro_signal,
        extract_user_herd_signal,
    )
    from ..services.alpha_vantage import AlphaVantageCollector
    from ..services.fred import FredCollector

    signals = []

    # Technical (most reliable — pure math on price data)
    tech = extract_technical_signal(ticker)
    if tech:
        signals.append(tech)

    # Macro regime
    fred = FredCollector()
    macro = extract_macro_signal(fred)
    if macro:
        signals.append(macro)

    # Sentiment (limited by Alpha Vantage API quota)
    av = AlphaVantageCollector()
    sentiment = extract_sentiment_signal(av, [ticker], ticker.lower())
    if sentiment:
        signals.append(sentiment)

    # Momentum — try to find topic for this ticker
    async with pool.acquire() as conn:
        topic_row = await conn.fetchrow("""
            SELECT t.slug FROM topics t
            JOIN topic_stocks ts ON ts.topic_id = t.id
            WHERE ts.ticker = $1
            LIMIT 1
        """, ticker)

    topic_slug = topic_row["slug"] if topic_row else None

    if topic_slug:
        momentum = await extract_momentum_signal(pool, topic_slug)
        if momentum:
            signals.append(momentum)

        user_herd = await extract_user_herd_signal(pool, topic_slug)
        if user_herd:
            signals.append(user_herd)

    # Fuse signals
    brain = _get_brain(pool, stock_service)
    decision = await brain.evaluate_ticker(ticker, signals)

    return {
        "ticker": ticker,
        "topic": topic_slug,
        "signals": signals,
        "decision": {
            "action": decision["action"],
            "confidence": decision["confidence"],
            "direction": decision["direction"],
            "reason": decision["reason"],
            "regime": decision.get("regime", "normal"),
        },
    }


@router.post("/execute/{ticker}")
async def execute_trade(
    ticker: str,
    pool=Depends(get_db_pool),
    stock_service=Depends(get_stock_service),
):
    """
    Run analysis AND execute the trade if signals warrant it.
    This is what the agent's scheduler would call automatically.
    """
    ticker = ticker.upper()

    # First analyze
    from ..services.agent_signals import (
        extract_momentum_signal,
        extract_sentiment_signal,
        extract_technical_signal,
        extract_macro_signal,
        extract_user_herd_signal,
    )
    from ..services.alpha_vantage import AlphaVantageCollector
    from ..services.fred import FredCollector

    signals = []

    tech = extract_technical_signal(ticker)
    if tech:
        signals.append(tech)

    fred = FredCollector()
    macro = extract_macro_signal(fred)
    if macro:
        signals.append(macro)

    av = AlphaVantageCollector()
    sentiment = extract_sentiment_signal(av, [ticker], ticker.lower())
    if sentiment:
        signals.append(sentiment)

    async with pool.acquire() as conn:
        topic_row = await conn.fetchrow("""
            SELECT t.slug FROM topics t
            JOIN topic_stocks ts ON ts.topic_id = t.id
            WHERE ts.ticker = $1 LIMIT 1
        """, ticker)

    topic_slug = topic_row["slug"] if topic_row else None

    if topic_slug:
        momentum = await extract_momentum_signal(pool, topic_slug)
        if momentum:
            signals.append(momentum)
        user_herd = await extract_user_herd_signal(pool, topic_slug)
        if user_herd:
            signals.append(user_herd)

    brain = _get_brain(pool, stock_service)
    decision = await brain.evaluate_ticker(ticker, signals)
    trade = await brain.execute_decision(decision)

    return {
        "ticker": ticker,
        "decision": decision["action"],
        "confidence": decision["confidence"],
        "reason": decision["reason"],
        "trade": trade,
    }


@router.post("/learn")
async def trigger_learning(
    pool=Depends(get_db_pool),
    stock_service=Depends(get_stock_service),
):
    """
    Trigger self-correction: review closed trades and update signal weights.
    Also records daily performance snapshot.
    """
    brain = _get_brain(pool, stock_service)
    weight_update = await brain.update_signal_weights()
    perf = await brain.record_daily_performance()
    return {"weight_update": weight_update, "performance": perf}


@router.get("/weights")
async def get_signal_weights(pool=Depends(get_db_pool)):
    """Get current signal weights and their accuracy."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT signal_type, weight, accuracy, total_predictions,
                   correct_predictions, updated_at
            FROM agent_signal_weights
            ORDER BY weight DESC
        """)
    return {
        "weights": [
            {
                "type": r["signal_type"],
                "weight": round(r["weight"], 2),
                "accuracy": round(r["accuracy"] * 100, 1),
                "predictions": r["total_predictions"],
                "correct": r["correct_predictions"],
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in rows
        ]
    }
