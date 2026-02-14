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

### Topic Insights System
- [x] Created `backend/app/services/topic_insights.py` — curated insights for 10 topics (AI, nuclear, GLP-1, quantum, EV, cyber, crypto, space, solar, semiconductors)
- [x] Bilingual insights (EN/HE): why trending, stock connections, related topics, hidden cross-sector connections
- [x] AI-powered insight generation via Claude API (with curated fallback when no API key)
- [x] Added `GET /api/trends/{slug}/insight` — topic insight endpoint
- [x] Added `GET /api/trends/{slug}/stock-insight/{ticker}` — stock-topic connection endpoint
- [x] Refactored `backend/app/routers/news.py` — dynamic topic loading from topics.json, NewsAPI integration
- [x] Expanded `frontend/src/components/TopicCard.tsx` — "Why is this trending?" button, insight panel with AI analysis, stock connections, related topics, hidden connections
- [x] Added insight translations to `frontend/src/i18n/translations.ts`
- [x] Added `getTopicInsight()` and `getStockInsight()` API helpers to `frontend/src/lib/api.ts`

### Stock Prices on Dashboard + Enriched Company Profiles
- [x] Injected `StockPriceService` into `trends.py` — `get_trends()` and `get_trend_by_slug()` now fetch live prices via batch call
- [x] Dashboard TopicCards now show `current_price`, `daily_change_pct`, and `previous_close`
- [x] Added `CompanyOfficer` model and expanded `StockProfileResponse` with 15+ new fields (management, financials, growth, analyst)
- [x] Expanded `GET /api/stocks/{ticker}/profile` — returns officers (top 5), margins, ROE, cashflow, debt, beta, revenue/earnings growth, recommendation, target price, analyst count
- [x] Added `CompanyOfficer` interface and expanded `StockProfile` TS interface with all new fields
- [x] Added ~30 new translation keys (HE/EN) for profile tabs, management, financials, analyst, company news
- [x] Redesigned `StockProfile.tsx` with tabbed layout: Overview | Management | Financials | Analyst
- [x] Added Company News section at bottom of profile modal (fetches via existing `getNews({ ticker })`)
- [x] Analyst tab: color-coded recommendation badge, target price, analyst count
- [x] Financials tab: financial health metrics, growth indicators (green/red), valuation with 52-week range bar

### Hebrew Summaries + AI Explain Mode + Screener Enhancements + Related Stocks
- [x] **Hebrew Company Summary**: Profile endpoint accepts `?language=he`, translates summary via Claude API (cached)
- [x] **AI Explain Mode — Backend**: `POST /api/chat/explain-term` and `POST /api/chat/explain-section` endpoints (don't count against daily chat limit)
- [x] **AI Explain Mode — Frontend**: `ExplainTooltip` component wraps financial metric labels (P/E, Beta, etc.) with tap-to-explain popovers
- [x] **AI Explain — Section Summaries**: "AI Explain" button on Financials and Analyst tabs sends actual data for contextual AI summary
- [x] **Screener — Price Range Filter**: Min/max price inputs in filter bar, backend `min_price` query param
- [x] **Screener — Topic Filter**: Topic dropdown populated from trends, backend `topic` query param filters by topic_slug
- [x] **Screener — Search Autocomplete**: Client-side autocomplete dropdown with keyboard navigation (arrow keys + Enter/Escape)
- [x] **Related Stocks**: `GET /api/stocks/{ticker}/related` returns stocks sharing same topics; horizontal scrollable cards in profile modal
- [x] Added ~15 new i18n keys (explain, screener, related stocks)
- [x] Added `RelatedStock` TypeScript interface

## All 29 API Routes
```
GET  /api/health
GET  /api/trends
GET  /api/trends/{slug}
GET  /api/trends/{slug}/insight
GET  /api/trends/{slug}/stock-insight/{ticker}
GET  /api/stocks
GET  /api/stocks/{ticker}
GET  /api/stocks/sector/{sector_name}
GET  /api/stocks/{ticker}/history
GET  /api/stocks/{ticker}/profile
GET  /api/stocks/{ticker}/related
GET  /api/stocks/{ticker}/peers          ← NEW
POST /api/stocks/{ticker}/research       ← NEW
POST /api/chat
GET  /api/chat/remaining
POST /api/chat/explain-term
POST /api/chat/explain-section
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

### Phase 3: Expansion & Deep Research
- [x] **Stock Coverage Expansion**: 48 → 140+ stocks across 33 topics (12 new categories)
  - Banking (JPM, GS, BAC, MS, WFC, C, SCHW)
  - Healthcare & Pharma (JNJ, UNH, PFE, ABT, MRK, TMO)
  - Biotech & mRNA (MRNA, REGN, VRTX, BIIB, GILD)
  - Retail & E-Commerce (WMT, COST, TGT, HD, LOW, SHOP, ETSY, MELI)
  - Oil & Gas (XOM, CVX, COP, SLB, OXY)
  - Consumer Brands (PG, KO, PEP, NKE, MCD, SBUX)
  - Industrials (CAT, GE, HON, UPS, MMM)
  - Gaming & Metaverse (RBLX, EA, TTWO, U)
  - Social Media (META, SNAP, PINS, RDDT)
  - European Markets (ASML, SAP, AZN, SHEL, NVS, UL, DEO, RACE)
  - Asian Markets (BABA, SONY, TM, BIDU, INFY, HDB, SE, GRAB)
  - Israeli Tech (CHKP, MNDY, TEVA, WIX, CYBR, NICE, SEDG, GLBE, INMD, RSKD, LUMI.TA, ICL)
  - Rising Mid-Caps (DKNG, ABNB, DUOL, HIMS, APP, CELH, AXON, MNDY)
  - Expanded existing topics (EV, cyber, defense, fintech, cloud, streaming, etc.)
- [x] **Watchlist News Feed**: Stocks/News tab toggle, aggregated news for all watched tickers with dedup, ticker badges, time ago
- [x] **Peer Comparison**: `GET /api/stocks/{ticker}/peers` — sector peers with market cap, P/E, beta, margins, institutional %, short ratio, revenue growth. Peers tab in StockProfile
- [x] **Staff AI Bios**: `generate_officer_bio()` in ai_explainer.py — Claude-powered 1-2 sentence bios, cached, bilingual. Shown in Management tab
- [x] **Deep Research (Perplexity)**: `POST /api/stocks/{ticker}/research` — Perplexity sonar API with yfinance fallback. Purple "Deep Research" button in profile modal, citations display
- [x] Added ~10 new i18n keys (peers, research, watchlist tabs)

### RAM Optimizations
- [x] **StockPriceService cache limits**: Max 200 entries, evicts oldest by `fetched_at`, auto-cleans entries >15min old
- [x] **Chunked batch downloads**: yfinance batches split into chunks of 30 tickers (down from 140+ in one call), reduces peak RAM
- [x] **AIExplainer cache limits**: Max 500 entries with insertion-order eviction; stale `_daily_usage` entries auto-cleaned on next rate-limit check
- [x] **Lazy-loaded topic insights**: `TOPIC_INSIGHTS`, `RELATED_TOPICS`, `HIDDEN_CONNECTIONS` loaded on first access instead of module import (~200KB saved)

### Workflow Notes
- Use `/compact` periodically in Claude Code to compress context
- Keep sessions to 1-2 features max to prevent RAM/context buildup
- Commit after each feature, save plans to PROGRESS.md for crash recovery

## Operational Next Steps
- [ ] Add Reddit/NewsAPI/Anthropic/X/Perplexity API keys for live data
- [ ] Run pipeline to collect real mention data
- [ ] Deploy to cloud (Vercel frontend + Railway/Render backend)
