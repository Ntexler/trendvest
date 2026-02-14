"""
TrendVest AI — Main FastAPI Application
========================================
Run:
    uvicorn app.main:app --reload --port 8000
"""
import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .models.database import get_pool, init_db
from .models.schemas import HealthResponse
from .services.stocks import StockPriceService
from . import deps


async def _warmup_cache(pool, stock_service: StockPriceService):
    """Pre-fetch all stock prices in background so first page load is fast."""
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT DISTINCT ticker FROM topic_stocks")
        tickers = [r["ticker"] for r in rows]
        if tickers:
            print(f"  Warming price cache for {len(tickers)} tickers...")
            stock_service.get_prices_batch(tickers)
            print(f"  Cache warm: {len(stock_service._cache)} prices loaded")
    except Exception as e:
        print(f"  Cache warmup failed (non-fatal): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB pool and seed data. Shutdown: close pool."""
    print("\n Starting TrendVest API...")
    pool = await get_pool()
    await init_db(pool)
    deps.set_db_pool(pool)
    stock_service = StockPriceService()
    deps.set_stock_service(stock_service)
    print("Database ready")
    await _warmup_cache(pool, stock_service)
    print("TrendVest API is running!\n")
    yield
    await pool.close()
    print("\nTrendVest API shutting down")


app = FastAPI(
    title="TrendVest AI API",
    description="API for trend tracking and stock screening platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
from .routers import trends, stocks, chat
from .routers import paper_trading, news as news_router, auth, recommendations

app.include_router(trends.router)
app.include_router(stocks.router)
app.include_router(chat.router)
app.include_router(paper_trading.router)
app.include_router(news_router.router)
app.include_router(auth.router)
app.include_router(recommendations.router)


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    pool = deps._db_pool
    topics_count = 0
    last_run = None
    if pool:
        async with pool.acquire() as conn:
            topics_count = await conn.fetchval("SELECT COUNT(*) FROM topics WHERE is_active = true") or 0
            last_run = await conn.fetchval("SELECT MAX(updated_at) FROM momentum_scores")
    return HealthResponse(
        status="ok",
        version="1.0.0",
        timestamp=datetime.now(timezone.utc),
        topics_count=topics_count,
        last_pipeline_run=last_run,
    )


@app.get("/")
async def root():
    return {
        "name": "TrendVest AI API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }
