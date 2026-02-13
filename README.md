# TrendVest AI 🚀

> פלטפורמת AI לגילוי מגמות ומעקב השקעות בעברית

AI-powered trend tracking platform for Israeli retail investors. Identifies trending topics from Reddit & news, maps them to stocks, and explains everything in simple Hebrew.

---

## Quick Start (5 minutes)

### 1. Prerequisites
- Docker & Docker Compose
- Reddit API credentials ([create app here](https://www.reddit.com/prefs/apps))
- NewsAPI key ([register here](https://newsapi.org/register))
- Claude API key ([get here](https://console.anthropic.com))

### 2. Setup
```bash
# Clone and enter project
cd trendvest

# Copy env file and fill in your keys
cp .env.example .env
# Edit .env with your API keys

# Start everything
docker compose up -d

# Seed the database with topics
docker compose exec backend python -c "
import asyncio
from app.models.database import get_pool, init_db
async def seed():
    pool = await get_pool()
    await init_db(pool)
    await pool.close()
asyncio.run(seed())
"
```

### 3. Verify
- API: http://localhost:8000/docs (Swagger UI)
- Health: http://localhost:8000/api/health

### 4. Run Pipeline (first data collection)
```bash
# Collect from Reddit + News + calculate momentum
docker compose exec backend python -m pipeline.collect

# Or collect from specific source
docker compose exec backend python -m pipeline.collect --source reddit
docker compose exec backend python -m pipeline.collect --source news
```

---

## Project Structure

```
trendvest/
├── backend/                  # Python FastAPI
│   ├── app/
│   │   ├── main.py           # FastAPI entry point
│   │   ├── routers/          # API endpoints
│   │   │   ├── trends.py     # /api/trends
│   │   │   ├── stocks.py     # /api/stocks
│   │   │   └── chat.py       # /api/chat
│   │   ├── services/         # Business logic
│   │   │   ├── reddit.py     # Reddit data collector
│   │   │   ├── news.py       # NewsAPI collector
│   │   │   ├── momentum.py   # Momentum calculation
│   │   │   ├── stocks.py     # yfinance price service
│   │   │   └── ai_explainer.py  # Claude AI chat
│   │   ├── models/
│   │   │   ├── database.py   # DB connection & seeding
│   │   │   └── schemas.py    # Pydantic models
│   │   └── data/
│   │       └── topics.json   # 20 topics + keywords + stocks
│   ├── requirements.txt
│   └── Dockerfile
├── pipeline/
│   └── collect.py            # Data collection cron script
├── database/
│   └── 001_schema.sql        # PostgreSQL schema
├── frontend/                 # (Next.js — TBD)
├── docker-compose.yml
├── .env.example
└── README.md
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/trends` | All topics sorted by momentum |
| GET | `/api/trends/:slug` | Single topic details |
| GET | `/api/stocks` | Stock screener (filter/sort) |
| GET | `/api/stocks/:ticker` | Single stock details |
| GET | `/api/stocks/sector/:name` | Stocks by sector |
| POST | `/api/chat` | AI explainer (Hebrew) |
| GET | `/api/chat/remaining` | Check daily question limit |
| GET | `/api/health` | Health check |

## Cron Schedule

```bash
# Reddit collection + momentum (every 30 min)
*/30 * * * * cd /app && python -m pipeline.collect --source reddit

# News collection (every 3 hours — API limit)
0 */3 * * * cd /app && python -m pipeline.collect --source news

# Momentum recalculation (5 min after each collection)
5,35 * * * * cd /app && python -m pipeline.collect --momentum-only
```

## Tech Stack

| Component | Technology | Cost |
|-----------|-----------|------|
| Frontend | Next.js + Tailwind | $0 (Vercel free) |
| Backend | Python FastAPI | $5-20/mo (Railway) |
| Database | PostgreSQL | $0-7/mo (Supabase free) |
| Data | Reddit API + NewsAPI | $0 (free tiers) |
| Prices | yfinance | $0 |
| AI | Claude Haiku | $5-20/mo |

---

⚠️ **Disclaimer:** TrendVest AI is not investment advice. Data is presented for tracking and educational purposes only.
