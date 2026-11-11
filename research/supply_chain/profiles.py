"""Company card data for the map: basic analytics, institutional holders and officers/directors.

Free source: Yahoo Finance (via yfinance). Holders come from 13F-style filings (top 10),
insiders from SEC Forms 3/4 where the company files in the US. Cached to data/profiles.json.

    python -m research.supply_chain.profiles
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from . import graph as G

OUT = Path(__file__).parent / "data" / "profiles.json"
INFO_KEYS = ["marketCap", "trailingPE", "forwardPE", "profitMargins", "revenueGrowth", "beta",
             "fiftyTwoWeekChange", "currency", "fullTimeEmployees", "heldPercentInstitutions",
             "heldPercentInsiders", "recommendationKey"]


def fetch(ticker: str) -> dict:
    import yfinance as yf
    t = yf.Ticker(ticker)
    out: dict = {"info": {}, "holders": [], "officers": [], "insiders": []}
    try:
        info = t.info
        out["info"] = {k: info.get(k) for k in INFO_KEYS if info.get(k) is not None}
        out["officers"] = [{"name": " ".join(str(o.get("name", "")).split()), "title": o.get("title")}
                           for o in info.get("companyOfficers", [])[:8]]
    except Exception:
        pass
    try:
        h = t.institutional_holders
        if h is not None and len(h):
            out["holders"] = [{"name": r["Holder"], "pct": round(float(r["pctHeld"]) * 100, 2)}
                              for _, r in h.head(10).iterrows()]
    except Exception:
        pass
    try:
        r = t.insider_roster_holders
        if r is not None and len(r):
            out["insiders"] = [{"name": str(x["Name"]).title(), "title": x["Position"]}
                               for _, x in r.head(12).iterrows()]
    except Exception:
        pass
    return out


def main() -> None:
    companies = G.load_companies()
    companies = companies[companies["tier"] != "control"]
    data = json.loads(OUT.read_text()) if OUT.exists() else {}
    for cid, c in companies.iterrows():
        if cid in data:
            continue
        data[cid] = fetch(c["ticker"])
        print(cid, len(data[cid]["holders"]), "holders,", len(data[cid]["officers"]), "officers,",
              len(data[cid]["insiders"]), "insiders", flush=True)
        OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False))
        time.sleep(0.4)


if __name__ == "__main__":
    main()
