"""
Stocks API endpoints for TrendVest — search, screener, prices, history, profile.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from ..models.schemas import StockDetail, StockProfileResponse, CompanyOfficer
from ..deps import get_db_pool, get_stock_service

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("", response_model=list[StockDetail])
async def screener(
    sector: Optional[str] = Query(None),
    max_price: Optional[float] = Query(None),
    sort_by: str = Query("change", pattern="^(change|price|name)$"),
    search: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    pool=Depends(get_db_pool),
    stock_service=Depends(get_stock_service),
):
    """Stock screener — filter and sort stocks."""
    async with pool.acquire() as conn:
        stocks = await conn.fetch("""
            SELECT ts.ticker, ts.company_name, ts.relevance_note,
                   t.sector, t.sector_en, t.name_he as topic, t.slug as topic_slug
            FROM topic_stocks ts
            JOIN topics t ON ts.topic_id = t.id
            WHERE t.is_active = true
            ORDER BY ts.priority
        """)

    seen = set()
    unique_stocks = []
    for s in stocks:
        if s["ticker"] not in seen:
            seen.add(s["ticker"])
            unique_stocks.append(s)

    if sector:
        unique_stocks = [s for s in unique_stocks if s["sector"] == sector or s["sector_en"] == sector]

    if search:
        q = search.lower()
        unique_stocks = [s for s in unique_stocks
                         if q in s["ticker"].lower() or q in s["company_name"].lower()]

    tickers = [s["ticker"] for s in unique_stocks]
    prices = stock_service.get_prices_batch(tickers)

    results = []
    for s in unique_stocks:
        price_data = prices.get(s["ticker"])
        price = price_data.price if price_data else None
        change_pct = price_data.change_pct if price_data else None
        prev_close = price_data.previous_close if price_data else None

        if max_price and price and price > max_price:
            continue

        results.append(StockDetail(
            ticker=s["ticker"],
            company_name=s["company_name"],
            sector=s["sector"],
            topic=s["topic"],
            topic_slug=s["topic_slug"],
            relevance_note=s["relevance_note"] or "",
            current_price=price,
            daily_change_pct=change_pct,
            previous_close=prev_close,
        ))

    if sort_by == "change":
        results.sort(key=lambda x: x.daily_change_pct or 0, reverse=True)
    elif sort_by == "price":
        results.sort(key=lambda x: x.current_price or 999999)
    elif sort_by == "name":
        results.sort(key=lambda x: x.ticker)

    return results[offset:offset + limit]


@router.get("/{ticker}", response_model=StockDetail)
async def get_stock(
    ticker: str,
    pool=Depends(get_db_pool),
    stock_service=Depends(get_stock_service),
):
    """Get a single stock's details and current price."""
    ticker = ticker.upper()
    async with pool.acquire() as conn:
        stock = await conn.fetchrow("""
            SELECT ts.ticker, ts.company_name, ts.relevance_note,
                   t.sector, t.name_he as topic, t.slug as topic_slug
            FROM topic_stocks ts
            JOIN topics t ON ts.topic_id = t.id
            WHERE ts.ticker = $1
            LIMIT 1
        """, ticker)

    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")

    price_data = stock_service.get_price(ticker)

    return StockDetail(
        ticker=stock["ticker"],
        company_name=stock["company_name"],
        sector=stock["sector"],
        topic=stock["topic"],
        topic_slug=stock["topic_slug"],
        relevance_note=stock["relevance_note"] or "",
        current_price=price_data.price if price_data else None,
        daily_change_pct=price_data.change_pct if price_data else None,
        previous_close=price_data.previous_close if price_data else None,
    )


@router.get("/sector/{sector_name}", response_model=list[StockDetail])
async def get_stocks_by_sector(
    sector_name: str,
    pool=Depends(get_db_pool),
    stock_service=Depends(get_stock_service),
):
    """Get all stocks in a sector."""
    async with pool.acquire() as conn:
        stocks = await conn.fetch("""
            SELECT ts.ticker, ts.company_name, ts.relevance_note,
                   t.sector, t.name_he as topic, t.slug as topic_slug
            FROM topic_stocks ts
            JOIN topics t ON ts.topic_id = t.id
            WHERE (t.sector = $1 OR t.sector_en = $1) AND t.is_active = true
            ORDER BY ts.priority
        """, sector_name)

    tickers = list(set(s["ticker"] for s in stocks))
    prices = stock_service.get_prices_batch(tickers)

    return [
        StockDetail(
            ticker=s["ticker"],
            company_name=s["company_name"],
            sector=s["sector"],
            topic=s["topic"],
            topic_slug=s["topic_slug"],
            relevance_note=s["relevance_note"] or "",
            current_price=prices.get(s["ticker"], None) and prices[s["ticker"]].price,
            daily_change_pct=prices.get(s["ticker"], None) and prices[s["ticker"]].change_pct,
        )
        for s in stocks
    ]


@router.get("/{ticker}/history")
async def get_stock_history(
    ticker: str,
    period: str = Query("1mo", pattern="^(1mo|3mo|6mo|1y)$"),
):
    """Get stock price history for charts."""
    try:
        import yfinance as yf
    except ImportError:
        raise HTTPException(status_code=503, detail="yfinance not available")

    ticker = ticker.upper()
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No history for {ticker}")

        data = []
        for date_idx, row in hist.iterrows():
            data.append({
                "date": date_idx.strftime("%Y-%m-%d"),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]) if row["Volume"] else 0,
            })
        return {"ticker": ticker, "period": period, "data": data}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ticker}/profile", response_model=StockProfileResponse)
async def get_stock_profile(ticker: str):
    """Get enriched company profile: overview, management, financials, analyst data."""
    try:
        import yfinance as yf
    except ImportError:
        raise HTTPException(status_code=503, detail="yfinance not available")

    ticker = ticker.upper()
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # Extract top 5 officers
        officers = []
        for officer in (info.get("companyOfficers") or [])[:5]:
            officers.append(CompanyOfficer(
                name=officer.get("name", ""),
                title=officer.get("title", ""),
                age=officer.get("age"),
                total_pay=officer.get("totalPay"),
            ))

        return StockProfileResponse(
            ticker=ticker,
            name=info.get("longName") or info.get("shortName", ticker),
            summary=info.get("longBusinessSummary", ""),
            sector=info.get("sector", ""),
            industry=info.get("industry", ""),
            employees=info.get("fullTimeEmployees"),
            website=info.get("website", ""),
            market_cap=info.get("marketCap"),
            pe_ratio=info.get("trailingPE"),
            dividend_yield=info.get("dividendYield"),
            fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
            fifty_two_week_low=info.get("fiftyTwoWeekLow"),
            country=info.get("country", ""),
            city=info.get("city", ""),
            exchange=info.get("exchange", ""),
            quote_type=info.get("quoteType", ""),
            officers=officers,
            profit_margins=info.get("profitMargins"),
            operating_margins=info.get("operatingMargins"),
            return_on_equity=info.get("returnOnEquity"),
            free_cashflow=info.get("freeCashflow"),
            total_debt=info.get("totalDebt"),
            total_cash=info.get("totalCash"),
            beta=info.get("beta"),
            revenue_growth=info.get("revenueGrowth"),
            earnings_growth=info.get("earningsGrowth"),
            recommendation_key=info.get("recommendationKey"),
            target_mean_price=info.get("targetMeanPrice"),
            number_of_analysts=info.get("numberOfAnalystOpinions"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
