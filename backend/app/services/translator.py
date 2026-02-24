"""
Article translation and summary service for TrendVest.
Uses Claude API to translate and summarize financial articles.
"""
import os
import time
from typing import Optional

try:
    import anthropic
except ImportError:
    anthropic = None

# Cache translations to avoid repeated API calls
_translation_cache: dict[str, dict] = {}
CACHE_TTL = 3600  # 1 hour
MAX_CACHE = 500

TRANSLATE_SYSTEM_HE = """אתה מתרגם פיננסי מקצועי של TrendVest.
תפקידך לתרגם ולסכם כתבות פיננסיות לעברית.

כללים:
- תרגם את הכותרת לעברית
- צור סיכום של 2-3 משפטים בעברית המסבירים את עיקרי הכתבה
- שמור על דיוק פיננסי — אל תשנה מספרים, שמות חברות או מניות
- השתמש בעברית פשוטה וברורה
- אם המאמר כבר בעברית, רק סכם אותו

פורמט תשובה (JSON):
{"translated_title": "...", "summary": "...", "key_points": ["...", "..."], "language": "he"}
"""

TRANSLATE_SYSTEM_EN = """You are a professional financial translator for TrendVest.
Your job is to translate and summarize financial articles into English.

Rules:
- Translate the title to English
- Create a 2-3 sentence summary explaining the key points
- Maintain financial accuracy — don't change numbers, company names, or tickers
- Use clear, simple English
- If the article is already in English, just summarize it

Response format (JSON):
{"translated_title": "...", "summary": "...", "key_points": ["...", "..."], "language": "en"}
"""


def translate_and_summarize(
    title: str,
    description: str,
    source: str,
    target_language: str = "he",
    url: str = "",
) -> dict:
    """
    Translate and summarize an article.

    Args:
        title: Article title
        description: Article description/content
        source: Source name
        target_language: Target language (he/en)
        url: Original article URL

    Returns:
        Dict with translated_title, summary, key_points, language
    """
    cache_key = f"{title[:80]}:{target_language}"
    now = time.time()

    # Check cache
    if cache_key in _translation_cache:
        cached = _translation_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    # Evict old cache entries
    if len(_translation_cache) >= MAX_CACHE:
        oldest_key = min(_translation_cache, key=lambda k: _translation_cache[k]["time"])
        del _translation_cache[oldest_key]

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or anthropic is None:
        # Fallback without API
        result = {
            "translated_title": title,
            "summary": description[:300] if description else "",
            "key_points": [],
            "language": target_language,
            "source": source,
            "url": url,
            "ai_generated": False,
        }
        _translation_cache[cache_key] = {"time": now, "data": result}
        return result

    system_prompt = TRANSLATE_SYSTEM_HE if target_language == "he" else TRANSLATE_SYSTEM_EN

    user_content = f"""Article to translate and summarize:

Title: {title}
Source: {source}
Description: {description[:1000] if description else 'No description available'}
URL: {url}

Translate to: {"Hebrew" if target_language == "he" else "English"}

Respond with valid JSON only."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )

        import json
        text = response.content[0].text.strip()
        # Handle markdown code blocks
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        parsed = json.loads(text)
        result = {
            "translated_title": parsed.get("translated_title", title),
            "summary": parsed.get("summary", description[:300]),
            "key_points": parsed.get("key_points", []),
            "language": target_language,
            "source": source,
            "url": url,
            "ai_generated": True,
        }
    except Exception as e:
        print(f"Translation error: {e}")
        result = {
            "translated_title": title,
            "summary": description[:300] if description else "",
            "key_points": [],
            "language": target_language,
            "source": source,
            "url": url,
            "ai_generated": False,
        }

    _translation_cache[cache_key] = {"time": now, "data": result}
    return result


def batch_translate(
    articles: list[dict],
    target_language: str = "he",
    max_articles: int = 10,
) -> list[dict]:
    """Translate a batch of articles."""
    results = []
    for article in articles[:max_articles]:
        translated = translate_and_summarize(
            title=article.get("title", ""),
            description=article.get("description", ""),
            source=article.get("source", ""),
            target_language=target_language,
            url=article.get("url", ""),
        )
        results.append(translated)
    return results
