"""
Israeli institutional data sources for TrendVest.
Free — no API keys needed. Aggregates from:
- Bank of Israel (בנק ישראל) — monetary reports, interest rates, inflation
- Central Bureau of Statistics (למ"ס) — macro data, employment, indices
- Israel Securities Authority (רשות ני"ע) — company reports, regulation
- TASE (הבורסה) — market data, announcements
- Aaron Institute / Reichman — economic policy research
- Taub Center — socio-economic research
- S&P Maalot — local credit ratings
"""
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional

import requests

# Israeli institutional RSS/data feeds
INSTITUTIONAL_FEEDS = {
    "boi": {
        "name": "בנק ישראל",
        "name_en": "Bank of Israel",
        "feeds": [
            "https://www.boi.org.il/he/DataAndStatistics/Pages/RSS.aspx",
            "https://www.boi.org.il/he/NewsAndPublications/PressReleases/Pages/RSS.aspx",
        ],
        "category": "monetary",
        "logo": "https://www.boi.org.il/favicon.ico",
    },
    "cbs": {
        "name": "הלמ\"ס",
        "name_en": "Central Bureau of Statistics",
        "feeds": [
            "https://www.cbs.gov.il/he/RSS/Pages/default.aspx",
        ],
        "category": "macro",
        "logo": "https://www.cbs.gov.il/favicon.ico",
    },
    "isa": {
        "name": "רשות ני\"ע",
        "name_en": "Israel Securities Authority",
        "feeds": [
            "https://www.isa.gov.il/RSS/Pages/default.aspx",
        ],
        "category": "regulation",
        "logo": "https://www.isa.gov.il/favicon.ico",
    },
    "tase_institutional": {
        "name": "הבורסה לני\"ע",
        "name_en": "TASE",
        "feeds": [
            "https://maya.tase.co.il/rss/news",
            "https://maya.tase.co.il/rss/company",
        ],
        "category": "market",
        "logo": "https://maya.tase.co.il/favicon.ico",
    },
    "aaron_institute": {
        "name": "מכון אהרן",
        "name_en": "Aaron Institute (Reichman)",
        "feeds": [
            "https://www.runi.ac.il/research-institutes/economics/aaron-institute/feed/",
        ],
        "category": "research",
        "logo": "https://www.runi.ac.il/favicon.ico",
    },
    "taub_center": {
        "name": "מרכז טאוב",
        "name_en": "Taub Center",
        "feeds": [
            "https://www.taubcenter.org.il/he/feed/",
        ],
        "category": "research",
        "logo": "https://www.taubcenter.org.il/favicon.ico",
    },
    "sp_maalot": {
        "name": "S&P מעלות",
        "name_en": "S&P Maalot",
        "feeds": [
            "https://www.maalot.co.il/rss/RatingActions.xml",
        ],
        "category": "ratings",
        "logo": "https://www.maalot.co.il/favicon.ico",
    },
}

# Cache
_inst_cache: dict[str, dict] = {}
CACHE_TTL = 1800  # 30 minutes (institutional data updates less frequently)

# Standard headers
HEADERS = {
    "User-Agent": "TrendVest/1.0 (Financial Data Aggregator)",
    "Accept": "application/rss+xml, application/xml, text/xml, application/atom+xml",
}


def _parse_institutional_feed(url: str, source_key: str, source_name: str, category: str) -> list[dict]:
    """Parse a single institutional RSS/Atom feed."""
    try:
        resp = requests.get(url, timeout=15, headers=HEADERS)
        if resp.status_code != 200:
            return []

        root = ET.fromstring(resp.content)
        items = []
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        # Try RSS 2.0
        for item in root.findall(".//item"):
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "")
            description = item.findtext("description", "").strip()

            if title and link:
                items.append({
                    "title": title,
                    "url": link,
                    "source": source_name,
                    "source_type": "il_institutional",
                    "source_key": source_key,
                    "category": category,
                    "published_at": pub_date,
                    "description": description[:200] if description else "",
                    "language": "he",
                })

        # Try Atom
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

                if title and link:
                    items.append({
                        "title": title,
                        "url": link,
                        "source": source_name,
                        "source_type": "il_institutional",
                        "source_key": source_key,
                        "category": category,
                        "published_at": pub_date,
                        "description": summary[:200] if summary else "",
                        "language": "he",
                    })

        return items[:10]
    except Exception as e:
        print(f"Institutional feed error ({source_key} - {url}): {e}")
        return []


def get_institutional_data(
    source: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 30,
) -> list[dict]:
    """
    Get data from Israeli institutional sources.

    Args:
        source: Filter by source key (boi, cbs, isa, tase_institutional, etc.)
        category: Filter by category (monetary, macro, regulation, market, research, ratings)
        limit: Max items to return
    """
    cache_key = f"inst:{source or 'all'}:{category or 'all'}:{limit}"
    now = time.time()

    if cache_key in _inst_cache:
        cached = _inst_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    feeds_to_fetch = []
    for key, config in INSTITUTIONAL_FEEDS.items():
        if source and key != source:
            continue
        if category and config["category"] != category:
            continue
        for feed_url in config["feeds"]:
            feeds_to_fetch.append((feed_url, key, config["name"], config["category"]))

    all_items = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(_parse_institutional_feed, url, key, name, cat): key
            for url, key, name, cat in feeds_to_fetch
        }
        for future in as_completed(futures):
            try:
                all_items.extend(future.result())
            except Exception:
                pass

    # Deduplicate by title
    seen = set()
    unique = []
    for item in all_items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)

    # Sort by published_at
    unique.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    result = unique[:limit]

    _inst_cache[cache_key] = {"time": now, "data": result}
    return result
