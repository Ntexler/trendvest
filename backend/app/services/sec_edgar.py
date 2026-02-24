"""
SEC EDGAR RSS feed service for TrendVest.
Free — no API key needed. Provides real-time SEC filings (10-K, 10-Q, 8-K, etc.).
Rate limit: max 10 requests/second (SEC fair access policy).
"""
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional

import requests

# SEC EDGAR RSS endpoints
SEC_FEEDS = {
    "latest": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&dateb=&owner=include&count=40&search_text=&start=0&output=atom",
    "10k": "https://efts.sec.gov/LATEST/search-index?q=%2210-K%22&dateRange=custom&startdt={from_date}&enddt={to_date}&forms=10-K",
    "8k": "https://efts.sec.gov/LATEST/search-index?q=%228-K%22&dateRange=custom&startdt={from_date}&enddt={to_date}&forms=8-K",
}

# EDGAR full-text search API (EFTS)
EFTS_BASE = "https://efts.sec.gov/LATEST/search-index"
EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"

# Cache
_sec_cache: dict[str, dict] = {}
CACHE_TTL = 600  # 10 minutes

# SEC requires identifying User-Agent
SEC_HEADERS = {
    "User-Agent": "TrendVest info@trendvest.app",
    "Accept": "application/atom+xml, application/xml, text/xml",
}


def get_company_filings(ticker: str, filing_type: str = "", limit: int = 10) -> list[dict]:
    """
    Get recent SEC filings for a specific company.

    Args:
        ticker: Stock ticker (e.g. "NVDA")
        filing_type: Filter by type (10-K, 10-Q, 8-K, etc.) or empty for all
        limit: Max filings to return
    """
    cache_key = f"sec:company:{ticker}:{filing_type}:{limit}"
    now = time.time()
    if cache_key in _sec_cache:
        cached = _sec_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    try:
        url = "https://efts.sec.gov/LATEST/search-index"
        params = {
            "q": f'"{ticker}"',
            "dateRange": "custom",
            "forms": filing_type if filing_type else "10-K,10-Q,8-K,S-1,4",
        }

        resp = requests.get(url, params=params, headers=SEC_HEADERS, timeout=10)
        time.sleep(0.2)  # Respect SEC rate limit

        if resp.status_code != 200:
            # Fallback to EDGAR company search
            return _get_filings_rss(ticker, filing_type, limit)

        data = resp.json()
        hits = data.get("hits", {}).get("hits", [])

        results = []
        for hit in hits[:limit]:
            source = hit.get("_source", {})
            results.append({
                "title": source.get("display_names", [ticker])[0] + " — " + source.get("form_type", "Filing"),
                "url": f"https://www.sec.gov/Archives/edgar/data/{source.get('entity_id', '')}/{source.get('file_num', '')}",
                "source": "SEC EDGAR",
                "source_type": "sec_filing",
                "filing_type": source.get("form_type", ""),
                "published_at": source.get("file_date", ""),
                "description": source.get("display_names", [""])[0],
                "related_ticker": ticker.upper(),
                "related_topic": None,
                "language": "en",
            })

        _sec_cache[cache_key] = {"time": now, "data": results}
        return results

    except Exception as e:
        print(f"SEC EDGAR error for {ticker}: {e}")
        return _get_filings_rss(ticker, filing_type, limit)


def _get_filings_rss(ticker: str, filing_type: str = "", limit: int = 10) -> list[dict]:
    """Fallback: get filings via EDGAR RSS/Atom feed."""
    try:
        type_param = filing_type if filing_type else ""
        url = (
            f"https://www.sec.gov/cgi-bin/browse-edgar?"
            f"action=getcompany&company={ticker}&type={type_param}"
            f"&dateb=&owner=include&count={limit}&search_text=&action=getcompany&output=atom"
        )
        resp = requests.get(url, headers=SEC_HEADERS, timeout=10)
        time.sleep(0.2)

        if resp.status_code != 200:
            return []

        root = ET.fromstring(resp.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        results = []
        for entry in root.findall("atom:entry", ns):
            title = (entry.findtext("atom:title", "", ns) or "").strip()
            link_el = entry.find("atom:link", ns)
            link = link_el.get("href", "") if link_el is not None else ""
            updated = entry.findtext("atom:updated", "", ns)
            summary = (entry.findtext("atom:summary", "", ns) or "").strip()

            # Extract filing type from title
            ft = ""
            if " - " in title:
                ft = title.split(" - ")[0].strip()

            if title and link:
                results.append({
                    "title": title,
                    "url": link,
                    "source": "SEC EDGAR",
                    "source_type": "sec_filing",
                    "filing_type": ft,
                    "published_at": updated,
                    "description": summary[:200] if summary else "",
                    "related_ticker": ticker.upper(),
                    "related_topic": None,
                    "language": "en",
                })

        return results[:limit]

    except Exception as e:
        print(f"SEC EDGAR RSS fallback error: {e}")
        return []


def get_latest_filings(filing_types: Optional[list[str]] = None, limit: int = 20) -> list[dict]:
    """
    Get latest SEC filings across all companies.

    Args:
        filing_types: Filter by filing types (e.g. ["10-K", "8-K"])
        limit: Max filings to return
    """
    cache_key = f"sec:latest:{','.join(filing_types or [])}:{limit}"
    now = time.time()
    if cache_key in _sec_cache:
        cached = _sec_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    try:
        url = SEC_FEEDS["latest"]
        resp = requests.get(url, headers=SEC_HEADERS, timeout=10)
        time.sleep(0.2)

        if resp.status_code != 200:
            return []

        root = ET.fromstring(resp.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        results = []
        for entry in root.findall("atom:entry", ns):
            title = (entry.findtext("atom:title", "", ns) or "").strip()
            link_el = entry.find("atom:link", ns)
            link = link_el.get("href", "") if link_el is not None else ""
            updated = entry.findtext("atom:updated", "", ns)
            summary = (entry.findtext("atom:summary", "", ns) or "").strip()

            # Filter by filing type if specified
            if filing_types:
                matched = any(ft in title for ft in filing_types)
                if not matched:
                    continue

            if title and link:
                results.append({
                    "title": title,
                    "url": link,
                    "source": "SEC EDGAR",
                    "source_type": "sec_filing",
                    "published_at": updated,
                    "description": summary[:200] if summary else "",
                    "related_ticker": None,
                    "related_topic": None,
                    "language": "en",
                })

        result = results[:limit]
        _sec_cache[cache_key] = {"time": now, "data": result}
        return result

    except Exception as e:
        print(f"SEC EDGAR latest filings error: {e}")
        return []
