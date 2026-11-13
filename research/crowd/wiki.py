"""Wikipedia daily page views of every company in our maps (2016 on) - a free stand-in for Google searches
(Moat et al. 2013 used Wikipedia views the same way). Title found by the English Wikipedia search for the company name.

    python -m research.crowd.wiki      -> data/wiki_views.csv (date, ticker, views), data/wiki_titles.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import requests

D = Path(__file__).parent / "data"
SC = Path(__file__).parents[1] / "supply_chain" / "data"
S = requests.Session()
S.headers["User-Agent"] = "research-script/0.1 (contact: none)"


def get(url, **p):
    for a in range(5):
        try:
            r = S.get(url, params=p, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
        except Exception:  # noqa: BLE001
            pass
        time.sleep(5 * (a + 1))
    return None


def main() -> None:
    comp = {}
    for d in sorted(SC.iterdir()):
        if (d / "companies.csv").exists():
            for r in pd.read_csv(d / "companies.csv", comment="#").itertuples():
                if r.tier != "control":
                    comp.setdefault(r.ticker, r.name)
    tf = D / "wiki_titles.json"
    titles = json.loads(tf.read_text()) if tf.exists() else {}
    for t, name in comp.items():
        if t in titles:
            continue
        j = get("https://en.wikipedia.org/w/api.php", action="query", list="search", srsearch=f"{name} company", srlimit=1, format="json")
        hit = (j or {}).get("query", {}).get("search", [])
        titles[t] = hit[0]["title"] if hit else None
        time.sleep(0.3)
    tf.write_text(json.dumps(titles, ensure_ascii=False, indent=0))
    out = D / "wiki_views.csv"
    done = set(pd.read_csv(out).ticker) if out.exists() else set()
    for t, title in titles.items():
        if not title or t in done:
            continue
        j = get(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/"
                f"{requests.utils.quote(title.replace(' ', '_'), safe='')}/daily/20160101/{pd.Timestamp.today():%Y%m%d}")
        items = (j or {}).get("items", [])
        rows = [{"date": i["timestamp"][:8], "ticker": t, "views": i["views"]} for i in items] or [{"date": None, "ticker": t, "views": None}]
        pd.DataFrame(rows).to_csv(out, mode="a", header=not out.exists(), index=False)
        time.sleep(0.5)
    print(sum(bool(v) for v in titles.values()), "titles")


if __name__ == "__main__":
    main()
