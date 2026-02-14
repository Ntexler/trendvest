"""
Paper trading (demo/practice) router for TrendVest.
"""
from fastapi import APIRouter, Depends, HTTPException
from ..models.schemas import TradeRequest, PortfolioResponse, HoldingResponse, TradeHistoryItem
from ..deps import get_db_pool, get_stock_service

router = APIRouter(prefix="/api/paper", tags=["paper-trading"])

STARTING_BALANCE = 100000.0


async def ensure_portfolio(conn, session_id: str):
    """Create portfolio if it doesn't exist."""
    await conn.execute("""
        INSERT INTO paper_portfolios (session_id, cash_balance)
        VALUES ($1, $2)
        ON CONFLICT (session_id) DO NOTHING
    """, session_id, STARTING_BALANCE)


@router.post("/trade")
async def execute_trade(
    body: TradeRequest,
    pool=Depends(get_db_pool),
    stock_service=Depends(get_stock_service),
):
    """Execute a paper trade (buy or sell)."""
    ticker = body.ticker.upper()

    # Get current price
    price_data = stock_service.get_price(ticker)
    if not price_data or not price_data.price:
        raise HTTPException(status_code=400, detail=f"Could not get price for {ticker}")

    price = price_data.price
    total = price * body.quantity

    async with pool.acquire() as conn:
        await ensure_portfolio(conn, body.session_id)

        if body.action == "buy":
            # Check cash balance
            cash = await conn.fetchval(
                "SELECT cash_balance FROM paper_portfolios WHERE session_id = $1",
                body.session_id
            )
            if cash < total:
                raise HTTPException(status_code=400, detail=f"Insufficient funds. Need ${total:.2f}, have ${cash:.2f}")

            # Deduct cash
            await conn.execute(
                "UPDATE paper_portfolios SET cash_balance = cash_balance - $1 WHERE session_id = $2",
                total, body.session_id
            )

            # Update holdings
            existing = await conn.fetchrow(
                "SELECT quantity, avg_cost FROM paper_holdings WHERE session_id = $1 AND ticker = $2",
                body.session_id, ticker
            )
            if existing:
                new_qty = existing["quantity"] + body.quantity
                new_avg = ((existing["avg_cost"] * existing["quantity"]) + total) / new_qty
                await conn.execute(
                    "UPDATE paper_holdings SET quantity = $1, avg_cost = $2 WHERE session_id = $3 AND ticker = $4",
                    new_qty, new_avg, body.session_id, ticker
                )
            else:
                await conn.execute(
                    "INSERT INTO paper_holdings (session_id, ticker, quantity, avg_cost) VALUES ($1, $2, $3, $4)",
                    body.session_id, ticker, body.quantity, price
                )

        elif body.action == "sell":
            existing = await conn.fetchrow(
                "SELECT quantity FROM paper_holdings WHERE session_id = $1 AND ticker = $2",
                body.session_id, ticker
            )
            if not existing or existing["quantity"] < body.quantity:
                raise HTTPException(status_code=400, detail=f"Not enough shares of {ticker} to sell")

            new_qty = existing["quantity"] - body.quantity
            if new_qty == 0:
                await conn.execute(
                    "DELETE FROM paper_holdings WHERE session_id = $1 AND ticker = $2",
                    body.session_id, ticker
                )
            else:
                await conn.execute(
                    "UPDATE paper_holdings SET quantity = $1 WHERE session_id = $2 AND ticker = $3",
                    new_qty, body.session_id, ticker
                )

            # Add cash
            await conn.execute(
                "UPDATE paper_portfolios SET cash_balance = cash_balance + $1 WHERE session_id = $2",
                total, body.session_id
            )

        # Record trade
        await conn.execute("""
            INSERT INTO paper_trades (session_id, ticker, action, quantity, price, total)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, body.session_id, ticker, body.action, body.quantity, price, total)

    return {
        "status": "executed",
        "ticker": ticker,
        "action": body.action,
        "quantity": body.quantity,
        "price": price,
        "total": total,
    }


@router.get("/portfolio/{session_id}", response_model=PortfolioResponse)
async def get_portfolio(
    session_id: str,
    pool=Depends(get_db_pool),
    stock_service=Depends(get_stock_service),
):
    """Get portfolio state with current prices."""
    async with pool.acquire() as conn:
        await ensure_portfolio(conn, session_id)

        cash = await conn.fetchval(
            "SELECT cash_balance FROM paper_portfolios WHERE session_id = $1",
            session_id
        )

        holdings_rows = await conn.fetch(
            "SELECT ticker, quantity, avg_cost FROM paper_holdings WHERE session_id = $1",
            session_id
        )

    # Get current prices
    tickers = [h["ticker"] for h in holdings_rows]
    prices = stock_service.get_prices_batch(tickers) if tickers else {}

    holdings = []
    total_market_value = 0
    total_cost = 0

    for h in holdings_rows:
        price_data = prices.get(h["ticker"])
        current_price = price_data.price if price_data else h["avg_cost"]
        market_value = current_price * h["quantity"]
        cost_basis = h["avg_cost"] * h["quantity"]
        pnl = market_value - cost_basis
        pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0

        total_market_value += market_value
        total_cost += cost_basis

        holdings.append(HoldingResponse(
            ticker=h["ticker"],
            quantity=h["quantity"],
            avg_cost=round(h["avg_cost"], 2),
            current_price=round(current_price, 2),
            market_value=round(market_value, 2),
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 2),
        ))

    total_value = cash + total_market_value
    total_pnl = total_value - STARTING_BALANCE

    return PortfolioResponse(
        session_id=session_id,
        cash_balance=round(cash, 2),
        total_value=round(total_value, 2),
        total_pnl=round(total_pnl, 2),
        holdings=holdings,
    )


@router.get("/history/{session_id}", response_model=list[TradeHistoryItem])
async def get_trade_history(
    session_id: str,
    limit: int = 50,
    pool=Depends(get_db_pool),
):
    """Get trade history for a session."""
    async with pool.acquire() as conn:
        trades = await conn.fetch("""
            SELECT ticker, action, quantity, price, total, executed_at
            FROM paper_trades
            WHERE session_id = $1
            ORDER BY executed_at DESC
            LIMIT $2
        """, session_id, limit)

    return [
        TradeHistoryItem(
            ticker=t["ticker"],
            action=t["action"],
            quantity=t["quantity"],
            price=t["price"],
            total=t["total"],
            executed_at=t["executed_at"],
        )
        for t in trades
    ]
