"""
Stocks API endpoints for TrendVest — search, screener, prices, history, profile, peers, research.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from datetime import datetime, timezone
from ..models.schemas import StockDetail, StockProfileResponse, CompanyOfficer, PeerStock, ResearchResponse
from ..deps import get_db_pool, get_stock_service
from ..services.ai_explainer import AIExplainer

_explainer = AIExplainer()

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("", response_model=list[StockDetail])
async def screener(
    sector: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    topic: Optional[str] = Query(None),
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

    if topic:
        unique_stocks = [s for s in unique_stocks if s["topic_slug"] == topic]

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

        if min_price and price and price < min_price:
            continue
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
async def get_stock_profile(
    ticker: str,
    language: Optional[str] = Query(None),
):
    """Get enriched company profile: overview, management, financials, analyst data."""
    try:
        import yfinance as yf
    except ImportError:
        raise HTTPException(status_code=503, detail="yfinance not available")

    ticker = ticker.upper()
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # Extract top 5 officers with AI-generated bios
        company_name = info.get("longName") or info.get("shortName", ticker)
        officers = []
        for officer in (info.get("companyOfficers") or [])[:5]:
            oname = officer.get("name", "")
            otitle = officer.get("title", "")
            bio = await _explainer.generate_officer_bio(
                oname, otitle, company_name, language or "en"
            )
            officers.append(CompanyOfficer(
                name=oname,
                title=otitle,
                age=officer.get("age"),
                total_pay=officer.get("totalPay"),
                bio=bio,
            ))

        summary = info.get("longBusinessSummary", "")
        if language == "he" and summary:
            summary = await _explainer.translate_text(summary, "he", ticker)

        return StockProfileResponse(
            ticker=ticker,
            name=info.get("longName") or info.get("shortName", ticker),
            summary=summary,
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


@router.get("/{ticker}/related")
async def get_related_stocks(
    ticker: str,
    pool=Depends(get_db_pool),
    stock_service=Depends(get_stock_service),
):
    """Get stocks related to this ticker via shared topics."""
    ticker = ticker.upper()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT DISTINCT ts2.ticker, ts2.company_name, t.name_he as topic,
                   t.slug as topic_slug, ts2.relevance_note
            FROM topic_stocks ts1
            JOIN topics t ON ts1.topic_id = t.id
            JOIN topic_stocks ts2 ON ts2.topic_id = t.id
            WHERE ts1.ticker = $1
              AND ts2.ticker != $1
              AND t.is_active = true
            ORDER BY ts2.ticker
        """, ticker)

    if not rows:
        return []

    seen = set()
    unique = []
    for r in rows:
        if r["ticker"] not in seen:
            seen.add(r["ticker"])
            unique.append(r)

    tickers = [r["ticker"] for r in unique]
    prices = stock_service.get_prices_batch(tickers)

    results = []
    for r in unique:
        pd = prices.get(r["ticker"])
        results.append({
            "ticker": r["ticker"],
            "company_name": r["company_name"],
            "topic": r["topic"],
            "relevance_note": r["relevance_note"] or "",
            "current_price": pd.price if pd else None,
            "daily_change_pct": pd.change_pct if pd else None,
        })

    return results


@router.get("/{ticker}/peers", response_model=list[PeerStock])
async def get_peer_stocks(
    ticker: str,
    pool=Depends(get_db_pool),
    stock_service=Depends(get_stock_service),
):
    """Get peer stocks from the same sector with comparison metrics."""
    try:
        import yfinance as yf
    except ImportError:
        raise HTTPException(status_code=503, detail="yfinance not available")

    ticker = ticker.upper()

    # Find the sector of the target stock
    async with pool.acquire() as conn:
        target = await conn.fetchrow("""
            SELECT t.sector_en FROM topic_stocks ts
            JOIN topics t ON ts.topic_id = t.id
            WHERE ts.ticker = $1 LIMIT 1
        """, ticker)

        if not target:
            raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")

        # Find other stocks in same sector
        peers = await conn.fetch("""
            SELECT DISTINCT ts.ticker, ts.company_name
            FROM topic_stocks ts
            JOIN topics t ON ts.topic_id = t.id
            WHERE t.sector_en = $1 AND ts.ticker != $2
            ORDER BY ts.ticker
            LIMIT 10
        """, target["sector_en"], ticker)

    if not peers:
        return []

    peer_tickers = [p["ticker"] for p in peers]
    prices = stock_service.get_prices_batch(peer_tickers)

    results = []
    for p in peers:
        pd = prices.get(p["ticker"])
        try:
            info = yf.Ticker(p["ticker"]).info
        except Exception:
            info = {}

        results.append(PeerStock(
            ticker=p["ticker"],
            company_name=p["company_name"],
            current_price=pd.price if pd else None,
            daily_change_pct=pd.change_pct if pd else None,
            market_cap=info.get("marketCap"),
            pe_ratio=info.get("trailingPE"),
            beta=info.get("beta"),
            dividend_yield=info.get("dividendYield"),
            profit_margins=info.get("profitMargins"),
            revenue_growth=info.get("revenueGrowth"),
            institutional_pct=info.get("heldPercentInstitutions"),
            short_ratio=info.get("shortRatio"),
        ))

    return results


@router.post("/{ticker}/research", response_model=ResearchResponse)
async def deep_research(ticker: str, language: str = Query("en")):
    """Deep research via Perplexity API — real-time web-searched analysis."""
    import os
    import httpx

    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        try:
            import yfinance as yf
            info = yf.Ticker(ticker.upper()).info
            name = info.get("longName", ticker)
            sector = info.get("sector", "")
            industry = info.get("industry", "")
            summary = info.get("longBusinessSummary", "")
            rec = info.get("recommendationKey", "N/A")
            target_price = info.get("targetMeanPrice", "N/A")
            analysts = info.get("numberOfAnalystOpinions", "N/A")

            analysis = (
                f"**{name} ({ticker.upper()})** - {sector} / {industry}\n\n"
                f"{summary[:500]}{'...' if len(summary) > 500 else ''}\n\n"
                f"**Analyst Consensus:** {rec} | **Target Price:** ${target_price} | **Analysts:** {analysts}\n\n"
                f"_Note: Connect a Perplexity API key for real-time web-searched deep research._"
            )
        except Exception:
            analysis = f"Deep research for {ticker.upper()} requires a Perplexity API key. Add PERPLEXITY_API_KEY to your .env file."

        return ResearchResponse(
            ticker=ticker.upper(),
            analysis=analysis,
            citations=[],
            generated_at=datetime.now(timezone.utc),
        )

    prompt = (
        f"Provide a comprehensive investment research analysis for the stock {ticker.upper()}. "
        f"Include: 1) Recent news and developments, 2) Financial performance, "
        f"3) Competitive position, 4) Key risks, 5) Analyst outlook. "
        f"Be concise but thorough."
    )
    if language == "he":
        prompt += " Respond in Hebrew."

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "sonar",
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            citations = [{"url": c} for c in data.get("citations", [])]

            return ResearchResponse(
                ticker=ticker.upper(),
                analysis=content,
                citations=citations,
                generated_at=datetime.now(timezone.utc),
            )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Research API error: {str(e)}")
