"""
AI Agent router for TrendVest.

Exposes the agent's dashboard, manual trigger for analysis,
and performance data to the frontend.
"""

from fastapi import APIRouter, Depends
from ..deps import get_db_pool, get_stock_service

router = APIRouter(prefix="/api/agent", tags=["ai-agent"])


def _get_brain(pool, stock_service):
    from ..services.agent_brain import AgentBrain
    return AgentBrain(pool=pool, stock_service=stock_service)


async def _collect_signals(ticker: str, pool, stock_service) -> dict:
    """
    Shared signal collection for analyze and execute endpoints.

    Returns {"all": [...signals], "topic_slug": str|None}.
    Uses v2 signal extractors with NLP, Finnhub, and timing analysis.
    """
    from ..services.agent_signals import (
        extract_momentum_signal,
        extract_sentiment_signal,
        extract_technical_signal,
        extract_macro_signal,
        extract_user_herd_signal,
        extract_nlp_sentiment_signal,
        extract_user_ml_signal,
    )
    from ..services.alpha_vantage import AlphaVantageCollector
    from ..services.finnhub import FinnhubCollector
    from ..services.fred import FredCollector

    signals = []

    # 1. Technical (most reliable — pure math on price data)
    tech = extract_technical_signal(ticker)
    if tech:
        signals.append(tech)

    # 2. Macro regime
    fred = FredCollector()
    macro = extract_macro_signal(fred)
    if macro:
        signals.append(macro)

    # 3. Collect news texts for NLP (from yfinance news headlines)
    news_texts = []
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        news_items = stock.news or []
        for item in news_items[:15]:
            content = item.get("content", {})
            title = content.get("title", "")
            if title:
                news_texts.append(title)
    except Exception:
        pass

    # 4. Sentiment (multi-source: Alpha Vantage + Finnhub + NLP)
    av = AlphaVantageCollector()
    finnhub = FinnhubCollector()
    sentiment = extract_sentiment_signal(
        av, [ticker], ticker.lower(),
        finnhub_collector=finnhub,
        news_texts=news_texts,
    )
    if sentiment:
        signals.append(sentiment)

    # 5. Standalone NLP sentiment (if we got news texts, add as separate signal)
    if news_texts and len(news_texts) >= 3:
        nlp_sig = extract_nlp_sentiment_signal(news_texts, source_label=f"yfinance_{ticker}")
        if nlp_sig:
            # Change type to avoid double-counting with fused sentiment
            nlp_sig["signal_type"] = "nlp_sentiment"
            signals.append(nlp_sig)

    # 6. Momentum + User herd + ML — need topic for this ticker
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

        # User herd with timing analysis (pass stock_service for price comparison)
        user_herd = await extract_user_herd_signal(pool, topic_slug, stock_service=stock_service)
        if user_herd:
            signals.append(user_herd)

        # 7. User Behavior ML (real scikit-learn model)
        ml_sig = await extract_user_ml_signal(pool, topic_slug, stock_service=stock_service)
        if ml_sig:
            signals.append(ml_sig)

    return {"all": signals, "topic_slug": topic_slug}


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

    signals = await _collect_signals(ticker, pool, stock_service)
    brain = _get_brain(pool, stock_service)
    decision = await brain.evaluate_ticker(ticker, signals["all"])

    return {
        "ticker": ticker,
        "topic": signals["topic_slug"],
        "signals": signals["all"],
        "decision": {
            "action": decision["action"],
            "confidence": decision["confidence"],
            "direction": decision["direction"],
            "reason": decision["reason"],
            "regime": decision.get("regime", "normal"),
            "earnings_warning": decision.get("fusion", {}).get("earnings_warning"),
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

    signals = await _collect_signals(ticker, pool, stock_service)
    brain = _get_brain(pool, stock_service)
    decision = await brain.evaluate_ticker(ticker, signals["all"])
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
    outcomes = await brain.update_trade_outcomes()
    weight_update = await brain.update_signal_weights()
    perf = await brain.record_daily_performance()
    return {"outcomes": outcomes, "weight_update": weight_update, "performance": perf}


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


@router.get("/breaking")
async def get_breaking_news(
    pool=Depends(get_db_pool),
    stock_service=Depends(get_stock_service),
):
    """
    Scan for breaking news across the agent's watchlist.
    Returns urgent alerts sorted by urgency × velocity.
    """
    from ..services.agent_breaking import detect_breaking_news, get_agent_watchlist
    from ..services.finnhub import FinnhubCollector

    watchlist = await get_agent_watchlist(pool)
    if not watchlist:
        return {"has_breaking": False, "alerts": [], "tickers_scanned": 0}

    finnhub = FinnhubCollector()
    result = detect_breaking_news(watchlist, finnhub_collector=finnhub)

    # Log alerts to DB for audit
    if result["has_breaking"]:
        async with pool.acquire() as conn:
            for alert in result["alerts"][:5]:
                await conn.execute("""
                    INSERT INTO agent_breaking_alerts
                        (ticker, headline, velocity_ratio, urgency_score)
                    VALUES ($1, $2, $3, $4)
                """, alert["ticker"], alert["headline"],
                   alert["velocity_ratio"], alert["urgency_score"])

    return result


@router.post("/breaking/scan")
async def trigger_breaking_scan(
    pool=Depends(get_db_pool),
    stock_service=Depends(get_stock_service),
):
    """
    Scan for breaking news AND auto-analyze any tickers with alerts.
    This is the "hot news rapid response" endpoint.
    """
    from ..services.agent_breaking import detect_breaking_news, get_agent_watchlist
    from ..services.finnhub import FinnhubCollector

    watchlist = await get_agent_watchlist(pool)
    finnhub = FinnhubCollector()
    breaking = detect_breaking_news(watchlist, finnhub_collector=finnhub)

    analyses = []
    if breaking["has_breaking"]:
        brain = _get_brain(pool, stock_service)
        # Auto-analyze the top 3 most urgent tickers
        for alert in breaking["alerts"][:3]:
            ticker = alert["ticker"]
            signals = await _collect_signals(ticker, pool, stock_service)
            decision = await brain.evaluate_ticker(ticker, signals["all"])
            analyses.append({
                "ticker": ticker,
                "headline": alert["headline"],
                "urgency": alert["urgency_score"],
                "decision": decision["action"],
                "confidence": decision["confidence"],
                "reason": decision["reason"],
            })

    return {
        "breaking": breaking,
        "auto_analyses": analyses,
    }


@router.post("/ml/retrain")
async def retrain_ml_model(
    pool=Depends(get_db_pool),
    stock_service=Depends(get_stock_service),
):
    """
    Retrain the user behavior ML model on historical data.
    Should be called weekly or when significant new data is available.
    """
    from ..services.agent_user_ml import UserBehaviorML
    ml = UserBehaviorML(pool, stock_service)
    return await ml.retrain()


@router.get("/ml/info")
async def get_ml_model_info(
    pool=Depends(get_db_pool),
    stock_service=Depends(get_stock_service),
):
    """Get info about the current ML model status and accuracy."""
    from ..services.agent_user_ml import UserBehaviorML
    ml = UserBehaviorML(pool, stock_service)
    return await ml.get_model_info()
