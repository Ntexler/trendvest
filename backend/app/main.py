"""
TrendVest AI — Main FastAPI Application
========================================
Run:
    uvicorn app.main:app --reload --port 8000
"""
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .models.database import get_pool, init_db
from .models.schemas import HealthResponse
from .services.stocks import StockPriceService
from . import deps


# ── Rate Limiting Middleware ──

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    In-memory sliding window rate limiter.
    - General API: 100 requests per minute per IP
    - Auth endpoints: 10 requests per minute per IP
    - Admin/Agent write: 20 requests per minute per IP
    """

    def __init__(self, app):
        super().__init__(app)
        self.requests: dict[str, list[float]] = defaultdict(list)
        self.limits = {
            "auth": (10, 60),      # 10 req / 60s
            "admin": (20, 60),     # 20 req / 60s
            "agent_write": (20, 60),  # 20 req / 60s
            "general": (100, 60),  # 100 req / 60s
        }

    def _get_bucket(self, path: str, method: str) -> str:
        if path.startswith("/api/auth/"):
            return "auth"
        if path.startswith("/api/admin/"):
            return "admin"
        if path.startswith("/api/agent/") and method in ("POST", "PUT", "DELETE"):
            return "agent_write"
        return "general"

    def _clean_old(self, key: str, window: float):
        now = time.time()
        self.requests[key] = [t for t in self.requests[key] if now - t < window]

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        bucket = self._get_bucket(request.url.path, request.method)
        max_requests, window = self.limits[bucket]

        key = f"{client_ip}:{bucket}"
        self._clean_old(key, window)

        if len(self.requests[key]) >= max_requests:
            return Response(
                content='{"detail":"Rate limit exceeded. Please slow down."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(window)},
            )

        self.requests[key].append(time.time())
        response = await call_next(request)
        return response


# ── Security Headers Middleware ──

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # Don't expose server info
        response.headers.pop("server", None)
        return response


# ── App Setup ──

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
    # Don't expose docs in production
    docs_url="/docs" if os.getenv("ENV", "development") != "production" else None,
    redoc_url="/redoc" if os.getenv("ENV", "development") != "production" else None,
)

# CORS — locked to specific origins
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Add security middlewares
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)

# Register routers
from .routers import trends, stocks, chat
from .routers import paper_trading, news as news_router, auth, recommendations, feed
from .routers import agent as agent_router
from .routers import admin as admin_router

app.include_router(trends.router)
app.include_router(stocks.router)
app.include_router(chat.router)
app.include_router(paper_trading.router)
app.include_router(news_router.router)
app.include_router(auth.router)
app.include_router(recommendations.router)
app.include_router(agent_router.router)
app.include_router(feed.router)
app.include_router(admin_router.router)


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
