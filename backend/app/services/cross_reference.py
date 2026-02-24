"""
Cross-referencing algorithm for TrendVest.
Analyzes all data sources to identify trending topics in economic discourse.
Scores topics by how many independent sources mention them.
"""
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from .israeli_news import get_israeli_news
from .global_rss import get_global_news
from .blogs import get_blog_posts
from .israeli_institutional import get_institutional_data
from .us_government import get_us_gov_data
from .international_institutional import get_international_data

# Cache
_trending_cache: dict[str, dict] = {}
CACHE_TTL = 600  # 10 minutes

# Financial keyword patterns — used to extract meaningful terms
STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "must", "can", "could", "and", "but", "or",
    "nor", "not", "no", "so", "yet", "for", "at", "by", "in", "of", "on",
    "to", "up", "it", "its", "as", "if", "than", "that", "this", "with",
    "from", "into", "about", "over", "after", "before", "between", "under",
    "during", "through", "new", "says", "said", "also", "more", "most",
    "other", "some", "such", "than", "they", "their", "them", "these",
    "those", "what", "which", "who", "whom", "how", "when", "where", "why",
    "all", "each", "every", "both", "few", "many", "much", "several", "own",
    "same", "first", "last", "next", "just", "now", "then", "here", "there",
    "only", "very", "even", "well", "back", "still", "get", "got", "make",
    "made", "take", "took", "come", "came", "go", "went", "one", "two",
    # Hebrew stop words
    "של", "את", "על", "זה", "לא", "גם", "עם", "היא", "הוא", "כי",
    "אם", "או", "כל", "יש", "אין", "הם", "היו", "עד", "מה", "כך",
    "לפני", "אחרי", "בין", "תחת", "מעל", "אצל", "אחר", "כמו", "רק",
}

# Financial terms that indicate significant topics
FINANCIAL_TERMS = {
    # English
    "inflation", "recession", "gdp", "rate", "rates", "interest", "fed",
    "federal", "reserve", "treasury", "bond", "bonds", "yield", "yields",
    "stock", "stocks", "market", "markets", "bull", "bear", "rally",
    "crash", "correction", "earnings", "revenue", "profit", "loss",
    "dividend", "ipo", "merger", "acquisition", "tariff", "tariffs",
    "trade", "deficit", "surplus", "unemployment", "jobs", "employment",
    "housing", "mortgage", "oil", "gas", "energy", "crypto", "bitcoin",
    "ethereum", "blockchain", "ai", "artificial", "intelligence",
    "semiconductor", "chip", "chips", "tech", "technology", "bank",
    "banking", "fintech", "insurance", "healthcare", "pharma",
    "biotech", "ev", "electric", "vehicle", "solar", "renewable",
    "nuclear", "defense", "cyber", "cloud", "streaming", "retail",
    "ecommerce", "consumer", "commodity", "commodities", "gold",
    "silver", "copper", "wheat", "sanctions", "regulation", "sec",
    "ecb", "boj", "pboc", "imf", "opec", "nato", "geopolitical",
    "war", "conflict", "election", "policy", "fiscal", "monetary",
    "quantitative", "easing", "tightening", "dollar", "euro", "yen",
    "yuan", "shekel", "forex", "currency", "devaluation", "default",
    "debt", "credit", "downgrade", "upgrade", "outlook", "forecast",
    "growth", "contraction", "stagnation", "stagflation", "bubble",
    "liquidity", "volatility", "vix", "s&p", "nasdaq", "dow",
    "startup", "venture", "private", "equity", "hedge", "fund",
    # Hebrew
    "אינפלציה", "מיתון", "ריבית", "תוצר", "אבטלה", "תעסוקה",
    "מניות", "שוק", "בורסה", "דיבידנד", "חוב", "אגח", "תשואה",
    "נפט", "גז", "אנרגיה", "קריפטו", "ביטקוין", "בינה", "מלאכותית",
    "טכנולוגיה", "בנק", "ביטוח", "בריאות", "פארמה", "ביוטק",
    "רכב", "חשמלי", "סולארי", "גרעין", "ביטחון", "סייבר",
    "ענן", "קמעונאי", "סחורות", "זהב", "דולר", "שקל",
    "סטארטאפ", "הון", "סיכון", "מכס", "מכסים", "סנקציות",
    "מונטרי", "פיסקלי", "תקציב", "גירעון", "עודף",
}


def _extract_terms(text: str) -> list[str]:
    """Extract meaningful financial terms from text."""
    if not text:
        return []
    # Lowercase and split
    words = re.findall(r'[\w\u0590-\u05FF]+', text.lower())
    # Filter: keep financial terms or multi-word phrases
    terms = []
    for w in words:
        if w in STOP_WORDS or len(w) < 3:
            continue
        if w in FINANCIAL_TERMS:
            terms.append(w)
        elif len(w) >= 5:
            terms.append(w)
    return terms


def _extract_bigrams(text: str) -> list[str]:
    """Extract meaningful two-word phrases."""
    if not text:
        return []
    words = re.findall(r'[\w\u0590-\u05FF]+', text.lower())
    words = [w for w in words if w not in STOP_WORDS and len(w) >= 3]
    bigrams = []
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i+1]}"
        bigrams.append(bigram)
    return bigrams


def _fetch_all_sources(market: Optional[str] = None) -> list[dict]:
    """Fetch articles from all sources in parallel."""
    all_items = []

    def fetch_israeli_news():
        return get_israeli_news(limit=30)

    def fetch_global_news():
        return get_global_news(limit=30)

    def fetch_blogs():
        return get_blog_posts(limit=30)

    def fetch_il_institutional():
        return get_institutional_data(limit=20)

    def fetch_us_gov():
        return get_us_gov_data(limit=20)

    def fetch_intl_europe():
        return get_international_data(region="europe", limit=20)

    def fetch_intl_asia():
        return get_international_data(region="asia", limit=20)

    def fetch_intl_global():
        return get_international_data(region="international", limit=20)

    fetchers = []
    if market is None or market == "all":
        fetchers = [
            fetch_israeli_news, fetch_global_news, fetch_blogs,
            fetch_il_institutional, fetch_us_gov,
            fetch_intl_europe, fetch_intl_asia, fetch_intl_global,
        ]
    elif market == "israel":
        fetchers = [fetch_israeli_news, fetch_il_institutional, fetch_blogs]
    elif market == "us":
        fetchers = [fetch_global_news, fetch_us_gov, fetch_blogs]
    elif market == "europe":
        fetchers = [fetch_global_news, fetch_intl_europe, fetch_blogs]
    elif market == "asia":
        fetchers = [fetch_global_news, fetch_intl_asia, fetch_blogs]

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(f): f.__name__ for f in fetchers}
        for future in as_completed(futures):
            try:
                items = future.result()
                all_items.extend(items)
            except Exception as e:
                print(f"Cross-reference fetch error ({futures[future]}): {e}")

    return all_items


def get_trending_topics(
    market: Optional[str] = None,
    limit: int = 15,
) -> list[dict]:
    """
    Cross-reference all sources to identify trending topics.

    Scores topics by:
    - Number of unique sources mentioning them
    - Total mention frequency
    - Recency weight (newer = higher)
    - Source diversity bonus (more diverse = higher)

    Args:
        market: Filter by market region (israel, us, europe, asia, all)
        limit: Max topics to return

    Returns:
        List of trending topic dicts with score, sources, articles
    """
    cache_key = f"trending:{market or 'all'}:{limit}"
    now = time.time()

    if cache_key in _trending_cache:
        cached = _trending_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    # 1. Fetch all articles
    all_items = _fetch_all_sources(market)

    if not all_items:
        return []

    # 2. Extract terms from all articles
    term_counter = Counter()
    bigram_counter = Counter()
    term_sources: dict[str, set] = defaultdict(set)
    bigram_sources: dict[str, set] = defaultdict(set)
    term_articles: dict[str, list] = defaultdict(list)
    bigram_articles: dict[str, list] = defaultdict(list)

    for item in all_items:
        title = item.get("title", "")
        desc = item.get("description", "")
        text = f"{title} {desc}"
        source = item.get("source", "unknown")
        source_type = item.get("source_type", "unknown")

        # Extract single terms
        terms = _extract_terms(text)
        unique_terms = set(terms)
        for term in unique_terms:
            term_counter[term] += 1
            term_sources[term].add(f"{source_type}:{source}")
            if len(term_articles[term]) < 5:
                term_articles[term].append({
                    "title": title,
                    "url": item.get("url", ""),
                    "source": source,
                    "source_type": source_type,
                    "published_at": item.get("published_at", ""),
                })

        # Extract bigrams
        bigrams = _extract_bigrams(text)
        unique_bigrams = set(bigrams)
        for bg in unique_bigrams:
            bigram_counter[bg] += 1
            bigram_sources[bg].add(f"{source_type}:{source}")
            if len(bigram_articles[bg]) < 5:
                bigram_articles[bg].append({
                    "title": title,
                    "url": item.get("url", ""),
                    "source": source,
                    "source_type": source_type,
                    "published_at": item.get("published_at", ""),
                })

    # 3. Score and rank topics
    scored_topics = []

    # Score single terms (only financial terms or highly mentioned ones)
    for term, count in term_counter.most_common(100):
        if count < 3:
            continue
        source_count = len(term_sources[term])
        if source_count < 2 and term not in FINANCIAL_TERMS:
            continue

        # Score: frequency * source diversity
        score = count * (1 + source_count * 0.5)
        if term in FINANCIAL_TERMS:
            score *= 1.5  # Boost financial terms

        scored_topics.append({
            "topic": term,
            "type": "term",
            "mention_count": count,
            "source_count": source_count,
            "sources": sorted(term_sources[term]),
            "score": round(score, 1),
            "articles": term_articles[term][:3],
        })

    # Score bigrams
    for bg, count in bigram_counter.most_common(50):
        if count < 2:
            continue
        source_count = len(bigram_sources[bg])
        if source_count < 2:
            continue

        score = count * (1 + source_count * 0.7)

        # Check if any word is a financial term
        words = bg.split()
        if any(w in FINANCIAL_TERMS for w in words):
            score *= 1.3

        scored_topics.append({
            "topic": bg,
            "type": "phrase",
            "mention_count": count,
            "source_count": source_count,
            "sources": sorted(bigram_sources[bg]),
            "score": round(score, 1),
            "articles": bigram_articles[bg][:3],
        })

    # 4. Sort by score and deduplicate
    scored_topics.sort(key=lambda x: x["score"], reverse=True)

    # Deduplicate: remove terms that are substrings of higher-ranked bigrams
    seen_terms = set()
    unique_topics = []
    for topic in scored_topics:
        t = topic["topic"]
        # Skip if this single term is already covered by a bigram
        if topic["type"] == "term":
            covered = False
            for existing in unique_topics:
                if existing["type"] == "phrase" and t in existing["topic"]:
                    covered = True
                    break
            if covered:
                continue
        if t not in seen_terms:
            seen_terms.add(t)
            unique_topics.append(topic)

    result = unique_topics[:limit]

    _trending_cache[cache_key] = {"time": now, "data": result}
    return result
