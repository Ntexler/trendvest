"""
International institutional data sources for TrendVest.
Free — no API keys needed. Central banks, statistical agencies, and research institutes.

Europe:
- ECB (European Central Bank) — Eurozone monetary policy
- Eurostat — EU statistics
- Deutsche Bundesbank — German economic research
- Bank of England — UK monetary policy
- OECD — International economic policy research
- Bruegel — European economic research

Asia:
- Bank of Japan — Japanese monetary policy
- PBOC — Chinese monetary policy
- Nikkei Asia — Asian financial news
- Caixin — Chinese financial news
- SCMP — Hong Kong financial news
- RBI — Indian monetary policy
- Economic Times India — Indian financial news
- ADB — Asian development research

Global:
- World Bank — Global development data
- IMF — International monetary research
"""
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional

import requests

# International institutional RSS feeds
INTL_INSTITUTIONAL_FEEDS = {
    "ecb": {
        "name": "European Central Bank",
        "name_short": "ECB",
        "region": "europe",
        "feeds": [
            "https://www.ecb.europa.eu/rss/press.html",
            "https://www.ecb.europa.eu/rss/pub.html",
        ],
        "category": "monetary",
    },
    "eurostat": {
        "name": "Eurostat",
        "name_short": "Eurostat",
        "region": "europe",
        "feeds": [
            "https://ec.europa.eu/eurostat/web/main/news/euro-indicators/rss",
        ],
        "category": "macro",
    },
    "bundesbank": {
        "name": "Deutsche Bundesbank",
        "name_short": "Bundesbank",
        "region": "europe",
        "feeds": [
            "https://www.bundesbank.de/SiteGlobals/Functions/RSSFeed/EN/RSSNewsfeed/rssnewsfeed.rss",
        ],
        "category": "monetary",
    },
    "boe": {
        "name": "Bank of England",
        "name_short": "BoE",
        "region": "europe",
        "feeds": [
            "https://www.bankofengland.co.uk/rss/speeches",
            "https://www.bankofengland.co.uk/rss/news",
        ],
        "category": "monetary",
    },
    "oecd": {
        "name": "OECD",
        "name_short": "OECD",
        "region": "international",
        "feeds": [
            "https://www.oecd.org/newsroom/news.rss",
        ],
        "category": "research",
    },
    "bruegel": {
        "name": "Bruegel",
        "name_short": "Bruegel",
        "region": "europe",
        "feeds": [
            "https://www.bruegel.org/rss.xml",
        ],
        "category": "research",
    },
    "worldbank": {
        "name": "World Bank",
        "name_short": "World Bank",
        "region": "international",
        "feeds": [
            "https://blogs.worldbank.org/feed",
        ],
        "category": "development",
    },
    "imf": {
        "name": "International Monetary Fund",
        "name_short": "IMF",
        "region": "international",
        "feeds": [
            "https://www.imf.org/en/News/Rss?language=eng",
        ],
        "category": "monetary",
    },
    # ── Asia ──
    "boj": {
        "name": "Bank of Japan",
        "name_short": "BOJ",
        "region": "asia",
        "feeds": [
            "https://www.boj.or.jp/en/rss/whatsnew.xml",
        ],
        "category": "monetary",
    },
    "pboc": {
        "name": "People's Bank of China",
        "name_short": "PBOC",
        "region": "asia",
        "feeds": [
            "http://www.pbc.gov.cn/english/rss/index.xml",
        ],
        "category": "monetary",
    },
    "nikkei_asia": {
        "name": "Nikkei Asia",
        "name_short": "Nikkei",
        "region": "asia",
        "feeds": [
            "https://asia.nikkei.com/rss/feed/nar",
        ],
        "category": "news",
    },
    "caixin": {
        "name": "Caixin Global",
        "name_short": "Caixin",
        "region": "asia",
        "feeds": [
            "https://www.caixinglobal.com/rss/feed.xml",
        ],
        "category": "news",
    },
    "scmp": {
        "name": "South China Morning Post",
        "name_short": "SCMP",
        "region": "asia",
        "feeds": [
            "https://www.scmp.com/rss/91/feed",       # Business
            "https://www.scmp.com/rss/92/feed",       # Economy
        ],
        "category": "news",
    },
    "rbi": {
        "name": "Reserve Bank of India",
        "name_short": "RBI",
        "region": "asia",
        "feeds": [
            "https://rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?output=rss",
        ],
        "category": "monetary",
    },
    "economic_times": {
        "name": "The Economic Times",
        "name_short": "ET India",
        "region": "asia",
        "feeds": [
            "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
            "https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms",
        ],
        "category": "news",
    },
    "adb": {
        "name": "Asian Development Bank",
        "name_short": "ADB",
        "region": "asia",
        "feeds": [
            "https://www.adb.org/news/feed",
        ],
        "category": "development",
    },
    "straits_times": {
        "name": "The Straits Times",
        "name_short": "ST",
        "region": "asia",
        "feeds": [
            "https://www.straitstimes.com/news/business/rss.xml",
        ],
        "category": "news",
    },
}

# Cache
_intl_cache: dict[str, dict] = {}
CACHE_TTL = 1800  # 30 minutes

HEADERS = {
    "User-Agent": "TrendVest/1.0 (Economic Data Aggregator)",
    "Accept": "application/rss+xml, application/xml, text/xml, application/atom+xml",
}


def _parse_intl_feed(url: str, source_key: str, source_name: str, category: str, region: str) -> list[dict]:
    """Parse an international institutional RSS/Atom feed."""
    try:
        resp = requests.get(url, timeout=15, headers=HEADERS)
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
                    "source": source_name,
                    "source_type": "intl_institutional",
                    "source_key": source_key,
                    "category": category,
                    "region": region,
                    "published_at": pub_date,
                    "description": description[:200] if description else "",
                    "language": "en",
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

                if title and link:
                    items.append({
                        "title": title,
                        "url": link,
                        "source": source_name,
                        "source_type": "intl_institutional",
                        "source_key": source_key,
                        "category": category,
                        "region": region,
                        "published_at": pub_date,
                        "description": summary[:200] if summary else "",
                        "language": "en",
                    })

        return items[:10]
    except Exception as e:
        print(f"Intl institutional feed error ({source_key} - {url}): {e}")
        return []


def get_international_data(
    source: Optional[str] = None,
    region: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 30,
) -> list[dict]:
    """
    Get data from international institutional sources.

    Args:
        source: Filter by source key (ecb, eurostat, boe, oecd, boj, pboc, nikkei_asia, etc.)
        region: Filter by region (europe, asia, international)
        category: Filter by category (monetary, macro, research, development, news)
        limit: Max items to return
    """
    cache_key = f"intl:{source or 'all'}:{region or 'all'}:{category or 'all'}:{limit}"
    now = time.time()

    if cache_key in _intl_cache:
        cached = _intl_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    feeds_to_fetch = []
    for key, config in INTL_INSTITUTIONAL_FEEDS.items():
        if source and key != source:
            continue
        if region and config["region"] != region:
            continue
        if category and config["category"] != category:
            continue
        for feed_url in config["feeds"]:
            feeds_to_fetch.append((feed_url, key, config["name"], config["category"], config["region"]))

    all_items = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(_parse_intl_feed, url, key, name, cat, reg): key
            for url, key, name, cat, reg in feeds_to_fetch
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

    _intl_cache[cache_key] = {"time": now, "data": result}
    return result
