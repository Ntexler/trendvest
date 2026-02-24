"""
Global financial news RSS feeds for TrendVest.
Free — no API key needed. Aggregates from The Economist, Financial Times,
Wall Street Journal, Bloomberg, Seeking Alpha, Benzinga, Handelsblatt,
Les Echos, and other major financial publications worldwide.
"""
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional

import requests

# Global financial news RSS feeds
GLOBAL_FEEDS = {
    "economist": {
        "name": "The Economist",
        "feeds": [
            "https://www.economist.com/finance-and-economics/rss.xml",
            "https://www.economist.com/business/rss.xml",
            "https://www.economist.com/science-and-technology/rss.xml",
        ],
        "logo": "https://www.economist.com/favicon.ico",
    },
    "ft": {
        "name": "Financial Times",
        "feeds": [
            "https://www.ft.com/rss/home",
            "https://www.ft.com/markets?format=rss",
            "https://www.ft.com/technology?format=rss",
        ],
        "logo": "https://www.ft.com/favicon.ico",
    },
    "seeking_alpha": {
        "name": "Seeking Alpha",
        "feeds": [
            "https://seekingalpha.com/market_currents.xml",
            "https://seekingalpha.com/tag/wall-st-breakfast.xml",
        ],
        "logo": "https://seekingalpha.com/favicon.ico",
    },
    "benzinga": {
        "name": "Benzinga",
        "feeds": [
            "https://www.benzinga.com/feed",
        ],
        "logo": "https://www.benzinga.com/favicon.ico",
    },
    "reuters": {
        "name": "Reuters",
        "feeds": [
            "https://www.reutersagency.com/feed/?taxonomy=best-sectors&post_type=best",
        ],
        "logo": "https://www.reuters.com/favicon.ico",
    },
    "cnbc": {
        "name": "CNBC",
        "feeds": [
            "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147",  # Top News
            "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069",  # Tech
        ],
        "logo": "https://www.cnbc.com/favicon.ico",
    },
    "wsj": {
        "name": "Wall Street Journal",
        "feeds": [
            "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",      # Markets
            "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml",     # Business
            "https://feeds.a.dj.com/rss/RSSWSJD.xml",             # Tech
        ],
        "logo": "https://www.wsj.com/favicon.ico",
    },
    "bloomberg": {
        "name": "Bloomberg",
        "feeds": [
            "https://feeds.bloomberg.com/markets/news.rss",
            "https://feeds.bloomberg.com/technology/news.rss",
        ],
        "logo": "https://www.bloomberg.com/favicon.ico",
    },
    "handelsblatt": {
        "name": "Handelsblatt",
        "feeds": [
            "https://www.handelsblatt.com/contentexport/feed/finanzen",
        ],
        "logo": "https://www.handelsblatt.com/favicon.ico",
    },
    "les_echos": {
        "name": "Les Echos",
        "feeds": [
            "https://syndication.lesechos.fr/rss/rss_finance_marches.xml",
        ],
        "logo": "https://www.lesechos.fr/favicon.ico",
    },
}

# Cache
_global_rss_cache: dict[str, dict] = {}
CACHE_TTL = 900  # 15 minutes


def _parse_global_rss(url: str, source_key: str, source_name: str) -> list[dict]:
    """Parse a single RSS/Atom feed and return normalized news items."""
    try:
        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "TrendVest/1.0 (Financial News Aggregator)",
            "Accept": "application/rss+xml, application/xml, text/xml, application/atom+xml",
        })
        if resp.status_code != 200:
            return []

        root = ET.fromstring(resp.content)
        items = []

        ns = {"atom": "http://www.w3.org/2005/Atom", "media": "http://search.yahoo.com/mrss/"}

        # Try RSS 2.0
        for item in root.findall(".//item"):
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "")
            description = item.findtext("description", "").strip()

            image_url = ""
            media_content = item.find("{http://search.yahoo.com/mrss/}content")
            if media_content is not None:
                image_url = media_content.get("url", "")
            media_thumb = item.find("{http://search.yahoo.com/mrss/}thumbnail")
            if not image_url and media_thumb is not None:
                image_url = media_thumb.get("url", "")
            enclosure = item.find("enclosure")
            if not image_url and enclosure is not None and "image" in enclosure.get("type", ""):
                image_url = enclosure.get("url", "")

            if title and link:
                items.append({
                    "title": title,
                    "url": link,
                    "source": source_name,
                    "source_type": "global_news",
                    "source_key": source_key,
                    "published_at": pub_date,
                    "image_url": image_url,
                    "description": description[:200] if description else "",
                    "related_ticker": None,
                    "related_topic": None,
                    "language": "en",
                })

        # Try Atom if no RSS items found
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
                        "source_type": "global_news",
                        "source_key": source_key,
                        "published_at": pub_date,
                        "image_url": "",
                        "description": summary[:200] if summary else "",
                        "related_ticker": None,
                        "related_topic": None,
                        "language": "en",
                    })

        return items[:15]
    except Exception as e:
        print(f"Global RSS error ({source_key} - {url}): {e}")
        return []


def get_global_news(
    source: Optional[str] = None,
    limit: int = 30,
) -> list[dict]:
    """
    Get global financial news from major publications.

    Args:
        source: Filter by source key (economist, ft, seeking_alpha, benzinga, reuters, cnbc)
        limit: Max items to return
    """
    cache_key = f"global:{source or 'all'}:{limit}"
    now = time.time()

    if cache_key in _global_rss_cache:
        cached = _global_rss_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    feeds_to_fetch = []
    sources = {source: GLOBAL_FEEDS[source]} if source and source in GLOBAL_FEEDS else GLOBAL_FEEDS

    for key, config in sources.items():
        for feed_url in config["feeds"]:
            feeds_to_fetch.append((feed_url, key, config["name"]))

    all_items = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(_parse_global_rss, url, key, name): key
            for url, key, name in feeds_to_fetch
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

    # Sort by published_at (newest first)
    unique.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    result = unique[:limit]

    _global_rss_cache[cache_key] = {"time": now, "data": result}
    return result


def match_global_news_to_topics(news_items: list[dict], topic_keywords: dict[str, list[str]]) -> list[dict]:
    """Match global news to topics by keyword matching."""
    for item in news_items:
        text = (item.get("title", "") + " " + item.get("description", "")).lower()
        for slug, keywords in topic_keywords.items():
            for kw in keywords:
                if kw.lower() in text:
                    item["related_topic"] = slug
                    break
            if item.get("related_topic"):
                break
    return news_items
