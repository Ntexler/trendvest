# Data Pipeline & AI Integration — TrendVest

## Overview
TrendVest has two major subsystems beyond the basic CRUD:
1. **Data Pipeline** — collects mention counts from external sources (Reddit, NewsAPI, Google Trends, X/Twitter) and calculates momentum scores
2. **AI Integration** — uses Claude API for chat, translations, term explanations, section analysis, officer bios, and topic insights

## Data Pipeline

### Entry Point
`pipeline/collect.py` — standalone CLI script, also runs as cron job inside Docker.

```bash
python -m pipeline.collect                    # All sources + momentum
python -m pipeline.collect --source reddit    # Reddit only
python -m pipeline.collect --source news      # NewsAPI only
python -m pipeline.collect --source google_trends
python -m pipeline.collect --source x         # X/Twitter
python -m pipeline.collect --momentum-only    # Recalculate momentum only
python -m pipeline.collect --seed-only        # Seed DB from topics.json
```

### Data Flow
```
topics.json (20+ topics with keywords, subreddits, stocks)
    ↓
Collectors (Reddit, News, Google Trends, X)
    ↓ mention counts per topic per source
topic_mentions table
    ↓
MomentumCalculator
    ↓ score, direction, mention_count_today, mention_avg_7d
momentum_scores table
    ↓
API serves to frontend → Dashboard, TopicCards
```

### Collectors
All collectors follow the same interface:

```python
class SomeCollector:
    def collect_all(self, topics: list[dict]) -> list[dict]:
        """Returns list of mention records."""
        # Each record: {topic_slug, source, mention_count, collected_at, period_start, period_end}
```

| Collector | File | API | Rate Limits |
|-----------|------|-----|-------------|
| RedditCollector | `services/reddit.py` | PRAW (Reddit API) | 1s delay between requests |
| NewsCollector | `services/news.py` | NewsAPI | Free tier limits |
| GoogleTrendsCollector | `services/google_trends.py` | pytrends | Variable |
| XTwitterCollector | `services/x_twitter.py` | X/Twitter API | Depends on tier |

### Adding a New Data Source
1. Create `backend/app/services/my_source.py` with `MySourceCollector` class
2. Implement `collect_all(topics) -> list[dict]` returning mention records
3. Add `source` value to DB constraint: `CHECK (source IN ('reddit', 'news', 'google_trends', 'x', 'my_source'))`
4. Register in `pipeline/collect.py`:
   ```python
   if args.source in (None, "my_source"):
       collector = MySourceCollector()
       mentions = collector.collect_all(topics)
       all_mentions.extend(mentions)
   ```
5. Add CLI argument choice: `choices=["reddit", "news", "google_trends", "x", "my_source"]`

### Topics Configuration
`backend/app/data/topics.json` defines all tracked topics:
```json
{
  "topics": [
    {
      "slug": "ai-chips",
      "name_en": "AI Chips",
      "name_he": "שבבי AI",
      "sector": "טכנולוגיה",
      "sector_en": "Technology",
      "keywords": ["AI chips", "GPU", "NVIDIA", "semiconductor"],
      "subreddits": ["stocks", "wallstreetbets", "technology"],
      "stocks": [
        { "ticker": "NVDA", "company_name": "NVIDIA", "relevance_note": "Leading AI GPU maker", "priority": 1 }
      ]
    }
  ]
}
```

### Momentum Scoring
`backend/app/services/momentum.py` — `MomentumCalculator`

**Formula:** `score = (mentions_today / avg_mentions_7d) * 100`

**Direction thresholds:**
- `score > 150` → `"rising"` (50%+ above 7-day average)
- `score > 80` → `"stable"` (normal range)
- `score <= 80` → `"falling"` (below average)
- `today > 0, no history` → score = 200 (new strong signal)

**Storage:** Upsert into `momentum_scores` table (unique per topic_id)

### Cron Schedule
```bash
*/30 * * * *  python -m pipeline.collect --source reddit    # Every 30 min
0 */3 * * *   python -m pipeline.collect --source news      # Every 3 hours
5,35 * * * *  python -m pipeline.collect --momentum-only    # 5 min after each collection
```

---

## AI Integration (Claude API)

### Service: `backend/app/services/ai_explainer.py` — `AIExplainer`

Core class providing all AI functionality. Uses `anthropic` Python SDK with Claude Haiku 4.5.

### Capabilities

| Method | Purpose | Model | Max Tokens |
|--------|---------|-------|------------|
| `ask()` | Chat Q&A (Hebrew/English) | claude-haiku-4-5 | 500 |
| `translate_text()` | Translate company summaries to Hebrew | claude-haiku-4-5 | 800 |
| `explain_term()` | 1-2 sentence financial term definition | claude-haiku-4-5 | 200 |
| `explain_section()` | Contextual summary of stock financial data | claude-haiku-4-5 | 400 |
| `generate_officer_bio()` | 1-2 sentence professional bio | claude-haiku-4-5 | 150 |

### Rate Limiting
- Free tier: 3 questions/day per user (tracked in-memory by user_id)
- Daily counter resets at midnight
- `check_rate_limit(user_id) -> (allowed: bool, remaining: int)`

### Caching
- In-memory LRU cache (max 500 entries)
- Cache keys: `"translate:{ticker}:{lang}"`, `"term:{term}:{lang}"`, `"section:{ticker}:{section}:{lang}"`, `"bio:{name}:{company}:{lang}"`
- Responses cached to avoid redundant API calls

### System Prompts
- Hebrew prompt: Financial education assistant for Israeli investors, simple Hebrew, no investment advice
- English prompt: Same rules in English
- Critical rules: never say "buy"/"sell", always add disclaimers, under 200 words

### Fallback Behavior
- If `ANTHROPIC_API_KEY` is missing → returns friendly fallback message
- If `anthropic` library not installed → returns `None` client
- API errors → returns "try again" message in appropriate language

### Topic Insights
`backend/app/services/topic_insights.py` — generates AI-powered topic insights:
- Why a topic is trending
- Stock connections explanation
- Related topics and hidden connections
- Falls back to curated/hardcoded insights if AI is unavailable

### Deep Research (Perplexity)
`backend/app/routers/stocks.py` — `/api/stocks/{ticker}/research`:
- Uses Perplexity API (`sonar` model) for real-time web-searched analysis
- Falls back to yfinance data if `PERPLEXITY_API_KEY` is not set
- Returns analysis text + citation URLs

### Environment Variables for AI
```
ANTHROPIC_API_KEY=sk-ant-...     # Required for Claude chat/translations
PERPLEXITY_API_KEY=pplx-...     # Optional for deep research
```

### Adding a New AI Feature
1. Add method to `AIExplainer` class in `services/ai_explainer.py`
2. Use `self.client.messages.create()` with appropriate model, system prompt, max_tokens
3. Add caching with `self._cache_set(key, value)` and check `self._cache`
4. Add graceful fallback for when client is None (no API key)
5. Create API endpoint in appropriate router
6. Add frontend API function in `lib/api.ts` and use in component
