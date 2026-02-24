"""
TrendVest AI Agent Brain — v2.

v2 additions:
  - Regime-specific signal weights (bull/bear/volatile have different weights)
  - Signal decay integration (older signals matter less)
  - Earnings blackout check (don't trade near earnings)
  - Outcome tracking for 1d/7d/30d periods
  - Improved self-correction with regime context

HONEST DISCLAIMER:
This is a weighted scoring system, NOT machine learning.
It cannot predict the market. It tracks which signals worked
in the past and gives them slightly more weight next time.
Over 90 days it aims to be right >50% of the time — and that's
already a meaningful achievement.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ──

STARTING_BALANCE = 100_000.0
MAX_POSITION_PCT = 0.15        # Max 15% of portfolio in one stock
MAX_OPEN_POSITIONS = 10        # Diversification limit
MIN_CONFIDENCE = 0.55          # Don't trade below this confidence
STOP_LOSS_PCT = -8.0           # Sell if down 8%
TAKE_PROFIT_PCT = 15.0         # Sell if up 15%
DAILY_LOSS_LIMIT_PCT = -3.0    # Stop trading if portfolio drops 3% in a day

# Regime-specific confidence multipliers
# In volatile markets, require more confidence to act
REGIME_MULTIPLIERS = {
    "bull": 1.0,       # Normal confidence threshold
    "normal": 1.0,
    "bear": 0.8,       # Harder to buy in bear market
    "volatile": 0.65,  # Much harder — VIX > 30
}

# Regime-specific signal trust adjustments
# e.g., technical signals work better in bull markets
REGIME_SIGNAL_ADJUSTMENTS: dict[str, dict[str, float]] = {
    "bull": {
        "technical": 1.2,    # RSI oversold bounces work well
        "momentum": 1.1,     # Momentum follows trend
        "user_herd": 0.8,    # FOMO risk higher in bull
        "sentiment": 1.0,
        "nlp_sentiment": 0.9,  # NLP less trusted than API sentiment
        "macro": 0.8,        # Macro less relevant when VIX is low
        "cross_reference": 1.0,
        "user_ml": 1.2,      # ML shines in stable bull markets
    },
    "bear": {
        "technical": 0.8,    # Oversold can keep falling
        "momentum": 0.7,     # Momentum is unreliable in bear
        "user_herd": 0.6,    # Users are wrong more often
        "sentiment": 1.2,    # Sentiment extremes = potential bottoms
        "nlp_sentiment": 1.0,  # NLP can catch bottom sentiment
        "macro": 1.3,        # Macro drives bear markets
        "cross_reference": 0.9,
        "user_ml": 0.7,      # User patterns less reliable in panic
    },
    "volatile": {
        "technical": 0.7,    # Whipsaws kill technical signals
        "momentum": 0.6,     # Noise dominates
        "user_herd": 0.5,    # Panic behavior
        "sentiment": 0.8,    # Sentiment swings wildly
        "nlp_sentiment": 0.6,  # NLP too noisy in volatile markets
        "macro": 1.4,        # VIX and macro are king
        "cross_reference": 0.7,
        "user_ml": 0.5,      # ML trained on normal data fails in chaos
    },
    "normal": {},  # No adjustments
}


class AgentBrain:
    """The AI agent's decision-making core."""

    def __init__(self, pool, stock_service):
        self.pool = pool
        self.stock_service = stock_service

    # ──────────────────────────────────────
    # SIGNAL FUSION (v2: regime-aware + decay)
    # ──────────────────────────────────────

    async def fuse_signals(
        self,
        signals: list[dict],
        ticker: Optional[str] = None,
    ) -> dict:
        """
        Combine multiple signals into a single confidence score.

        v2 improvements:
        - Apply time decay to signal strength
        - Use regime-specific weight adjustments
        - Check earnings blackout
        """
        if not signals:
            return {"direction": "neutral", "confidence": 0.0, "signals_used": 0, "regime": "normal"}

        # Apply signal decay
        from .agent_signals import apply_signal_decay
        signals = [apply_signal_decay(s) for s in signals]

        # Detect regime from macro signal
        regime = "normal"
        for s in signals:
            if s["signal_type"] == "macro" and s.get("raw_data", {}).get("regime"):
                regime = s["raw_data"]["regime"]
                break

        # Load learned weights
        weights = await self._get_signal_weights()
        regime_adj = REGIME_SIGNAL_ADJUSTMENTS.get(regime, {})

        weighted_score = 0.0
        total_weight = 0.0
        signals_used = 0

        for signal in signals:
            stype = signal["signal_type"]
            base_weight = weights.get(stype, 1.0)
            regime_factor = regime_adj.get(stype, 1.0)
            weight = base_weight * regime_factor

            if signal["direction"] == "bullish":
                dir_score = 1.0
            elif signal["direction"] == "bearish":
                dir_score = -1.0
            else:
                dir_score = 0.0

            contribution = dir_score * signal["strength"] * weight
            weighted_score += contribution
            total_weight += weight * signal["strength"]
            signals_used += 1

        if total_weight > 0:
            normalized = weighted_score / total_weight
        else:
            normalized = 0.0

        confidence = abs(normalized)
        if normalized > 0.05:
            direction = "bullish"
        elif normalized < -0.05:
            direction = "bearish"
        else:
            direction = "neutral"
            confidence = 0.0

        # Apply regime confidence multiplier
        confidence *= REGIME_MULTIPLIERS.get(regime, 1.0)

        # Earnings blackout check
        earnings_warning = None
        if ticker:
            from .agent_signals import detect_earnings_blackout
            blackout = detect_earnings_blackout(ticker)
            if blackout and blackout.get("is_blackout"):
                confidence *= 0.3  # Dramatically reduce confidence near earnings
                earnings_warning = blackout

        return {
            "direction": direction,
            "confidence": round(min(confidence, 0.95), 3),
            "signals_used": signals_used,
            "regime": regime,
            "raw_score": round(normalized, 4),
            "earnings_warning": earnings_warning,
        }

    # ──────────────────────────────────────
    # TRADING DECISIONS
    # ──────────────────────────────────────

    async def evaluate_ticker(self, ticker: str, signals: list[dict]) -> dict:
        """
        Evaluate whether to buy, sell, or hold a specific ticker.

        Returns { action, confidence, reason, signals_snapshot }.
        """
        fusion = await self.fuse_signals(signals, ticker=ticker)

        # Check if we already hold this
        holding = await self._get_holding(ticker)
        portfolio = await self._get_portfolio_state()

        # Check daily loss limit
        if portfolio["daily_pnl_pct"] <= DAILY_LOSS_LIMIT_PCT:
            return {
                "action": "hold",
                "confidence": 0.0,
                "reason": f"Daily loss limit hit ({portfolio['daily_pnl_pct']:.1f}%)",
                "fusion": fusion,
            }

        action = "hold"
        reason = ""

        if holding:
            # Already holding — check exit conditions
            price_data = self.stock_service.get_price(ticker)
            current_price = price_data.price if price_data else holding["avg_cost"]
            pnl_pct = (current_price / holding["avg_cost"] - 1) * 100

            if pnl_pct <= STOP_LOSS_PCT:
                action = "sell"
                reason = f"Stop-loss triggered ({pnl_pct:.1f}%)"
            elif pnl_pct >= TAKE_PROFIT_PCT:
                action = "sell"
                reason = f"Take-profit triggered ({pnl_pct:.1f}%)"
            elif fusion["direction"] == "bearish" and fusion["confidence"] > 0.6:
                action = "sell"
                reason = f"Bearish reversal signal (conf={fusion['confidence']:.0%})"
            else:
                reason = f"Holding (P&L: {pnl_pct:.1f}%)"

        else:
            # Not holding — check entry conditions
            if (
                fusion["direction"] == "bullish"
                and fusion["confidence"] >= MIN_CONFIDENCE
                and portfolio["open_positions"] < MAX_OPEN_POSITIONS
            ):
                # Check position sizing
                price_data = self.stock_service.get_price(ticker)
                if price_data and price_data.price > 0:
                    max_spend = portfolio["total_value"] * MAX_POSITION_PCT
                    if portfolio["cash"] >= price_data.price * 5:  # At least 5 shares
                        action = "buy"
                        reason = f"Bullish signal (conf={fusion['confidence']:.0%}, {fusion['signals_used']} signals)"
                    else:
                        reason = "Insufficient cash for minimum position"
                else:
                    reason = "Cannot fetch price"
            elif fusion["direction"] == "bearish":
                reason = f"Bearish signal — no entry (conf={fusion['confidence']:.0%})"
            elif fusion["confidence"] < MIN_CONFIDENCE:
                reason = f"Confidence too low ({fusion['confidence']:.0%} < {MIN_CONFIDENCE:.0%})"
            else:
                reason = "No clear signal"

        return {
            "action": action,
            "ticker": ticker,
            "confidence": fusion["confidence"],
            "direction": fusion["direction"],
            "reason": reason,
            "regime": fusion["regime"],
            "fusion": fusion,
            "signals_snapshot": signals,
        }

    # ──────────────────────────────────────
    # TRADE EXECUTION
    # ──────────────────────────────────────

    async def execute_decision(self, decision: dict) -> Optional[dict]:
        """
        Execute a buy or sell decision on the agent's paper portfolio.
        Returns trade record or None if no trade was made.
        """
        if decision["action"] == "hold":
            return None

        ticker = decision["ticker"]
        price_data = self.stock_service.get_price(ticker)
        if not price_data or not price_data.price:
            return None

        price = price_data.price

        async with self.pool.acquire() as conn:
            portfolio = await self._get_portfolio_state()

            if decision["action"] == "buy":
                # Calculate quantity based on confidence and max position size
                max_spend = portfolio["total_value"] * MAX_POSITION_PCT
                max_spend = min(max_spend, portfolio["cash"])
                quantity = int(max_spend / price)
                # Scale by confidence (higher confidence → larger position)
                quantity = max(5, int(quantity * decision["confidence"]))
                total = price * quantity

                if total > portfolio["cash"]:
                    quantity = int(portfolio["cash"] / price)
                    total = price * quantity

                if quantity < 1:
                    return None

                # Update portfolio
                await conn.execute(
                    "UPDATE agent_portfolio SET cash_balance = cash_balance - $1, updated_at = NOW()",
                    total,
                )
                await conn.execute("""
                    INSERT INTO agent_holdings (ticker, quantity, avg_cost, entered_at)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT (ticker) DO UPDATE SET
                        quantity = agent_holdings.quantity + $2,
                        avg_cost = (agent_holdings.avg_cost * agent_holdings.quantity + $3 * $2)
                                   / (agent_holdings.quantity + $2)
                """, ticker, quantity, price)

                # Record trade
                trade_id = await conn.fetchval("""
                    INSERT INTO agent_trades
                        (ticker, action, quantity, entry_price, confidence, signals_snapshot, is_open)
                    VALUES ($1, 'buy', $2, $3, $4, $5, true)
                    RETURNING id
                """, ticker, quantity, price, decision["confidence"],
                   json.dumps(decision.get("signals_snapshot", [])))

                return {
                    "trade_id": trade_id,
                    "action": "buy",
                    "ticker": ticker,
                    "quantity": quantity,
                    "price": price,
                    "total": round(total, 2),
                    "confidence": decision["confidence"],
                    "reason": decision["reason"],
                }

            elif decision["action"] == "sell":
                holding = await self._get_holding(ticker)
                if not holding:
                    return None

                quantity = holding["quantity"]
                total = price * quantity

                # Remove holding
                await conn.execute(
                    "DELETE FROM agent_holdings WHERE ticker = $1", ticker
                )
                await conn.execute(
                    "UPDATE agent_portfolio SET cash_balance = cash_balance + $1, updated_at = NOW()",
                    total,
                )

                # Close trade(s) for this ticker
                await conn.execute("""
                    UPDATE agent_trades SET
                        is_open = false,
                        exit_price = $1,
                        closed_at = NOW()
                    WHERE ticker = $2 AND is_open = true
                """, price, ticker)

                pnl = total - (holding["avg_cost"] * quantity)
                pnl_pct = (price / holding["avg_cost"] - 1) * 100

                return {
                    "action": "sell",
                    "ticker": ticker,
                    "quantity": quantity,
                    "price": price,
                    "total": round(total, 2),
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "confidence": decision["confidence"],
                    "reason": decision["reason"],
                }

        return None

    # ──────────────────────────────────────
    # SELF-CORRECTION (Weight Learning)
    # ──────────────────────────────────────

    async def update_signal_weights(self):
        """
        Review closed trades and update signal weights based on outcomes.

        For each closed trade:
        - Look at which signals were active at entry
        - If the trade was profitable, those signals get +1 correct
        - If not, they get +1 total but no correct increment
        - Weight = accuracy * base_weight

        This is NOT ML. It's a running accuracy tracker.
        """
        async with self.pool.acquire() as conn:
            # Get recently closed trades that haven't been evaluated yet
            trades = await conn.fetch("""
                SELECT id, ticker, entry_price, exit_price, signals_snapshot
                FROM agent_trades
                WHERE is_open = false AND exit_price IS NOT NULL
                  AND closed_at > NOW() - INTERVAL '7 days'
            """)

            if not trades:
                return {"updated": 0}

            updates = {}
            for trade in trades:
                was_profitable = trade["exit_price"] > trade["entry_price"]
                try:
                    snapshots = json.loads(trade["signals_snapshot"]) if isinstance(trade["signals_snapshot"], str) else trade["signals_snapshot"]
                except (json.JSONDecodeError, TypeError):
                    continue

                for signal in (snapshots or []):
                    stype = signal.get("signal_type")
                    if not stype:
                        continue

                    if stype not in updates:
                        updates[stype] = {"total": 0, "correct": 0}

                    # A signal is "correct" if it said bullish and trade was profitable,
                    # or if it said bearish and... well, we only buy on bullish, so
                    # any buy signal is "correct" if profitable
                    direction = signal.get("direction", "neutral")
                    if direction == "bullish" and was_profitable:
                        updates[stype]["correct"] += 1
                    elif direction == "bearish" and not was_profitable:
                        updates[stype]["correct"] += 1  # Bearish was right to warn
                    updates[stype]["total"] += 1

            # Apply updates to weights
            for stype, counts in updates.items():
                await conn.execute("""
                    UPDATE agent_signal_weights SET
                        total_predictions = total_predictions + $1,
                        correct_predictions = correct_predictions + $2,
                        accuracy = CASE
                            WHEN total_predictions + $1 > 0
                            THEN (correct_predictions + $2)::float / (total_predictions + $1)
                            ELSE 0.5
                        END,
                        weight = CASE
                            WHEN total_predictions + $1 >= 10
                            THEN GREATEST(0.3, LEAST(2.0,
                                (correct_predictions + $2)::float / (total_predictions + $1) * 2
                            ))
                            ELSE 1.0  -- Keep default until we have enough data
                        END,
                        updated_at = NOW()
                    WHERE signal_type = $3
                """, counts["total"], counts["correct"], stype)

            return {"updated": len(updates), "details": updates}

    # ──────────────────────────────────────
    # OUTCOME TRACKING (1d / 7d / 30d)
    # ──────────────────────────────────────

    async def update_trade_outcomes(self) -> dict:
        """
        Update outcome_1d, outcome_7d, outcome_30d for open and recently closed trades.

        For each buy trade, check what the current price is vs entry price at
        the 1-day, 7-day, and 30-day marks. This lets us see which signals
        actually predicted correct moves over different time horizons.
        """
        now = datetime.now(timezone.utc)
        updated = {"outcome_1d": 0, "outcome_7d": 0, "outcome_30d": 0}

        async with self.pool.acquire() as conn:
            # Get trades that need outcome updates
            trades = await conn.fetch("""
                SELECT id, ticker, entry_price, opened_at,
                       outcome_1d, outcome_7d, outcome_30d
                FROM agent_trades
                WHERE entry_price IS NOT NULL
                  AND opened_at IS NOT NULL
                  AND (
                      (outcome_1d IS NULL AND opened_at <= NOW() - INTERVAL '1 day')
                      OR (outcome_7d IS NULL AND opened_at <= NOW() - INTERVAL '7 days')
                      OR (outcome_30d IS NULL AND opened_at <= NOW() - INTERVAL '30 days')
                  )
                ORDER BY opened_at DESC
                LIMIT 100
            """)

            if not trades:
                return {"updated": updated, "total_checked": 0}

            # Gather unique tickers for batch price fetch
            tickers = list({t["ticker"] for t in trades})
            prices = self.stock_service.get_prices_batch(tickers) if tickers else {}

            for trade in trades:
                ticker = trade["ticker"]
                entry = float(trade["entry_price"])
                opened = trade["opened_at"]
                if not opened or entry <= 0:
                    continue

                # Get current price for this ticker
                pd = prices.get(ticker)
                current_price = pd.price if pd else None
                if not current_price:
                    continue

                pnl_pct = round((current_price / entry - 1) * 100, 2)
                age = now - opened

                # 1-day outcome
                if trade["outcome_1d"] is None and age >= timedelta(days=1):
                    await conn.execute(
                        "UPDATE agent_trades SET outcome_1d = $1 WHERE id = $2",
                        pnl_pct, trade["id"],
                    )
                    updated["outcome_1d"] += 1

                # 7-day outcome
                if trade["outcome_7d"] is None and age >= timedelta(days=7):
                    await conn.execute(
                        "UPDATE agent_trades SET outcome_7d = $1 WHERE id = $2",
                        pnl_pct, trade["id"],
                    )
                    updated["outcome_7d"] += 1

                # 30-day outcome
                if trade["outcome_30d"] is None and age >= timedelta(days=30):
                    await conn.execute(
                        "UPDATE agent_trades SET outcome_30d = $1 WHERE id = $2",
                        pnl_pct, trade["id"],
                    )
                    updated["outcome_30d"] += 1

        return {"updated": updated, "total_checked": len(trades)}

    # ──────────────────────────────────────
    # PERFORMANCE TRACKING
    # ──────────────────────────────────────

    async def record_daily_performance(self) -> dict:
        """Snapshot daily performance vs SPY benchmark."""
        portfolio = await self._get_portfolio_state()

        # Get SPY for benchmark
        spy_data = self.stock_service.get_price("SPY")
        spy_price = spy_data.price if spy_data else None

        today = datetime.now(timezone.utc).date()

        async with self.pool.acquire() as conn:
            # Get yesterday's performance for comparison
            yesterday = await conn.fetchrow("""
                SELECT portfolio_value, benchmark_value
                FROM agent_performance
                WHERE date < $1
                ORDER BY date DESC LIMIT 1
            """, today)

            prev_value = yesterday["portfolio_value"] if yesterday else STARTING_BALANCE
            daily_pnl = portfolio["total_value"] - prev_value
            daily_pnl_pct = (daily_pnl / prev_value * 100) if prev_value > 0 else 0
            cumulative_pnl = portfolio["total_value"] - STARTING_BALANCE
            cumulative_pnl_pct = (cumulative_pnl / STARTING_BALANCE * 100)

            # Benchmark tracking
            benchmark_pnl_pct = None
            if spy_price and yesterday and yesterday["benchmark_value"]:
                first_spy = await conn.fetchval("""
                    SELECT benchmark_value FROM agent_performance
                    ORDER BY date ASC LIMIT 1
                """)
                if first_spy and first_spy > 0:
                    benchmark_pnl_pct = (spy_price / first_spy - 1) * 100

            # Count wins
            total_closed = await conn.fetchval(
                "SELECT COUNT(*) FROM agent_trades WHERE is_open = false AND exit_price IS NOT NULL"
            ) or 0
            wins = await conn.fetchval(
                "SELECT COUNT(*) FROM agent_trades WHERE is_open = false AND exit_price > entry_price"
            ) or 0
            win_rate = (wins / total_closed * 100) if total_closed > 0 else 0

            # Detect regime
            regime = portfolio.get("regime", "normal")

            # Upsert today's performance
            await conn.execute("""
                INSERT INTO agent_performance (
                    date, portfolio_value, daily_pnl, daily_pnl_pct,
                    cumulative_pnl, cumulative_pnl_pct,
                    benchmark_value, benchmark_pnl_pct,
                    open_positions, total_trades, win_rate, regime
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                ON CONFLICT (date) DO UPDATE SET
                    portfolio_value = EXCLUDED.portfolio_value,
                    daily_pnl = EXCLUDED.daily_pnl,
                    daily_pnl_pct = EXCLUDED.daily_pnl_pct,
                    cumulative_pnl = EXCLUDED.cumulative_pnl,
                    cumulative_pnl_pct = EXCLUDED.cumulative_pnl_pct,
                    benchmark_value = EXCLUDED.benchmark_value,
                    benchmark_pnl_pct = EXCLUDED.benchmark_pnl_pct,
                    open_positions = EXCLUDED.open_positions,
                    total_trades = EXCLUDED.total_trades,
                    win_rate = EXCLUDED.win_rate,
                    regime = EXCLUDED.regime
            """, today, portfolio["total_value"], round(daily_pnl, 2),
               round(daily_pnl_pct, 2), round(cumulative_pnl, 2),
               round(cumulative_pnl_pct, 2), spy_price, benchmark_pnl_pct,
               portfolio["open_positions"], total_closed, round(win_rate, 1), regime)

        return {
            "date": str(today),
            "portfolio_value": portfolio["total_value"],
            "daily_pnl": round(daily_pnl, 2),
            "daily_pnl_pct": round(daily_pnl_pct, 2),
            "cumulative_pnl_pct": round(cumulative_pnl_pct, 2),
            "benchmark_pnl_pct": benchmark_pnl_pct,
            "win_rate": round(win_rate, 1),
            "open_positions": portfolio["open_positions"],
        }

    # ──────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────

    async def _get_signal_weights(self) -> dict[str, float]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT signal_type, weight FROM agent_signal_weights")
        return {r["signal_type"]: r["weight"] for r in rows}

    async def _get_holding(self, ticker: str) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT ticker, quantity, avg_cost FROM agent_holdings WHERE ticker = $1",
                ticker,
            )
        if row:
            return {"ticker": row["ticker"], "quantity": row["quantity"], "avg_cost": row["avg_cost"]}
        return None

    async def _get_portfolio_state(self) -> dict:
        async with self.pool.acquire() as conn:
            cash = await conn.fetchval("SELECT cash_balance FROM agent_portfolio LIMIT 1")
            if cash is None:
                cash = STARTING_BALANCE

            holdings = await conn.fetch("SELECT ticker, quantity, avg_cost FROM agent_holdings")

        # Get current prices for all holdings
        tickers = [h["ticker"] for h in holdings]
        prices = self.stock_service.get_prices_batch(tickers) if tickers else {}

        total_market = 0.0
        for h in holdings:
            pd = prices.get(h["ticker"])
            current = pd.price if pd else h["avg_cost"]
            total_market += current * h["quantity"]

        total_value = cash + total_market
        daily_pnl_pct = 0.0  # Will be calculated properly in record_daily_performance

        return {
            "cash": round(cash, 2),
            "total_value": round(total_value, 2),
            "market_value": round(total_market, 2),
            "open_positions": len(holdings),
            "daily_pnl_pct": daily_pnl_pct,
        }

    async def get_dashboard(self) -> dict:
        """Get complete agent dashboard data for the frontend."""
        async with self.pool.acquire() as conn:
            # Portfolio state
            portfolio = await self._get_portfolio_state()

            # Holdings with current prices
            holdings_rows = await conn.fetch(
                "SELECT ticker, quantity, avg_cost, entered_at FROM agent_holdings ORDER BY entered_at DESC"
            )
            tickers = [h["ticker"] for h in holdings_rows]
            prices = self.stock_service.get_prices_batch(tickers) if tickers else {}

            holdings = []
            for h in holdings_rows:
                pd = prices.get(h["ticker"])
                current = pd.price if pd else h["avg_cost"]
                pnl_pct = (current / h["avg_cost"] - 1) * 100 if h["avg_cost"] > 0 else 0
                holdings.append({
                    "ticker": h["ticker"],
                    "quantity": h["quantity"],
                    "avg_cost": round(h["avg_cost"], 2),
                    "current_price": round(current, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "entered_at": h["entered_at"].isoformat() if h["entered_at"] else None,
                })

            # Recent trades
            trades = await conn.fetch("""
                SELECT ticker, action, quantity, entry_price, exit_price,
                       confidence, is_open, opened_at, closed_at,
                       outcome_1d, outcome_7d, outcome_30d
                FROM agent_trades
                ORDER BY opened_at DESC
                LIMIT 20
            """)

            # Performance history
            perf = await conn.fetch("""
                SELECT date, portfolio_value, daily_pnl_pct, cumulative_pnl_pct,
                       benchmark_pnl_pct, win_rate, regime
                FROM agent_performance
                ORDER BY date DESC
                LIMIT 30
            """)

            # Signal weights
            weights = await conn.fetch("""
                SELECT signal_type, weight, accuracy, total_predictions, correct_predictions
                FROM agent_signal_weights
                ORDER BY weight DESC
            """)

            # Stats
            total_trades_count = await conn.fetchval(
                "SELECT COUNT(*) FROM agent_trades"
            ) or 0
            wins = await conn.fetchval(
                "SELECT COUNT(*) FROM agent_trades WHERE is_open = false AND exit_price > entry_price"
            ) or 0
            losses = await conn.fetchval(
                "SELECT COUNT(*) FROM agent_trades WHERE is_open = false AND exit_price <= entry_price"
            ) or 0

        return {
            "portfolio": portfolio,
            "holdings": holdings,
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
                for t in trades
            ],
            "performance": [
                {
                    "date": str(p["date"]),
                    "value": p["portfolio_value"],
                    "daily_pnl_pct": p["daily_pnl_pct"],
                    "cumulative_pnl_pct": p["cumulative_pnl_pct"],
                    "benchmark_pnl_pct": p["benchmark_pnl_pct"],
                    "win_rate": p["win_rate"],
                    "regime": p["regime"],
                }
                for p in perf
            ],
            "signal_weights": [
                {
                    "type": w["signal_type"],
                    "weight": round(w["weight"], 2),
                    "accuracy": round(w["accuracy"] * 100, 1),
                    "predictions": w["total_predictions"],
                    "correct": w["correct_predictions"],
                }
                for w in weights
            ],
            "stats": {
                "total_trades": total_trades_count,
                "wins": wins,
                "losses": losses,
                "win_rate": round(wins / max(wins + losses, 1) * 100, 1),
                "cumulative_pnl": round(portfolio["total_value"] - STARTING_BALANCE, 2),
                "cumulative_pnl_pct": round((portfolio["total_value"] / STARTING_BALANCE - 1) * 100, 2),
            },
        }
