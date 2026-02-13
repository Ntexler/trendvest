# TrendVest AI — סטטוס פרויקט
**עדכון אחרון:** 13 פברואר 2026  
**גרסת מסמך חזון:** 2.0

---

## 🎯 מה זה TrendVest AI?
פלטפורמת AI בעברית שמזהה נושאים טרנדיים מרשתות חברתיות וחדשות, ממפה אותם למניות, ומציגה דשבורד חכם למשקיע מתחיל. **כלי מעקב וחינוך — לא כלי מסחר או ניבוי.**

## 📐 גישת MVP
- **20 נושאים/סקטורים מוגדרים מראש** (AI, EV, nuclear, GLP-1, quantum וכו')
- Keywords מוגדרים מראש לכל נושא (לא topic detection אוטומטי)
- ספירת אזכורים + חישוב מומנטום = מדיד ואמין
- מניות ממופות מראש לכל נושא (טבלת lookup, לא AI)
- LLM רק להסברים ולסיכומים

## 📅 תוכנית עבודה ומצב נוכחי

| שלב | שבועות | מטרה | סטטוס |
|------|--------|------|--------|
| 1. Validation | 1-2 | סקר + Landing page, יעד: 200 נרשמים | ⬜ טרם התחיל |
| 2. Data Pipeline | 2-4 | סקריפט Reddit + מומנטום + DB | ✅ **קוד מוכן** — צריך להריץ |
| 3. MVP Frontend | 4-7 | דשבורד + מסנן + Watchlist + AI Chat | 🟡 **פרוטוטיפ מוכן** (mock data) — צריך לחבר ל-API |
| 4. Launch + Iterate | 7-10 | Deploy + פידבק אמיתי | ⬜ טרם התחיל |
| 5. Monetization | חודשים 3-6 | Auth + Free/Pro tiers + Stripe | ⬜ טרם התחיל |

## 🏗 מצב פיתוח נוכחי — פירוט

### ✅ מה מוכן (קוד כתוב):
- **מסמך חזון מוצר v2.0** — כולל תחזיות ריאליסטיות
- **מסמך Technical Roadmap** — 14 פרקים, DB schema, API reference, deployment
- **Frontend prototype (JSX)** — 4 מסכים עם mock data:
  - דשבורד מגמות (20 נושאים, מומנטום, top movers, פילטר סקטור)
  - סורק מניות (חיפוש, סינון, מיון)
  - רשימת מעקב (הוספה/הסרה, סיכום ביצועים)
  - צ'אט AI (שאלות מוצעות, rate limiting)
- **Backend מלא (Python FastAPI):**
  - `backend/app/main.py` — FastAPI app + CORS + lifespan
  - `backend/app/routers/trends.py` — GET /api/trends, GET /api/trends/:slug
  - `backend/app/routers/stocks.py` — GET /api/stocks (screener), GET /api/stocks/:ticker
  - `backend/app/routers/chat.py` — POST /api/chat, GET /api/chat/remaining
  - `backend/app/services/reddit.py` — Reddit API collector (PRAW)
  - `backend/app/services/news.py` — NewsAPI collector
  - `backend/app/services/momentum.py` — Momentum calculator (today/avg7d × 100)
  - `backend/app/services/stocks.py` — yfinance price service + 5-min cache
  - `backend/app/services/ai_explainer.py` — Claude Haiku + system prompt + rate limit
  - `backend/app/models/database.py` — asyncpg pool + seed from JSON
  - `backend/app/models/schemas.py` — Pydantic models
- **Data:**
  - `backend/app/data/topics.json` — 20 נושאים + keywords + subreddits + מניות ממופות
- **Database:**
  - `database/001_schema.sql` — 5 טבלאות (topics, topic_stocks, topic_mentions, momentum_scores, watchlist_items)
- **Pipeline:**
  - `pipeline/collect.py` — סקריפט collection + momentum, תומך בפרמטרים (--source, --momentum-only, --seed-only)
- **Infrastructure:**
  - `docker-compose.yml` — PostgreSQL + Backend
  - `backend/Dockerfile`
  - `.env.example` — כל המשתנים הנדרשים
  - `README.md` — הוראות setup מלאות

### ⚠️ הערה חשובה:
דילגנו על סדר התכנית המקורי! התכנית אמרה:
1. קודם pipeline → 2. הרצת 48 שעות → 3. ורק אז frontend

בפועל: קפצנו ל-frontend עם mock data, ובנינו backend במקביל.
**זה לא רע** — אבל צריך עכשיו לחזור ולהריץ את ה-pipeline על נתוני אמת לפני שמחברים.

### 🔜 מה השלב הבא (לפי סדר עדיפות):
1. **להריץ `docker compose up`** — להקים DB + Backend
2. **להגדיר API keys** — Reddit, NewsAPI, Claude
3. **להריץ `python pipeline/collect.py --seed-only`** — לזרוע נתונים ל-DB
4. **להריץ `python pipeline/collect.py`** — collection ראשון
5. **להריץ 48 שעות** ולוודא שהנתונים הגיוניים
6. **לחבר Frontend ל-Backend API** — להחליף mock data בקריאות API אמיתיות
7. **לבנות Next.js frontend** — להעביר מ-JSX prototype ל-Next.js app

## 🛠 Stack טכנולוגי
| רכיב | טכנולוגיה | עלות |
|-------|-----------|------|
| Frontend | Next.js + Tailwind (Vercel free) | $0 |
| Backend | Python FastAPI (Railway/Render) | $5-20 |
| Database | PostgreSQL (Supabase/Neon free) | $0-7 |
| Data | Reddit API + NewsAPI (free tiers) | $0 |
| מניות | yfinance (Yahoo Finance) | $0 |
| AI Explainer | Claude API (Haiku) | $5-20 |
| **סה"כ** | | **$10-50/חודש** |

## 💰 מודל עסקי — Freemium
| שכבה | מחיר | כולל |
|------|------|------|
| Free | $0 | 5 מגמות, watchlist עד 5, 3 שאלות AI/יום |
| Pro | $12/חודש | כל 20 מגמות, watchlist ללא הגבלה, AI ללא הגבלה |
| API | $79/חודש | גישת API למפתחים |

## 📁 קבצי פרויקט
```
trendvest/
├── backend/app/main.py              # FastAPI app
├── backend/app/routers/             # API endpoints (trends, stocks, chat)
├── backend/app/services/            # Reddit, News, Momentum, Stocks, AI
├── backend/app/models/              # DB + Pydantic schemas
├── backend/app/data/topics.json     # 20 topics config
├── pipeline/collect.py              # Data collection cron script
├── database/001_schema.sql          # PostgreSQL schema
├── docker-compose.yml               # Local dev setup
├── .env.example                     # Required env vars
└── README.md                        # Setup instructions
```

---

## 📝 הערות לשיחה הבאה
> עדכן את הסעיף הזה בסוף כל שיחת פיתוח

**שיחה 1 (13/02/2026):** יצירת קובץ סטטוס פרויקט + frontend prototype
**שיחה 2 (13/02/2026):** יצירת Technical Roadmap (14 פרקים, docx)
**שיחה 3 (13/02/2026):** בניית Backend מלא — FastAPI + services + pipeline + Docker. 
הכל מוכן להרצה. השלב הבא: להריץ על המחשב עם Claude Code, לחבר API keys, ולהתחיל collection.

---
*קובץ זה נועד לשימוש כ"זיכרון" בין שיחות עם Claude. העלה אותו בתחילת כל שיחה חדשה.*
