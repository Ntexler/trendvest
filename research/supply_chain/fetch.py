"""Fetch everything that comes from free sources for one market (set MARKET=<folder>):

    MARKET=energy python -m research.supply_chain.fetch          # profiles, weekly prices, news
    MARKET=energy python -m research.supply_chain.fetch news     # one step only

profiles   company card data (Yahoo Finance), with revenue, profit and market value in US dollars
prices     weekly closes for the last five years, plus the market's comparison index
news       latest headlines per company: title, publisher's summary, date, source, link
"""

from __future__ import annotations

import json
import sys
import time

import pandas as pd

from . import graph as G
from .profiles import fetch as fetch_profile
from .run import all_prices

EXTRA = ["totalRevenue", "netIncomeToCommon", "grossMargins", "operatingMargins", "financialCurrency", "city", "country",
         "marketCap", "currency", "fullTimeEmployees"]


def chain_companies() -> pd.DataFrame:
    c = G.load_companies()
    return c[c["tier"] != "control"]


def profiles() -> None:
    import yfinance as yf
    path = G.DATA / "profiles.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    fx: dict[str, float | None] = {}

    def rate(cur):
        if cur in (None, "USD"):
            return 1.0
        minor = {"ILA": "ILS", "GBp": "GBP", "GBX": "GBP", "ZAc": "ZAR"}      # prices quoted in hundredths
        if cur in minor:
            r = rate(minor[cur])
            return r / 100 if r else None
        if cur not in fx:
            try:
                fx[cur] = float(yf.Ticker(f"{cur}USD=X").fast_info["lastPrice"])
            except Exception:  # noqa: BLE001
                fx[cur] = None
        return fx[cur]
    for cid, c in chain_companies().iterrows():
        if cid in data and "revenueUSD" in data[cid]["info"] and "marketCapUSD" in data[cid]["info"]:
            continue
        p = fetch_profile(c["ticker"])
        try:
            info = yf.Ticker(c["ticker"]).info
            p["info"].update({k: info[k] for k in EXTRA if info.get(k) is not None})
        except Exception:  # noqa: BLE001
            pass
        x = p["info"]
        r1, r2 = rate(x.get("financialCurrency")), rate(x.get("currency"))
        if r1 and x.get("totalRevenue"):
            x["revenueUSD"] = x["totalRevenue"] * r1
        if r1 and x.get("netIncomeToCommon") is not None:
            x["netIncomeUSD"] = x["netIncomeToCommon"] * r1
        if r2 and x.get("marketCap"):
            x["marketCapUSD"] = x["marketCap"] * r2
        data[cid] = p
        path.write_text(json.dumps(data, indent=1, ensure_ascii=False))
        time.sleep(0.4)
    print("profiles:", len(data))


def prices() -> None:
    import yfinance as yf
    companies = G.load_companies()
    px = all_prices(companies)
    wk = px.resample("W-FRI").last().iloc[-263:]
    out = {"dates": [str(d.date()) for d in wk.index], "series": {}}
    for cid, c in chain_companies().iterrows():
        out["series"][cid] = [None if pd.isna(v) else round(float(v), 2) for v in wk[c["ticker"]]]
    idx = yf.download(G.market()["index_ticker"], start=str(wk.index[0].date() - pd.Timedelta(days=10)), progress=False, auto_adjust=True)["Close"].squeeze()
    s = idx.resample("W-FRI").last().reindex(wk.index)
    out["series"]["_MARKET"] = [None if pd.isna(v) else round(float(v), 2) for v in s]
    (G.DATA / "prices_weekly.json").write_text(json.dumps(out))
    print("weekly prices:", len(out["dates"]), "weeks,", len(out["series"]) - 1, "companies")


def news() -> None:
    import yfinance as yf
    out = {}
    for cid, c in chain_companies().iterrows():
        items = []
        try:
            for n in (yf.Ticker(c["ticker"]).news or [])[:8]:
                x = n.get("content", n)
                url = (x.get("canonicalUrl") or {}).get("url") or (x.get("clickThroughUrl") or {}).get("url")
                if x.get("title") and url:
                    items.append({"t": x["title"], "s": (x.get("summary") or "")[:400], "d": (x.get("pubDate") or "")[:10],
                                  "p": (x.get("provider") or {}).get("displayName", ""), "u": url})
        except Exception:  # noqa: BLE001
            pass
        out[cid] = items
        time.sleep(0.25)
    (G.DATA / "news.json").write_text(json.dumps(out, ensure_ascii=False))
    print("news:", sum(len(v) for v in out.values()), "items")


if __name__ == "__main__":
    steps = {"profiles": profiles, "prices": prices, "news": news}
    for name in (sys.argv[1:] or list(steps)):
        steps[name]()
