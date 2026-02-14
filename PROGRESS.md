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

## All 27 API Routes
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

## Phase 3: Expansion & Deep Research (Planned)

### Feature 1: Expand Stock Coverage (100+ stocks, US + Global)
- [ ] **More US sectors**: Big banks (JPM, GS, BAC, MS), Healthcare (JNJ, PFE, UNH, ABT, MRK), Retail (WMT, COST, TGT, HD), Energy (XOM, CVX, COP, SLB), Tech megacaps (META, ORCL, CRM, ADBE, INTC), Consumer (PG, KO, PEP, NKE, MCD), Industrials (CAT, DE, GE, HON, UPS)
- [ ] **Lesser-known / mid-cap US stocks**: PLTR, DKNG, RBLX, CRWD, ZS, NET, SNOW, MELI, SE, SHOP, SQ, ABNB, RIVN, LCID, SOFI, HOOD, COIN, MARA, RIOT, AFRM
- [ ] **European stocks** (via ADRs or exchange suffixes): ASML, SAP, NOVO-B (Novo Nordisk), NESN (Nestle), AZN (AstraZeneca), SHEL (Shell), TTE (TotalEnergies), SIEGY (Siemens)
- [ ] **Asian stocks** (via ADRs): BABA, TSM, SONY, TM (Toyota), BIDU, NIO, LI, XPEV, INFY, HDB
- [ ] Add new topic categories for new sectors (Banking, Healthcare, Energy, Consumer, etc.)
- [ ] Update `topics.json` and `stock_topics.json` with new tickers + topic mappings
- [ ] yfinance already supports international tickers

### Feature 2: Staff Member AI Summaries
- [ ] Management tab currently shows officers with just name + title
- [ ] Use Claude API to generate 1-2 sentence professional bio from name + title + company
- [ ] Add `generate_officer_bio()` to `ai_explainer.py`
- [ ] Cache generated bios per officer name
- [ ] Show bios in Management tab of `StockProfile.tsx`
- [ ] Support bilingual (HE/EN)

### Feature 3: Watchlist News Feed
- [ ] Watchlist page (`Watchlist.tsx`) currently shows just prices
- [ ] Add a "News" tab/section to the Watchlist page
- [ ] Fetch news for all watched tickers via existing `/api/news?ticker=X`
- [ ] Aggregate, deduplicate, and sort by date
- [ ] Show ticker badge per news item
- [ ] i18n support

### Feature 4: Peer Comparison + Richer Financial Data
- [ ] New endpoint: `GET /api/stocks/{ticker}/peers` — returns same-sector stocks with key metrics
- [ ] New yfinance data fields: institutional ownership %, short interest, insider transactions, earnings date
- [ ] Frontend: "Peers" tab in StockProfile with comparison table
- [ ] Color-coded metrics (better/worse than peers)
- [ ] i18n support

### Feature 5: AI Deep Research (Perplexity Integration)
- [ ] Integrate Perplexity API (sonar model) for web-searched real-time analysis
- [ ] New endpoint: `POST /api/stocks/{ticker}/research` — calls Perplexity for latest analysis
- [ ] Show results with source citations and links
- [ ] "Deep Research" button per stock in profile modal
- [ ] Rate-limit (expensive API) — e.g., 5/day per session
- [ ] Add `PERPLEXITY_API_KEY` to `.env`

### Implementation Priority
1. Expand Stock Coverage (most visible impact)
2. Watchlist News Feed
3. Peer Comparison + Richer Data
4. Staff Member AI Bios
5. Perplexity Deep Research

---

## Operational Next Steps
- [ ] Add Reddit/NewsAPI/Anthropic/X API keys for live data
- [ ] Run pipeline to collect real mention data
- [ ] Deploy to cloud (Vercel frontend + Railway/Render backend)
