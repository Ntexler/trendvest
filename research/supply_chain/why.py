"""Why did the price move?
(News window: the day before and the day of the move. Later articles cannot explain it.)
 The biggest moves of the last two years, each with what we can document about that day.

For each company: daily return minus its home index (the "extra" move), the 8 largest days, and for each day:
  * a chain event from our event list on that day (and whether the company is actually linked to it)
  * news headlines published from the day before to the day after (Google News search by date), with links
  * a kind, read from the headlines' words: report, analyst, deal, regulation, other news
Days with nothing found are kept and marked unknown. Nothing is invented.

    MARKET=chips python -m research.supply_chain.why            # news for the companies in stories/targets.json
    MARKET=chips python -m research.supply_chain.why --all      # news for every company (slow: ~1 s per request)
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.parse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from . import graph as G
from . import markets as MK
from .run import all_prices

TOP, YEARS, MIN_ABN = 8, 2, 4.0         # moves per company, look-back, smallest extra move worth explaining (%)
UA = {"User-Agent": "Mozilla/5.0 (research script)"}
KINDS = [  # first match wins; words in English headlines
    ("report", r"earnings|results|quarter|guidance|outlook|forecast|revenue|profit|sales (?:rose|fell|jump|drop)|beats?|miss(?:es|ed)?\b"),
    ("analyst", r"upgrade|downgrade|price target|rating|analyst|initiat"),
    ("deal", r"acqui|merger|buyout|takeover|deal|stake|partnership|contract|order"),
    ("regulation", r"ban|tariff|export|sanction|probe|lawsuit|antitrust|regulat|investigation|fine"),
]
CACHE = Path(__file__).parent / "cache" / "news"
CACHE.mkdir(parents=True, exist_ok=True)


def big_moves(prices: pd.DataFrame, ticker: str) -> list[dict]:
    s, b = prices[ticker].dropna(), prices[MK.benchmark(ticker)].dropna()
    r = s.pct_change() * 100
    rb = b.pct_change().reindex(r.index).fillna(0) * 100
    start = pd.Timestamp(date.today() - timedelta(days=365 * YEARS))
    abn = (r - rb).loc[start:].dropna()
    if abn.empty:
        return []
    sd = abn.std()
    pick = abn[abn.abs() >= max(MIN_ABN, 2.5 * sd)].abs().sort_values(ascending=False).head(TOP).index
    return [{"date": str(d.date()), "ret": round(float(r[d]), 1), "index": round(float(rb[d]), 1), "extra": round(float(abn[d]), 1)}
            for d in sorted(pick)]


def news(query: str, day: str) -> list[dict]:
    d = date.fromisoformat(day)
    key = CACHE / (re.sub(r"\W+", "_", query)[:60] + f"_{day}.json")
    if key.exists():
        return json.loads(key.read_text())
    q = f'"{query}" after:{d - timedelta(days=2)} before:{d + timedelta(days=1)}'   # published the day before or the day itself
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    out = []
    for attempt in range(3):
        try:
            x = requests.get(url, headers=UA, timeout=20).text
            for it in re.findall(r"<item>(.*?)</item>", x, re.S)[:8]:
                t = html.unescape(re.search(r"<title>(.*?)</title>", it, re.S).group(1))
                src = re.search(r"<source[^>]*>(.*?)</source>", it, re.S)
                pub = re.search(r"<pubDate>(.*?)</pubDate>", it)
                link = re.search(r"<link>(.*?)</link>", it, re.S)
                src = html.unescape(src.group(1)) if src else ""
                if src and t.endswith(" - " + src):
                    t = t[: -len(src) - 3]
                out.append({"t": t, "src": src, "d": pd.Timestamp(pub.group(1)).strftime("%Y-%m-%d") if pub else day,
                            "u": link.group(1).strip() if link else ""})
            break
        except (requests.RequestException, AttributeError):
            time.sleep(3 * (attempt + 1))
    key.write_text(json.dumps(out, ensure_ascii=False))
    time.sleep(1.0)
    return out


def kind(headlines: list[dict]) -> str | None:
    text = " ".join(h["t"] for h in headlines).lower()
    counts = {k: len(re.findall(p, text)) for k, p in KINDS}
    best = max(counts, key=counts.get)
    return best if counts[best] else ("news" if headlines else None)


def main() -> None:
    companies = G.load_companies()
    chain = companies[companies["tier"] != "control"]
    prices = all_prices(companies)
    events = G.events()
    edges = G.load_edges()
    targets = {c["ticker"] for g in json.loads((G.DATA.parent / "stories" / "targets.json").read_text()).values() for c in g}
    every = "--all" in sys.argv
    ep = G.DATA / "earnings.json"
    earn = {k: [pd.Timestamp(x).tz_convert("UTC").tz_localize(None).normalize() for x in v]
            for k, v in (json.loads(ep.read_text()).items() if ep.exists() else [])}
    out, n_news = {}, 0
    for cid, c in chain.iterrows():
        if c["ticker"] not in prices:
            continue
        moves = big_moves(prices, c["ticker"])
        neighbours = set(edges[edges.supplier == cid].customer) | set(edges[edges.customer == cid].supplier)
        for m in moves:
            d = pd.Timestamp(m["date"])
            for eid, e in events.iterrows():
                if 0 <= (d - e["ts_utc"].tz_convert(None).normalize()).days <= 2:
                    hit = set(str(e["hit"]).split(";"))
                    m["event"] = {"id": eid, "name": e["name"], "linked": cid in hit or bool(hit & neighbours)}
            if every or c["ticker"] in targets:
                h = news(re.sub(r"\s*\(.*?\)", "", c["name"]), m["date"])
                n_news += 1
                h = [x for x in h if x["d"] <= m["date"]]   # an article dated after the move cannot explain it
                if h:
                    m["news"] = h[:5]
            if any(0 <= (d.normalize() - e).days <= 1 for e in earn.get(cid, [])):
                m["earnings"] = True           # report published that day or the evening before (official calendar)
            m["kind"] = ("report" if m.get("earnings") else None) or ("event" if m.get("event", {}).get("linked") else None) \
                or kind(m.get("news", []))
            m["searched"] = "news" in m or every or c["ticker"] in targets
        out[cid] = moves
    G.RESULTS.mkdir(parents=True, exist_ok=True)
    (G.RESULTS / "why.json").write_text(json.dumps(out, ensure_ascii=False))
    allm = [m for v in out.values() for m in v]
    known = sum(1 for m in allm if m.get("kind"))
    print(f"{G.MARKET}: {len(allm)} big moves in {len(out)} companies; {n_news} news searches; "
          f"{known} with a documented reason, {len(allm) - known} unknown")


if __name__ == "__main__":
    main()
