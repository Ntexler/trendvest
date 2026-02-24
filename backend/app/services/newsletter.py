"""
Weekly newsletter generation for TrendVest.
Cross-references all data sources and generates a digest
of the hottest economic events and trends.
"""
import os
import time
from datetime import datetime, timezone
from typing import Optional

from .cross_reference import get_trending_topics

try:
    import anthropic
except ImportError:
    anthropic = None

# Cache
_newsletter_cache: dict[str, dict] = {}
CACHE_TTL = 3600  # 1 hour (newsletters are expensive to generate)

NEWSLETTER_SYSTEM_HE = """אתה עיתונאי פיננסי של TrendVest — פלטפורמה ישראלית למעקב מגמות בשוק ההון.

תפקידך ליצור ניוזלטר שבועי מקצועי ואינפורמטיבי בעברית.

מבנה הניוזלטר:
1. **כותרת ראשית** — משפט אחד שמסכם את השבוע
2. **3-5 אירועים מרכזיים** — כל אירוע בפסקה קצרה (2-3 משפטים)
3. **מגמות מפתח** — 3 מגמות שכדאי לעקוב אחריהן
4. **מבט קדימה** — מה לצפות בשבוע הבא (1-2 משפטים)

כללים:
- כתוב בעברית ברורה ופשוטה
- הימנע מייעוץ השקעות — רק מידע וניתוח
- השתמש בנתונים ובעובדות מהמקורות
- שמור על טון מקצועי אך נגיש
- הניוזלטר צריך להיות 300-500 מילים
- הוסף disclaimer בסוף: "מידע חינוכי בלבד — אינו מהווה ייעוץ השקעות"
"""

NEWSLETTER_SYSTEM_EN = """You are a financial journalist for TrendVest — a trend-tracking stock discovery platform.

Your job is to create a professional, informative weekly newsletter in English.

Newsletter structure:
1. **Main headline** — One sentence summarizing the week
2. **3-5 key events** — Each event in a short paragraph (2-3 sentences)
3. **Key trends** — 3 trends worth watching
4. **Looking ahead** — What to expect next week (1-2 sentences)

Rules:
- Write in clear, simple English
- Avoid investment advice — only information and analysis
- Use data and facts from the sources
- Maintain a professional but accessible tone
- Newsletter should be 300-500 words
- Add disclaimer at end: "Educational information only — not investment advice"
"""


def generate_newsletter(
    language: str = "he",
    market: Optional[str] = None,
) -> dict:
    """
    Generate a weekly newsletter by cross-referencing all sources.

    Args:
        language: Newsletter language (he/en)
        market: Market focus (israel, us, europe, asia, all)

    Returns:
        Dict with newsletter content, trending topics, and metadata
    """
    cache_key = f"newsletter:{language}:{market or 'all'}"
    now = time.time()

    if cache_key in _newsletter_cache:
        cached = _newsletter_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    # 1. Get trending topics from cross-reference
    trending = get_trending_topics(market=market, limit=15)

    # 2. Build context for the AI
    topics_summary = []
    all_articles = []
    for topic in trending[:10]:
        topics_summary.append(
            f"- {topic['topic']} (score: {topic['score']}, "
            f"mentions: {topic['mention_count']}, "
            f"sources: {topic['source_count']})"
        )
        all_articles.extend(topic.get("articles", []))

    # Deduplicate articles
    seen_titles = set()
    unique_articles = []
    for article in all_articles:
        title = article.get("title", "")
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_articles.append(article)

    articles_text = "\n".join(
        f"- [{a['source']}] {a['title']}"
        for a in unique_articles[:20]
    )

    topics_text = "\n".join(topics_summary)

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or anthropic is None:
        # Fallback without API — structured summary without AI
        result = _build_fallback_newsletter(trending, unique_articles, language, market)
        _newsletter_cache[cache_key] = {"time": now, "data": result}
        return result

    system_prompt = NEWSLETTER_SYSTEM_HE if language == "he" else NEWSLETTER_SYSTEM_EN

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    user_content = f"""Generate a weekly newsletter for the week ending {today}.

Trending topics (cross-referenced from 70+ sources):
{topics_text}

Recent headlines:
{articles_text}

Market focus: {market or "all markets"}

Generate the newsletter now."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )

        newsletter_text = response.content[0].text.strip()

        result = {
            "newsletter": newsletter_text,
            "trending_topics": trending[:10],
            "top_articles": unique_articles[:10],
            "market": market or "all",
            "language": language,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ai_generated": True,
            "source_count": sum(t["source_count"] for t in trending[:10]),
            "total_mentions": sum(t["mention_count"] for t in trending[:10]),
        }
    except Exception as e:
        print(f"Newsletter generation error: {e}")
        result = _build_fallback_newsletter(trending, unique_articles, language, market)

    _newsletter_cache[cache_key] = {"time": now, "data": result}
    return result


def _build_fallback_newsletter(
    trending: list[dict],
    articles: list[dict],
    language: str,
    market: Optional[str],
) -> dict:
    """Build a structured newsletter without AI."""
    if language == "he":
        lines = [
            "# ניוזלטר שבועי — TrendVest",
            "",
            "## נושאים טרנדיים השבוע",
            "",
        ]
        for i, topic in enumerate(trending[:5], 1):
            lines.append(
                f"{i}. **{topic['topic']}** — {topic['mention_count']} אזכורים "
                f"מ-{topic['source_count']} מקורות (ציון: {topic['score']})"
            )
        lines.append("")
        lines.append("## כותרות מרכזיות")
        lines.append("")
        for article in articles[:8]:
            lines.append(f"- [{article.get('source', '')}] {article.get('title', '')}")
        lines.append("")
        lines.append("---")
        lines.append("*מידע חינוכי בלבד — אינו מהווה ייעוץ השקעות*")
    else:
        lines = [
            "# Weekly Newsletter — TrendVest",
            "",
            "## Trending Topics This Week",
            "",
        ]
        for i, topic in enumerate(trending[:5], 1):
            lines.append(
                f"{i}. **{topic['topic']}** — {topic['mention_count']} mentions "
                f"from {topic['source_count']} sources (score: {topic['score']})"
            )
        lines.append("")
        lines.append("## Top Headlines")
        lines.append("")
        for article in articles[:8]:
            lines.append(f"- [{article.get('source', '')}] {article.get('title', '')}")
        lines.append("")
        lines.append("---")
        lines.append("*Educational information only — not investment advice*")

    return {
        "newsletter": "\n".join(lines),
        "trending_topics": trending[:10],
        "top_articles": articles[:10],
        "market": market or "all",
        "language": language,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ai_generated": False,
        "source_count": sum(t["source_count"] for t in trending[:10]),
        "total_mentions": sum(t["mention_count"] for t in trending[:10]),
    }
