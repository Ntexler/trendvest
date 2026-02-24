"""
Israeli news sources for TrendVest — aggregates financial news
from Globes, Calcalist, Geektime, and TheMarker via RSS feeds.
"""
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional

import requests

# Israeli financial news RSS feeds
ISRAELI_FEEDS = {
    "globes": {
        "name": "גלובס",
        "name_en": "Globes",
        "feeds": [
            "https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=2",     # שוק ההון
            "https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=585",   # טכנולוגיה
        ],
        "logo": "https://www.globes.co.il/images/globes-logo.svg",
    },
    "calcalist": {
        "name": "כלכליסט",
        "name_en": "Calcalist",
        "feeds": [
            "https://www.calcalist.co.il/GeneralRSS/0,16335,L-8,00.xml",   # שוק ההון
            "https://www.calcalist.co.il/GeneralRSS/0,16335,L-4,00.xml",   # טכנולוגיה
        ],
        "logo": "https://www.calcalist.co.il/images/logo.svg",
    },
    "geektime": {
        "name": "גיקטיים",
        "name_en": "Geektime",
        "feeds": [
            "https://www.geektime.co.il/feed/",
        ],
        "logo": "https://www.geektime.co.il/wp-content/themes/flavor-developer/favicon.ico",
    },
    "themarker": {
        "name": "דה מרקר",
        "name_en": "TheMarker",
        "feeds": [
            "https://www.themarker.com/cmlink/1.145",   # שוק ההון
        ],
        "logo": "https://www.themarker.com/images/themarker-logo.svg",
    },
}

# Simple cache
_il_news_cache: dict[str, dict] = {}
CACHE_TTL = 600  # 10 minutes


def _parse_rss_feed(url: str, source_key: str, source_name: str) -> list[dict]:
    """Parse a single RSS feed and return normalized news items."""
    try:
        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "TrendVest/1.0 (Financial News Aggregator)",
            "Accept": "application/rss+xml, application/xml, text/xml",
        })
        if resp.status_code != 200:
            return []

        root = ET.fromstring(resp.content)
        items = []

        # Handle both RSS 2.0 and Atom feeds
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        # Try RSS 2.0 first
        for item in root.findall(".//item"):
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "")
            description = item.findtext("description", "").strip()

            # Try to extract image from description or media:content
            image_url = ""
            media_content = item.find("{http://search.yahoo.com/mrss/}content")
            if media_content is not None:
                image_url = media_content.get("url", "")
            enclosure = item.find("enclosure")
            if not image_url and enclosure is not None and "image" in (enclosure.get("type", "")):
                image_url = enclosure.get("url", "")

            if title and link:
                items.append({
                    "title": title,
                    "url": link,
                    "source": source_name,
                    "source_type": "il_news",
                    "source_key": source_key,
                    "published_at": pub_date,
                    "image_url": image_url,
                    "description": description[:200] if description else "",
                    "related_ticker": None,
                    "related_topic": None,
                    "language": "he",
                })

        # Try Atom if no RSS items found
        if not items:
            for entry in root.findall("atom:entry", ns):
                title = (entry.findtext("atom:title", "", ns) or "").strip()
                link_el = entry.find("atom:link", ns)
                link = link_el.get("href", "") if link_el is not None else ""
                pub_date = entry.findtext("atom:published", "", ns) or entry.findtext("atom:updated", "", ns)

                if title and link:
                    items.append({
                        "title": title,
                        "url": link,
                        "source": source_name,
                        "source_type": "il_news",
                        "source_key": source_key,
                        "published_at": pub_date,
                        "image_url": "",
                        "description": "",
                        "related_ticker": None,
                        "related_topic": None,
                        "language": "he",
                    })

        return items[:15]
    except Exception as e:
        print(f"Israeli RSS error ({source_key} - {url}): {e}")
        return []


def get_israeli_news(
    source: Optional[str] = None,
    limit: int = 30,
) -> list[dict]:
    """
    Get Israeli financial news from RSS feeds.

    Args:
        source: Filter by specific source key (globes, calcalist, geektime, themarker)
        limit: Max items to return
    """
    cache_key = f"il:{source or 'all'}:{limit}"
    now = time.time()

    if cache_key in _il_news_cache:
        cached = _il_news_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    feeds_to_fetch = []
    sources = {source: ISRAELI_FEEDS[source]} if source and source in ISRAELI_FEEDS else ISRAELI_FEEDS

    for key, config in sources.items():
        for feed_url in config["feeds"]:
            feeds_to_fetch.append((feed_url, key, config["name"]))

    all_items = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(_parse_rss_feed, url, key, name): key
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

    # Sort by published_at (newest first) - best effort
    unique.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    result = unique[:limit]

    _il_news_cache[cache_key] = {"time": now, "data": result}
    return result


def match_israeli_news_to_topics(news_items: list[dict], topic_keywords: dict[str, list[str]]) -> list[dict]:
    """
    Match Israeli news to topics by keyword matching.

    Args:
        news_items: List of news items
        topic_keywords: Dict of {topic_slug: [keywords]}
    """
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
