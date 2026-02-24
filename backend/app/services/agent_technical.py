"""
Technical indicators for TrendVest AI Agent.

Calculates RSI, SMA, and basic signals from yfinance historical data.
This is straightforward math on existing price data — no magic.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import yfinance as yf
    import pandas as pd
except ImportError:
    yf = None
    pd = None


def get_technical_signals(ticker: str) -> Optional[dict]:
    """
    Calculate technical indicators for a ticker.

    Returns:
        dict with RSI, SMA crossover, price vs SMA, and an overall direction.
        Returns None if data is insufficient.
    """
    if not yf or not pd:
        return None

    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="3mo", interval="1d")

        if hist.empty or len(hist) < 20:
            return None

        close = hist["Close"]
        volume = hist["Volume"]

        # ── RSI (14-day) ──
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=14, min_periods=14).mean()
        avg_loss = loss.rolling(window=14, min_periods=14).mean()
        rs = avg_gain / avg_loss.replace(0, float("nan"))
        rsi = 100 - (100 / (1 + rs))
        current_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0

        # ── SMAs ──
        sma_20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
        sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
        current_price = float(close.iloc[-1])

        # ── Volume trend ──
        vol_avg_20 = float(volume.rolling(20).mean().iloc[-1]) if len(volume) >= 20 else None
        vol_today = float(volume.iloc[-1])
        volume_ratio = vol_today / vol_avg_20 if vol_avg_20 and vol_avg_20 > 0 else 1.0

        # ── Price change stats ──
        change_5d = float((close.iloc[-1] / close.iloc[-6] - 1) * 100) if len(close) >= 6 else 0.0
        change_20d = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) >= 21 else 0.0

        # ── Derive direction ──
        # Scoring: each factor votes bullish (+1), bearish (-1), or neutral (0)
        score = 0

        # RSI
        if current_rsi < 30:
            score += 1  # Oversold = potential bounce (bullish)
        elif current_rsi > 70:
            score -= 1  # Overbought = potential drop (bearish)

        # Price vs SMA20
        if sma_20:
            if current_price > sma_20 * 1.02:
                score += 1
            elif current_price < sma_20 * 0.98:
                score -= 1

        # SMA crossover (20 vs 50)
        if sma_20 and sma_50:
            if sma_20 > sma_50:
                score += 1  # Golden cross territory
            elif sma_20 < sma_50:
                score -= 1  # Death cross territory

        # Recent momentum
        if change_5d > 3:
            score += 1
        elif change_5d < -3:
            score -= 1

        # Determine direction
        if score >= 2:
            direction = "bullish"
            strength = min(0.9, 0.5 + score * 0.1)
        elif score <= -2:
            direction = "bearish"
            strength = min(0.9, 0.5 + abs(score) * 0.1)
        else:
            direction = "neutral"
            strength = 0.3

        return {
            "ticker": ticker,
            "rsi": round(current_rsi, 1),
            "sma_20": round(sma_20, 2) if sma_20 else None,
            "sma_50": round(sma_50, 2) if sma_50 else None,
            "price": round(current_price, 2),
            "price_vs_sma20_pct": round((current_price / sma_20 - 1) * 100, 2) if sma_20 else None,
            "change_5d": round(change_5d, 2),
            "change_20d": round(change_20d, 2),
            "volume_ratio": round(volume_ratio, 2),
            "direction": direction,
            "strength": round(strength, 2),
            "score": score,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.warning("Technical analysis failed for %s: %s", ticker, e)
        return None
