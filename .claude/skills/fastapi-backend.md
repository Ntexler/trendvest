# FastAPI Backend Development — TrendVest

## Overview
The backend is a Python FastAPI application serving the TrendVest AI platform API. It provides endpoints for trend tracking, stock screening, AI chat, paper trading, news, auth, and personalized recommendations.

## Architecture

### Entry Point
- `backend/app/main.py` — FastAPI app with lifespan (DB pool init, cache warmup, shutdown)
- Runs via: `uvicorn app.main:app --reload --port 8000`
- Docker: `docker compose exec backend ...`

### Directory Structure
```
backend/app/
├── main.py              # FastAPI app, lifespan, CORS, router registration
├── deps.py              # Dependency injection (db_pool, stock_service singletons)
├── routers/             # API endpoint modules
│   ├── trends.py        # /api/trends — topics sorted by momentum
│   ├── stocks.py        # /api/stocks — screener, profile, history, peers, research
│   ├── chat.py          # /api/chat — AI explainer (Claude)
│   ├── paper_trading.py # /api/paper — demo trading
│   ├── news.py          # /api/news — news feed
│   ├── auth.py          # /api/auth — user registration/login
│   └── recommendations.py # /api/recommendations — personalized suggestions
├── services/            # Business logic layer
│   ├── reddit.py        # Reddit API data collector
│   ├── news.py          # NewsAPI collector
│   ├── google_trends.py # Google Trends collector
│   ├── x_twitter.py     # X/Twitter collector
│   ├── momentum.py      # Momentum score calculation
│   ├── stocks.py        # yfinance price service with caching
│   ├── ai_explainer.py  # Claude AI chat, translation, term/section explanation
│   └── topic_insights.py # AI-generated topic insights
├── models/
│   ├── database.py      # asyncpg pool creation, DB seeding from topics.json
│   └── schemas.py       # Pydantic models (request/response schemas)
└── data/
    └── topics.json      # 20+ topics with keywords, subreddits, stocks mapping
```

### Key Patterns

#### Dependency Injection
Dependencies are managed via `deps.py`:
```python
from ..deps import get_db_pool, get_stock_service

@router.get("/endpoint")
async def handler(pool=Depends(get_db_pool), stock_service=Depends(get_stock_service)):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT ...")
```

#### Database Access
- Uses `asyncpg` directly (no ORM)
- Connection pool acquired via `pool.acquire()` context manager
- Parameterized queries: `$1`, `$2`, etc.
- Schema in `database/001_schema.sql`

#### Router Pattern
Each router:
1. Creates `APIRouter(prefix="/api/<resource>", tags=["<tag>"])`
2. Defines endpoints with Pydantic response models
3. Uses `Depends()` for db pool and stock service

#### Adding a New Endpoint
1. Add Pydantic models to `models/schemas.py`
2. Create or extend a router in `routers/`
3. Register the router in `main.py`: `app.include_router(my_router.router)`
4. Add service logic in `services/` if needed

#### Stock Price Service
`StockPriceService` wraps yfinance with an in-memory cache:
- `get_price(ticker)` — single stock
- `get_prices_batch(tickers)` — batch fetch with TTL cache
- Returns `PriceData(price, change_pct, previous_close)`

### Database Schema (PostgreSQL 16)
Core tables:
- `topics` — trending topics (slug, name_en, name_he, sector, keywords, subreddits)
- `topic_stocks` — stocks linked to topics (ticker, company_name, relevance_note, priority)
- `topic_mentions` — mention counts per source per time period
- `momentum_scores` — calculated momentum per topic (score, direction, mention counts)
- `users` — auth (email, password_hash, tier: free/pro)
- `watchlist_items` — user watchlists
- `paper_portfolios/trades/holdings` — paper trading state

### Environment Variables
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/trendvest
REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / REDDIT_USER_AGENT
NEWS_API_KEY
ANTHROPIC_API_KEY
PERPLEXITY_API_KEY (optional, for deep research)
CORS_ORIGINS
```

### Testing & Running
```bash
# Start full stack
docker compose up -d

# Run backend only
cd backend && uvicorn app.main:app --reload --port 8000

# Seed database
docker compose exec backend python -c "..."

# API docs
http://localhost:8000/docs
```
