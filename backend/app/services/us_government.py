"""
US Government economic data sources for TrendVest.
Free — no API keys needed for RSS. BEA/BLS APIs have free keys.
Sources:
- BEA (Bureau of Economic Analysis) — GDP, trade, income data
- BLS (Bureau of Labor Statistics) — employment, CPI, wages
- NBER (National Bureau of Economic Research) — academic papers, recession indicators
"""
import os
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional

import requests

# US Government data RSS feeds
US_GOV_FEEDS = {
    "bea": {
        "name": "Bureau of Economic Analysis",
        "name_short": "BEA",
        "feeds": [
            "https://www.bea.gov/rss/rss.xml",
        ],
        "category": "macro",
    },
    "bls": {
        "name": "Bureau of Labor Statistics",
        "name_short": "BLS",
        "feeds": [
            "https://www.bls.gov/feed/bls_latest.rss",
        ],
        "category": "employment",
    },
    "nber": {
        "name": "National Bureau of Economic Research",
        "name_short": "NBER",
        "feeds": [
            "https://www.nber.org/rss/new.xml",
        ],
        "category": "research",
    },
    "treasury": {
        "name": "US Treasury",
        "name_short": "Treasury",
        "feeds": [
            "https://home.treasury.gov/system/files/RSS/press-rss.xml",
        ],
        "category": "fiscal",
    },
}

# Cache
_us_gov_cache: dict[str, dict] = {}
CACHE_TTL = 1800  # 30 minutes

HEADERS = {
    "User-Agent": "TrendVest/1.0 (Economic Data Aggregator)",
    "Accept": "application/rss+xml, application/xml, text/xml",
}


def _parse_us_gov_feed(url: str, source_key: str, source_name: str, category: str) -> list[dict]:
    """Parse a US government RSS feed."""
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
                    "source_type": "us_gov",
                    "source_key": source_key,
                    "category": category,
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
                        "source_type": "us_gov",
                        "source_key": source_key,
                        "category": category,
                        "published_at": pub_date,
                        "description": summary[:200] if summary else "",
                        "language": "en",
                    })

        return items[:15]
    except Exception as e:
        print(f"US Gov feed error ({source_key} - {url}): {e}")
        return []


def get_us_gov_data(
    source: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 30,
) -> list[dict]:
    """
    Get US government economic data releases.

    Args:
        source: Filter by source key (bea, bls, nber, treasury)
        category: Filter by category (macro, employment, research, fiscal)
        limit: Max items to return
    """
    cache_key = f"usgov:{source or 'all'}:{category or 'all'}:{limit}"
    now = time.time()

    if cache_key in _us_gov_cache:
        cached = _us_gov_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    feeds_to_fetch = []
    for key, config in US_GOV_FEEDS.items():
        if source and key != source:
            continue
        if category and config["category"] != category:
            continue
        for feed_url in config["feeds"]:
            feeds_to_fetch.append((feed_url, key, config["name"], config["category"]))

    all_items = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(_parse_us_gov_feed, url, key, name, cat): key
            for url, key, name, cat in feeds_to_fetch
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

    _us_gov_cache[cache_key] = {"time": now, "data": result}
    return result
