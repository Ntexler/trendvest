"""Historical data loaders for the News Impact research.

Sources
-------
* GDELT DOC 2.0 API (news archive, 2017-today): daily article volume and
  average tone for a free-text query. Rate limit: ~1 request / 5 seconds.
* Yahoo Finance via yfinance: daily adjusted prices for US and TASE tickers.

Everything is cached to ``cache/`` as CSV so re-runs are free.
"""

from __future__ import annotations

import time
import urllib.parse
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_MIN_INTERVAL = 10.0  # seconds between calls (API asks for >= 5; egress IP may be shared)
_last_call = 0.0


def _gdelt_get(params: dict, retries: int = 5) -> dict | None:
    """GET with rate limiting and exponential backoff. Returns parsed JSON or None."""
    global _last_call
    for attempt in range(retries):
        wait = GDELT_MIN_INTERVAL - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()
        try:
            r = requests.get(
                GDELT_URL, params=params, timeout=120,
                headers={"User-Agent": "Mozilla/5.0 (research script)"},
            )
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                return r.json()
        except (requests.RequestException, ValueError):
            pass
        time.sleep(min(20 * (attempt + 1), 60))
    return None


def _chunks(start: date, end: date, days: int = 90):
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=days), end)
        yield cur, nxt
        cur = nxt


def _gdelt_series(query: str, mode: str, start: date, end: date) -> pd.DataFrame:
    rows = []

    def fetch(a: date, b: date) -> None:
        data = _gdelt_get({
            "query": query,
            "mode": mode,
            "format": "json",
            "startdatetime": a.strftime("%Y%m%d000000"),
            "enddatetime": b.strftime("%Y%m%d000000"),
        })
        if not data or not data.get("timeline"):
            if (b - a).days > 31:  # long ranges sometimes time out: split and retry
                mid = a + (b - a) / 2
                fetch(a, mid)
                fetch(mid, b)
            else:
                print(f"  ! GDELT gap {mode} {a}..{b}", flush=True)
            return
        for series in data["timeline"]:
            name = series.get("series", mode)
            for pt in series["data"]:
                rows.append({
                    "date": pd.to_datetime(pt["date"][:8]),
                    "series": name,
                    "value": pt["value"],
                    "norm": pt.get("norm"),
                })

    for a, b in _chunks(start, end):
        fetch(a, b)
    return pd.DataFrame(rows)


def load_news(query: str, start: date, end: date, refresh: bool = False) -> pd.DataFrame:
    """Daily news attention for ``query``.

    Columns: ``articles`` (raw count), ``total`` (all articles GDELT saw that
    day, for normalisation), ``share`` (articles per 10k), ``tone`` (avg tone).
    """
    key = urllib.parse.quote_plus(query)[:80]
    path = CACHE_DIR / f"news_{key}_{start}_{end}.csv"
    if path.exists() and not refresh:
        return pd.read_csv(path, parse_dates=["date"], index_col="date")

    vol = _gdelt_series(query, "timelinevolraw", start, end)
    tone = _gdelt_series(query, "timelinetone", start, end)

    out = pd.DataFrame()
    if not vol.empty:
        v = vol.drop_duplicates("date").set_index("date")
        out["articles"] = v["value"].astype(float)
        out["total"] = v["norm"].astype(float)
        out["share"] = out["articles"] / out["total"].replace(0, pd.NA) * 1e4
    if not tone.empty:
        t = tone.drop_duplicates("date").set_index("date")["value"].astype(float)
        out = out.join(t.rename("tone"), how="outer")
    out = out.sort_index()
    out.index.name = "date"
    out.to_csv(path)
    return out


def load_prices(tickers: list[str], start: date, end: date, refresh: bool = False) -> pd.DataFrame:
    """Daily adjusted close + volume. Returns a wide frame with a (field, ticker) MultiIndex."""
    import yfinance as yf

    key = "_".join(t.replace("^", "") for t in sorted(tickers))[:120]
    path = CACHE_DIR / f"prices_{key}_{start}_{end}.pkl"
    if path.exists() and not refresh:
        return pd.read_pickle(path)
    df = yf.download(
        tickers, start=str(start), end=str(end), progress=False, auto_adjust=True
    )[["Close", "Volume"]]
    df.to_pickle(path)
    return df
