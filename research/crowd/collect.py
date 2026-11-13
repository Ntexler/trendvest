"""Collect free crowd data (resumable):
  wsb      daily top-50 tickers on Reddit r/wallstreetbets with comment counts and sentiment (tradestie.com, from ~2021-04)
  poly     Polymarket "will X beat its EPS estimate" markets: price history before the report and the result

    python -m research.crowd.collect wsb|poly
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

D = Path(__file__).parent / "data"
D.mkdir(exist_ok=True)
S = requests.Session()
S.headers["User-Agent"] = "research-script/0.1"


def get(url, **kw):
    for a in range(5):
        try:
            r = S.get(url, timeout=30, **kw)
            if r.status_code == 200:
                return r.json()
            time.sleep(5 * (a + 1))
        except Exception:  # noqa: BLE001
            time.sleep(5 * (a + 1))
    return None


def wsb():
    out = D / "wsb_daily.csv"
    have = set(pd.read_csv(out).date) if out.exists() else set()
    for d in pd.bdate_range("2021-04-01", pd.Timestamp.today() - pd.Timedelta(days=1)):
        ds = d.strftime("%Y-%m-%d")
        if ds in have:
            continue
        j = get("https://tradestie.com/api/v1/apps/reddit", params={"date": ds})
        rows = [{"date": ds, "rank": i + 1, **x} for i, x in enumerate(j or [])] or [{"date": ds}]
        pd.DataFrame(rows).to_csv(out, mode="a", header=not out.exists(), index=False)
        time.sleep(1.5)


def poly():
    ev, off = [], 0
    while True:
        j = get("https://gamma-api.polymarket.com/events", params={"tag_slug": "earnings", "closed": "true", "limit": 100, "offset": off})
        if not j:
            break
        ev += j
        off += 100
        time.sleep(0.5)
    rows = []
    for e in ev:
        for m in e.get("markets", []):
            try:
                tok = json.loads(m["clobTokenIds"])[0]
                res = json.loads(m["outcomePrices"])
            except Exception:  # noqa: BLE001
                continue
            h = get("https://clob.polymarket.com/prices-history", params={"market": tok, "interval": "max", "fidelity": 60}) or {}
            rows.append({"question": m.get("question"), "slug": m.get("slug"), "end": m.get("endDate"), "closed": m.get("closedTime"),
                         "yes_won": res[0] == "1", "volume": m.get("volume"), "history": h.get("history", [])})
            time.sleep(0.3)
    (D / "poly_earnings.json").write_text(json.dumps(rows))
    print(len(ev), "events", len(rows), "markets")


if __name__ == "__main__":
    if sys.argv[1] != "poly_fill":
        {"wsb": wsb, "poly": poly}[sys.argv[1]]()


def poly_fill():
    """Older markets return no history with interval=max: ask for the 14 days before the end explicitly."""
    p = D / "poly_earnings.json"
    M = json.loads(p.read_text())
    for m in M:
        if m["history"] or not m["end"] or not m["slug"]:
            continue
        j = get("https://gamma-api.polymarket.com/markets", params={"slug": m["slug"], "closed": "true"})
        if not j:
            continue
        tok = json.loads(j[0]["clobTokenIds"])[0]
        end = int(pd.Timestamp(m["end"]).timestamp())
        h = get("https://clob.polymarket.com/prices-history", params={"market": tok, "startTs": end - 14 * 86400, "endTs": end, "fidelity": 60}) or {}
        m["history"] = h.get("history", [])
        time.sleep(0.3)
    p.write_text(json.dumps(M))
    print(sum(bool(m["history"]) for m in M), "of", len(M), "with history")


if __name__ == "__main__" and sys.argv[1] == "poly_fill":
    poly_fill()
