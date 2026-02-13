"""
TrendVest AI — Main FastAPI Application
========================================
API server for the TrendVest trend-tracking platform.

Run:
    uvicorn app.main:app --reload --port 8000
"""
import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from .models.database import get_pool, init_db
from .models.schemas import HealthResponse
from .services.stocks import StockPriceService

# ── Services (singletons) ──
db_pool = None
stock_service = StockPriceService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB pool and seed data. Shutdown: close pool."""
    global db_pool
    print("\n🚀 Starting TrendVest API...")
    db_pool = await get_pool()
    await init_db(db_pool)
    print("✅ Database ready")
    print("✅ TrendVest API is running!\n")
    yield
    await db_pool.close()
    print("\n👋 TrendVest API shutting down")


app = FastAPI(
    title="TrendVest AI API",
    description="API for trend tracking and stock screening platform",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Dependency Injection ──
async def get_db_pool():
    return db_pool


async def get_stock_service():
    return stock_service


# ── Import and register routers ──
from .routers import trends, stocks, chat

# Override dependencies for routers
app.dependency_overrides[trends.router.dependencies] = None

# We need to wire up the pool dependency — use a simple approach:
# Each router endpoint that needs `pool` will get it via Depends()
# We override at the app level

# Register routers
app.include_router(trends.router)
app.include_router(stocks.router)
app.include_router(chat.router)


# ── Override default Depends() calls ──
# This is a workaround since routers use Depends() without explicit functions
# In production, use proper dependency injection
from fastapi import Request


@app.middleware("http")
async def inject_dependencies(request: Request, call_next):
    """Inject pool and services into request state."""
    request.state.pool = db_pool
    request.state.stock_service = stock_service
    return await call_next(request)


# ── Health Check ──
@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    topics_count = 0
    last_run = None

    if db_pool:
        async with db_pool.acquire() as conn:
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
