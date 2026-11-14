"""Candidates worth a closer look: cheap for their stage, growing, with demand arriving, and not broken.

A company is a candidate only if all four checks pass. Each check shows its number, so the reader can
disagree. This is a screen, not a forecast: nothing we tested predicts returns. Every candidate is
written to the ledger on the day it appears so it can be scored later against its own stage.

  cheap        price-to-earnings and price-to-sales both ranked inside the stage; average rank in the cheapest 40%
  growing      revenue up more than 5% on a year ago, and operating margin above zero
  demand       its customers in the map grow revenue by more than 5% on average (needs at least one customer)
  not_broken   positive net income, net debt below 3 years of operating profit (or more cash than debt),
               and the share price has not lost more than 40% in a year

    MARKET=chips python -m research.supply_chain.screen
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import graph as G

CHEAP_RANK, GROWTH, CRASH, MAX_DEBT = 0.40, 0.05, -40.0, 3.0


def run() -> dict:
    c = G.load_companies()
    chain = c[c["tier"] != "control"]
    info = {k: v["info"] for k, v in json.loads((G.DATA / "profiles.json").read_text()).items()}
    pulses = json.loads(p.read_text()) if (p := G.DATA / "pulses.json").exists() else {"monthly": {}}
    px = json.loads((G.DATA / "prices_weekly.json").read_text())["series"]
    edges = G.load_edges()
    df = pd.DataFrame({cid: {"pe": i.get("trailingPE") if (i.get("trailingPE") or 0) > 0 else np.nan,
                             "ps": (i["marketCapUSD"] / i["revenueUSD"]) if i.get("marketCapUSD") and i.get("revenueUSD") else np.nan,
                             "growth": pulses["monthly"][cid]["yoy_pct"] / 100 if cid in pulses["monthly"] else i.get("revenueGrowth"),
                             "margin": i.get("operatingMargins"), "net": i.get("netIncomeUSD"),
                             "nd": i.get("netDebtUSD"), "nd_e": i.get("netDebtToEbitda")}
                       for cid, i in info.items() if cid in chain.index}).T.astype(float)
    df["tier"] = chain["tier"]
    df["rank"] = df.groupby("tier")[["pe", "ps"]].rank(pct=True).mean(axis=1)
    out = {}
    for cid, r in df.iterrows():
        v = [x for x in px.get(cid, []) if x is not None]
        y1 = (v[-1] / v[max(0, len(v) - 53)] - 1) * 100 if len(v) > 10 else np.nan
        cust = [x for x in edges.loc[edges.supplier == cid, "customer"] if x in df.index and pd.notna(df.loc[x, "growth"])]
        cg = float(np.mean([df.loc[x, "growth"] for x in cust])) if cust else np.nan
        debt_ok = None if pd.isna(r["nd"]) else bool(r["nd"] <= 0 or (pd.notna(r["nd_e"]) and r["nd_e"] < MAX_DEBT))
        checks = {"cheap": bool(r["rank"] <= CHEAP_RANK) if pd.notna(r["rank"]) else None,
                  "growing": bool(r["growth"] > GROWTH and r["margin"] > 0) if pd.notna(r["growth"]) and pd.notna(r["margin"]) else None,
                  "demand": bool(cg > GROWTH) if pd.notna(cg) else None,
                  "not_broken": bool(r["net"] > 0 and y1 > CRASH and debt_ok) if pd.notna(r["net"]) and pd.notna(y1) and debt_ok is not None else None}
        num = lambda x, k=1: None if pd.isna(x) else round(float(x) * k, 1)      # noqa: E731
        out[cid] = {"checks": checks, "passed": sum(1 for x in checks.values() if x), "candidate": all(checks.values()),
                    "pe": num(r["pe"]), "ps": num(r["ps"]), "rank_in_stage": num(r["rank"], 100), "growth_pct": num(r["growth"], 100),
                    "margin_pct": num(r["margin"], 100), "customers_growth_pct": num(cg, 100), "customers": cust, "price_1y_pct": num(y1),
                    "net_debt_usd": None if pd.isna(r["nd"]) else float(r["nd"]), "net_debt_to_ebitda": num(r["nd_e"])}
    G.RESULTS.mkdir(parents=True, exist_ok=True)
    (G.RESULTS / "screen.json").write_text(json.dumps(out, indent=1))
    return out


def log_candidates(res: dict) -> int:
    """Append today's candidates to the ledger, once per company per calendar month."""
    from .ledger import DIR, _append, _read
    path = DIR / "candidates.jsonl"
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    have = {(r["company"], r["created_utc"][:7]) for r in _read(path)}
    px = json.loads((G.DATA / "prices_weekly.json").read_text())
    n = 0
    for cid, r in res.items():
        if r["candidate"] and (cid, month) not in have:
            v = [x for x in px["series"].get(cid, []) if x is not None]
            _append(path, {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "market": G.MARKET, "company": cid,
                           "price": v[-1] if v else None, "price_date": px["dates"][-1],
                           "numbers": {k: r[k] for k in ("pe", "ps", "rank_in_stage", "growth_pct", "margin_pct", "customers_growth_pct", "price_1y_pct")},
                           "to_score": "return after 3, 6 and 12 months against the median company of its stage"})
            n += 1
    return n


if __name__ == "__main__":
    res = run()
    cands = [k for k, v in res.items() if v["candidate"]]
    print(f"{G.MARKET}: {len(res)} companies; passed 4 of 4: {len(cands)}; 3 of 4: {sum(1 for v in res.values() if v['passed'] == 3)}")
    for k in cands:
        r = res[k]
        print(f"  {k:12s} P/E {r['pe']}, P/S {r['ps']}, rank in stage {r['rank_in_stage']}%, growth {r['growth_pct']}%, customers' growth {r['customers_growth_pct']}%, 1y price {r['price_1y_pct']}%")
    print("near misses (3 of 4):", {k: [c for c, ok in v["checks"].items() if not ok] for k, v in res.items() if v["passed"] == 3})
    print("logged to ledger:", log_candidates(res))
