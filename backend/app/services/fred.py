"""
FRED (Federal Reserve Economic Data) API service for TrendVest.
Free — requires API key (unlimited requests with key).
Get API key: https://fred.stlouisfed.org/docs/api/api_key.html

Provides macroeconomic indicators: GDP, CPI, unemployment, interest rates, etc.
"""
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests

# Cache
_fred_cache: dict[str, dict] = {}
CACHE_TTL = 3600  # 1 hour (macro data doesn't change often)

# Key economic indicators tracked
MACRO_INDICATORS = {
    "GDP": {
        "series_id": "GDP",
        "name": "Gross Domestic Product",
        "name_he": "תוצר מקומי גולמי",
        "frequency": "quarterly",
    },
    "CPIAUCSL": {
        "series_id": "CPIAUCSL",
        "name": "Consumer Price Index (CPI)",
        "name_he": "מדד המחירים לצרכן",
        "frequency": "monthly",
    },
    "UNRATE": {
        "series_id": "UNRATE",
        "name": "Unemployment Rate",
        "name_he": "שיעור האבטלה",
        "frequency": "monthly",
    },
    "FEDFUNDS": {
        "series_id": "FEDFUNDS",
        "name": "Federal Funds Rate",
        "name_he": "ריבית הפד",
        "frequency": "monthly",
    },
    "DGS10": {
        "series_id": "DGS10",
        "name": "10-Year Treasury Yield",
        "name_he": "תשואת אג\"ח 10 שנים",
        "frequency": "daily",
    },
    "T10YIE": {
        "series_id": "T10YIE",
        "name": "10-Year Breakeven Inflation",
        "name_he": "ציפיות אינפלציה 10 שנים",
        "frequency": "daily",
    },
    "VIXCLS": {
        "series_id": "VIXCLS",
        "name": "VIX Volatility Index",
        "name_he": "מדד הפחד VIX",
        "frequency": "daily",
    },
    "DCOILWTICO": {
        "series_id": "DCOILWTICO",
        "name": "Crude Oil Price (WTI)",
        "name_he": "מחיר נפט WTI",
        "frequency": "daily",
    },
}


class FredCollector:
    """Collects macroeconomic data from FRED API."""

    BASE_URL = "https://api.stlouisfed.org/fred"

    def __init__(self):
        self.api_key = os.getenv("FRED_API_KEY", "")

    def _get(self, endpoint: str, params: dict) -> Optional[dict]:
        if not self.api_key:
            return None
        params["api_key"] = self.api_key
        params["file_type"] = "json"
        try:
            resp = requests.get(
                f"{self.BASE_URL}/{endpoint}",
                params=params,
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
            print(f"FRED {endpoint} returned {resp.status_code}")
            return None
        except Exception as e:
            print(f"FRED error ({endpoint}): {e}")
            return None

    def get_series_latest(self, series_id: str, count: int = 10) -> Optional[dict]:
        """
        Get latest observations for a FRED series.
        Returns the most recent data points.
        """
        cache_key = f"fred:series:{series_id}:{count}"
        now = time.time()
        if cache_key in _fred_cache:
            cached = _fred_cache[cache_key]
            if now - cached["time"] < CACHE_TTL:
                return cached["data"]

        data = self._get("series/observations", {
            "series_id": series_id,
            "sort_order": "desc",
            "limit": count,
        })

        if not data:
            return None

        observations = data.get("observations", [])
        if not observations:
            return None

        # Parse observations
        points = []
        for obs in observations:
            val = obs.get("value", ".")
            if val == ".":
                continue
            points.append({
                "date": obs.get("date", ""),
                "value": float(val),
            })

        if not points:
            return None

        # Calculate change
        latest = points[0]["value"]
        previous = points[1]["value"] if len(points) > 1 else latest
        change = latest - previous
        change_pct = (change / previous * 100) if previous != 0 else 0

        indicator_info = MACRO_INDICATORS.get(series_id, {})
        result = {
            "series_id": series_id,
            "name": indicator_info.get("name", series_id),
            "name_he": indicator_info.get("name_he", series_id),
            "latest_value": latest,
            "previous_value": previous,
            "change": round(change, 4),
            "change_pct": round(change_pct, 2),
            "latest_date": points[0]["date"],
            "frequency": indicator_info.get("frequency", "unknown"),
            "history": list(reversed(points)),  # Oldest first for charts
        }

        _fred_cache[cache_key] = {"time": now, "data": result}
        return result

    def get_macro_dashboard(self) -> list[dict]:
        """
        Get all tracked macro indicators — returns a dashboard overview.
        """
        cache_key = "fred:dashboard"
        now = time.time()
        if cache_key in _fred_cache:
            cached = _fred_cache[cache_key]
            if now - cached["time"] < CACHE_TTL:
                return cached["data"]

        results = []
        for series_id in MACRO_INDICATORS:
            data = self.get_series_latest(series_id, count=5)
            if data:
                results.append(data)

        _fred_cache[cache_key] = {"time": now, "data": results}
        return results

    def get_series_info(self, series_id: str) -> Optional[dict]:
        """Get metadata about a FRED series."""
        data = self._get("series", {"series_id": series_id})
        if not data:
            return None
        series = data.get("seriess", [{}])[0]
        return {
            "id": series.get("id"),
            "title": series.get("title"),
            "frequency": series.get("frequency"),
            "units": series.get("units"),
            "last_updated": series.get("last_updated"),
            "notes": series.get("notes", "")[:300],
        }
