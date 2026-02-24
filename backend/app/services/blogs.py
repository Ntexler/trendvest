"""
Financial blogs and newsletters for TrendVest.
Free — no API keys needed. RSS feeds from top financial bloggers.

Global:
- Calculated Risk — US real estate and macro
- Marginal Revolution — Economic-intellectual blog
- Matt Levine / Money Stuff — Bloomberg newsletter, market analysis with humor
- Noah Smith / Noahpinion — Accessible economic policy writing
- The Macro Compass — Macro and markets analysis
- Kyla Scanlon — Visual macro explainer
- Doomberg — Energy, commodities, economic geopolitics
- John Mauldin — Weekly global macro letter

Israeli:
- The Solidit (הסולידית) — Passive investing and personal finance
- Pensioni (פנסיוני) — Pension and insurance in Israel
"""
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional

import requests

# Financial blog RSS feeds
BLOG_FEEDS = {
    # ── Global blogs ──
    "calculated_risk": {
        "name": "Calculated Risk",
        "name_he": "Calculated Risk",
        "url": "https://www.calculatedriskblog.com/",
        "rss": "https://www.calculatedriskblog.com/feeds/posts/default?alt=rss",
        "description": "US real estate and macro — precise data tracking",
        "category": "macro",
        "language": "en",
    },
    "marginal_revolution": {
        "name": "Marginal Revolution",
        "name_he": "Marginal Revolution",
        "url": "https://marginalrevolution.com/",
        "rss": "https://marginalrevolution.com/feed",
        "description": "Tyler Cowen & Alex Tabarrok — intellectual economics blog",
        "category": "macro",
        "language": "en",
    },
    "money_stuff": {
        "name": "Money Stuff (Matt Levine)",
        "name_he": "Money Stuff",
        "url": "https://www.bloomberg.com/opinion/authors/ARbTQlRLRjE/matthew-s-levine",
        "rss": "https://newsletterfeed.com/moneystuff",
        "description": "Bloomberg newsletter — market analysis with sharp humor",
        "category": "markets",
        "language": "en",
    },
    "noahpinion": {
        "name": "Noahpinion (Noah Smith)",
        "name_he": "Noahpinion",
        "url": "https://noahpinion.substack.com/",
        "rss": "https://noahpinion.substack.com/feed",
        "description": "Accessible writing on policy, China, tech",
        "category": "macro",
        "language": "en",
    },
    "macro_compass": {
        "name": "The Macro Compass",
        "name_he": "The Macro Compass",
        "url": "https://themacrocompass.substack.com/",
        "rss": "https://themacrocompass.substack.com/feed",
        "description": "Alfonso Peccatiello — excellent macro and markets analysis",
        "category": "macro",
        "language": "en",
    },
    "kyla_scanlon": {
        "name": "Kyla Scanlon",
        "name_he": "Kyla Scanlon",
        "url": "https://kylascanlon.substack.com/",
        "rss": "https://kylascanlon.substack.com/feed",
        "description": "Visual and accessible macro explainer",
        "category": "macro",
        "language": "en",
    },
    "doomberg": {
        "name": "Doomberg",
        "name_he": "Doomberg",
        "url": "https://doomberg.substack.com/",
        "rss": "https://doomberg.substack.com/feed",
        "description": "Energy, commodities, economic geopolitics",
        "category": "energy",
        "language": "en",
    },
    "mauldin": {
        "name": "Thoughts from the Frontline",
        "name_he": "John Mauldin",
        "url": "https://www.mauldineconomics.com/",
        "rss": "https://www.mauldineconomics.com/feed",
        "description": "John Mauldin — weekly global macro letter",
        "category": "macro",
        "language": "en",
    },
    # ── Israeli blogs ──
    "hasolidit_blog": {
        "name": "הסולידית",
        "name_he": "הסולידית",
        "url": "https://www.hasolidit.com/",
        "rss": "https://www.hasolidit.com/feed",
        "description": "הבלוג הישראלי המוביל על השקעות פסיביות וכלכלה אישית",
        "category": "personal_finance",
        "language": "he",
    },
    "pensioni": {
        "name": "פנסיוני",
        "name_he": "פנסיוני",
        "url": "https://pensioni.co.il/",
        "rss": "https://pensioni.co.il/feed",
        "description": "בלוג על פנסיה וביטוח בישראל",
        "category": "personal_finance",
        "language": "he",
    },
}

# Cache
_blog_cache: dict[str, dict] = {}
CACHE_TTL = 1800  # 30 minutes

HEADERS = {
    "User-Agent": "TrendVest/1.0 (Financial Blog Aggregator)",
    "Accept": "application/rss+xml, application/xml, text/xml, application/atom+xml",
}


def _parse_blog_feed(rss_url: str, blog_key: str, blog_name: str, language: str) -> list[dict]:
    """Parse a blog RSS/Atom feed."""
    try:
        resp = requests.get(rss_url, timeout=15, headers=HEADERS)
        if resp.status_code != 200:
            return []

        root = ET.fromstring(resp.content)
        items = []
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        # RSS 2.0
        for item in root.findall(".//item"):
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "")
            description = item.findtext("description", "").strip()

            if title and link:
                items.append({
                    "title": title,
                    "url": link,
                    "source": blog_name,
                    "source_type": "blog",
                    "source_key": blog_key,
                    "published_at": pub_date,
                    "description": description[:300] if description else "",
                    "language": language,
                })

        # Atom fallback
        if not items:
            for entry in root.findall("atom:entry", ns):
                title = (entry.findtext("atom:title", "", ns) or "").strip()
                link_el = entry.find("atom:link", ns)
                link = link_el.get("href", "") if link_el is not None else ""
                pub_date = (
                    entry.findtext("atom:published", "", ns)
                    or entry.findtext("atom:updated", "", ns)
                )
                summary = (entry.findtext("atom:summary", "", ns) or "").strip()
                content = (entry.findtext("atom:content", "", ns) or "").strip()

                if title and link:
                    items.append({
                        "title": title,
                        "url": link,
                        "source": blog_name,
                        "source_type": "blog",
                        "source_key": blog_key,
                        "published_at": pub_date,
                        "description": (summary or content)[:300],
                        "language": language,
                    })

        return items[:10]
    except Exception as e:
        print(f"Blog feed error ({blog_key}): {e}")
        return []


def get_blog_posts(
    blog: Optional[str] = None,
    category: Optional[str] = None,
    language: Optional[str] = None,
    limit: int = 30,
) -> list[dict]:
    """
    Get latest blog posts from financial blogs.

    Args:
        blog: Filter by specific blog key
        category: Filter by category (macro, markets, energy, personal_finance)
        language: Filter by language (en, he)
        limit: Max items to return
    """
    cache_key = f"blog:{blog or 'all'}:{category or 'all'}:{language or 'all'}:{limit}"
    now = time.time()

    if cache_key in _blog_cache:
        cached = _blog_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    feeds_to_fetch = []
    for key, config in BLOG_FEEDS.items():
        if blog and key != blog:
            continue
        if category and config["category"] != category:
            continue
        if language and config["language"] != language:
            continue
        feeds_to_fetch.append((config["rss"], key, config["name"], config["language"]))

    all_items = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(_parse_blog_feed, rss, key, name, lang): key
            for rss, key, name, lang in feeds_to_fetch
        }
        for future in as_completed(futures):
            try:
                all_items.extend(future.result())
            except Exception:
                pass

    # Deduplicate
    seen = set()
    unique = []
    for item in all_items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)

    unique.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    result = unique[:limit]

    _blog_cache[cache_key] = {"time": now, "data": result}
    return result
