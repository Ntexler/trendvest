# Next.js Frontend Development — TrendVest

## Overview
The frontend is a Next.js 15 application with React 19, TypeScript, and Tailwind CSS 4. It provides a single-page dashboard for tracking stock trends, screening stocks, paper trading, news feed, and an AI chatbot — all bilingual (Hebrew/English) with RTL support.

## Tech Stack
- **Next.js 15** with App Router (`src/app/`)
- **React 19** with client components (`"use client"`)
- **TypeScript 5.7**
- **Tailwind CSS 4** (via `@tailwindcss/postcss`)
- **Recharts** — charts and sparklines
- **Lucide React** — icon library
- No state management library — uses React hooks, context, and localStorage

## Directory Structure
```
frontend/src/
├── app/
│   ├── layout.tsx       # Root layout (HTML, body, fonts)
│   └── page.tsx         # Main SPA entry — routing, navigation, providers
├── components/
│   ├── Dashboard.tsx    # Trend topics grid with sector filter
│   ├── TopicCard.tsx    # Individual topic card with stocks & momentum
│   ├── Screener.tsx     # Stock screener with filters/sorting
│   ├── StockProfile.tsx # Full stock profile modal (overview, management, financials, peers)
│   ├── StockChart.tsx   # Price history chart (Recharts)
│   ├── Sparkline.tsx    # Inline mini chart
│   ├── HeatGauge.tsx    # Momentum heat gauge visualization
│   ├── PaperTrading.tsx # Paper trading interface (buy/sell/portfolio)
│   ├── TradeModal.tsx   # Trade execution modal
│   ├── Watchlist.tsx    # User watchlist with stocks & news tabs
│   ├── NewsFeed.tsx     # News articles feed
│   ├── ChatBot.tsx      # Floating AI chatbot (Claude-powered)
│   ├── TopBar.tsx       # Header with language toggle and mode switch
│   ├── MobileMenu.tsx   # Bottom navigation for mobile
│   ├── MarketTicker.tsx # Scrolling market ticker bar
│   ├── ExplainTooltip.tsx # AI-powered financial term explanations
│   └── Term.tsx         # Clickable financial term with tooltip
├── contexts/
│   └── ModeContext.tsx  # Beginner/Expert display mode
├── hooks/
│   ├── usePaperTrading.ts # Paper trading state management
│   └── useWatchlist.ts    # Watchlist persistence (localStorage)
├── i18n/
│   ├── context.tsx      # I18nProvider, useI18n hook
│   └── translations.ts  # All UI strings (Hebrew + English)
└── lib/
    ├── api.ts           # API client — all fetch functions
    └── types.ts         # TypeScript interfaces
```

## Key Patterns

### Single-Page Navigation
The app uses client-side state for navigation — no Next.js routing pages:
```tsx
const [page, setPage] = useState("trends");
// Pages: "trends" | "news" | "screener" | "trade" | "watchlist"
```

### i18n (Hebrew/English with RTL)
- `useI18n()` hook provides: `locale`, `dir`, `toggleLocale()`, `t(key)`
- Translations in `i18n/translations.ts` — flat key-value map: `{ "nav.trends": { he: "...", en: "..." } }`
- RTL handled via `<div dir={dir}>` on provider wrapper
- Hebrew uses Rubik font (`font-rubik` class)

**Adding new translations:**
1. Add key to `translations.ts`: `"section.key": { he: "עברית", en: "English" }`
2. Use in component: `const { t } = useI18n(); t("section.key")`

### Bilingual Content Display
Components render locale-dependent content:
```tsx
const { locale } = useI18n();
<span>{locale === "he" ? topic.name_he : topic.name_en}</span>
```

### Display Mode (Beginner/Expert)
- `ModeContext` provides `mode` ("beginner" | "expert") and `toggleMode()`
- Components conditionally show/hide advanced data based on mode

### API Client
All backend calls go through `lib/api.ts`:
```tsx
import { getTrends, getStocks, askAI } from "@/lib/api";
```
- Base URL: `/api` (proxied via Next.js rewrites or direct)
- All functions return typed promises
- Session ID managed via `getSessionId()` (localStorage UUID)

### Component Conventions
- All components are `"use client"` (client-side rendered)
- Dark theme by default — colors: `bg-[#0f172a]`, `text-white`, `text-[#94a3b8]`
- Accent: cyan (`cyan-400`, `cyan-500`)
- Cards: `bg-[#1e293b]` with `rounded-xl` and `border border-[#334155]`
- Responsive: mobile-first with `md:` breakpoints
- Icons: `lucide-react` (e.g., `<TrendingUp className="w-4 h-4" />`)

### Adding a New Component
1. Create `frontend/src/components/MyComponent.tsx` with `"use client"` directive
2. Use `useI18n()` for text, add translation keys to `translations.ts`
3. Import in `page.tsx` and add to navigation if it's a new page
4. Use `@/lib/api.ts` functions for data fetching
5. Follow the dark theme color palette and existing Tailwind patterns

### Adding a New Page
1. Create the component in `components/`
2. Add nav entry in `page.tsx` navigation arrays (desktop sidebar + mobile menu)
3. Add translation key: `"nav.mypage": { he: "...", en: "..." }`
4. Add page rendering in both desktop and mobile content areas

### Stock Profile Modal
`StockProfile.tsx` is a full-screen modal that opens when clicking a stock. It has tabs:
- Overview (summary, key metrics)
- Management (officers with AI bios)
- Financials (margins, growth, valuation)
- Analyst (recommendations, target price)
- Peers (sector comparison table)
- Deep Research (Perplexity/yfinance analysis)

### Paper Trading
- Session-based (UUID in localStorage)
- Starting balance: $100,000
- Real-time prices from yfinance via backend
- Portfolio allocation chart (Recharts pie)
- Trade history log

### Development
```bash
cd frontend
npm install
npm run dev      # http://localhost:3000
npm run build    # Production build
npm run lint     # ESLint
```
