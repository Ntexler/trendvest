# TrendVest AI — Progress

## Completed

### Phase 1: Backend Setup & Fixes
- [x] Project copied to `C:/Users/USER/trendvest`, git init
- [x] Python venv created, all dependencies installed
- [x] `.env` configured with PostgreSQL credentials
- [x] PostgreSQL `trendvest` database created (password reset to 'postgres')
- [x] Created `backend/app/deps.py` — proper dependency injection
- [x] Fixed `main.py` — removed broken `dependency_overrides`, added dotenv, proper lifespan
- [x] Fixed `trends.py` — `Depends()` → `Depends(get_db_pool)`
- [x] Fixed `stocks.py` — all `Depends()` calls fixed, added `/history` and `/profile` endpoints
- [x] Fixed `chat.py` — passes `language` parameter to AI explainer
- [x] Fixed `database.py` — added dotenv loading
- [x] Fixed `collect.py` — added dotenv loading
- [x] Updated `schemas.py` — added language field, auth, trading, tracking models
- [x] Updated `ai_explainer.py` — bilingual (HE/EN) support, graceful fallback without API key
- [x] Updated `001_schema.sql` — added users, watchlist, paper trading, user tracking tables

### Phase 1.9: Authentication & Security
- [x] Created `auth.py` router — register, login, refresh, me endpoints (JWT-based)
- [x] Password hashing with bcrypt (passlib)
- [x] JWT tokens with python-jose

### Phase 1.10: User Learning & Recommendations
- [x] Created `recommendations.py` router — track interactions, get recommendations
- [x] Interest scoring based on user behavior (views, clicks, searches)

### Phase 1.11: New API Endpoints
- [x] Created `news.py` router — news feed from yfinance (free, no API key needed)
- [x] Created `paper_trading.py` router — full mock trading (buy/sell, portfolio, history)
- [x] Stock history endpoint for charts (`GET /api/stocks/{ticker}/history`)
- [x] Stock profile endpoint for "Read More" (`GET /api/stocks/{ticker}/profile`)

### Phase 2: Next.js Frontend
- [x] Created Next.js 15 app with TypeScript + Tailwind CSS v4
- [x] i18n system (HE/EN toggle) with React context
- [x] API proxy via Next.js rewrites
- [x] **Page 1 — Dashboard**: Topics grid, top movers, sector filters, expandable topic cards
- [x] **Page 2 — News Feed**: Headline cards with images, source, ticker badges
- [x] **Page 3 — Screener**: Search, sort, stock list with prices and watchlist toggle
- [x] **Page 4 — Watchlist**: Summary card, stock list with remove button
- [x] **Page 5 — Practice Trading**: Portfolio overview, holdings, trade history, TradeModal
- [x] **Page 6 — Stock Detail**: Price chart (recharts), company profile modal, trade/watchlist buttons
- [x] **Floating AI Chatbot**: Chat panel with message bubbles, suggestions, rate limit counter
- [x] Mobile-first responsive design with bottom nav bar
- [x] Dark theme (#0a0e17 background)
- [x] RTL support for Hebrew

## All 24 API Routes
```
GET  /api/health
GET  /api/trends
GET  /api/trends/{slug}
GET  /api/stocks
GET  /api/stocks/{ticker}
GET  /api/stocks/sector/{sector_name}
GET  /api/stocks/{ticker}/history
GET  /api/stocks/{ticker}/profile
POST /api/chat
GET  /api/chat/remaining
POST /api/paper/trade
GET  /api/paper/portfolio/{session_id}
GET  /api/paper/history/{session_id}
GET  /api/news
POST /api/auth/register
POST /api/auth/login
POST /api/auth/refresh
GET  /api/auth/me
POST /api/track
GET  /api/recommendations
```

## How to Run
```bash
# Backend
cd trendvest/backend
../venv/Scripts/uvicorn app.main:app --reload --port 8000

# Frontend
cd trendvest/frontend
npm run dev
```

### Data Sources: Google Trends & X (Twitter)
- [x] Created `backend/app/services/google_trends.py` — pytrends-based interest scoring + related queries
- [x] Created `backend/app/services/x_twitter.py` — X API v2 mention counts + recent tweets
- [x] Updated `pipeline/collect.py` — added Google Trends and X as collection sources
- [x] Updated `database/001_schema.sql` — source CHECK includes 'x'
- [x] Created `database/002_add_x_source.sql` — migration for existing databases
- [x] Updated `backend/app/routers/news.py` — news feed now includes X tweets and Google Trends related queries
- [x] Updated `frontend/src/components/NewsFeed.tsx` — source filter chips (All/News/X/Trends) + badges + tweet engagement (likes/retweets)
- [x] Added `pytrends` to requirements.txt, `X_BEARER_TOKEN` to `.env`
- [x] Pipeline supports: `--source reddit`, `--source news`, `--source google_trends`, `--source x`

## Next Steps
- [ ] Add Reddit/NewsAPI/Anthropic/X API keys for live data
- [ ] Run pipeline to collect real mention data
- [ ] Deploy to cloud (Vercel frontend + Railway/Render backend)
