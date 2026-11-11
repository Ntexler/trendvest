"""Compare all researched markets on the same few questions, and find the companies that sit in several.

    python -m research.supply_chain.compare      -> map/site/data/compare.json
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).parent


def one(market: str) -> dict | None:
    d, r = BASE / "data" / market, BASE / "results" / market
    need = ["companies.csv", "market.json", "stages.json", "profiles.json", "prices_weekly.json"]
    if not all((d / f).exists() for f in need):
        return None
    c = pd.read_csv(d / "companies.csv", comment="#").set_index("id")
    chain = c[c["tier"] != "control"]
    m = json.loads((d / "market.json").read_text())
    st = json.loads((d / "stages.json").read_text())
    info = {k: v["info"] for k, v in json.loads((d / "profiles.json").read_text()).items() if k in chain.index}
    px = json.loads((d / "prices_weekly.json").read_text())
    col = lambda k: pd.Series({cid: i.get(k) for cid, i in info.items()}, dtype=float).dropna()     # noqa: E731
    rev, net = col("revenueUSD"), col("netIncomeUSD")
    wk = np.log(pd.DataFrame({k: v for k, v in px["series"].items() if k != "_MARKET"}, dtype=float)).diff()
    basket = wk.mean(axis=1).dropna()
    curve = basket.cumsum()
    y1 = pd.Series({k: (pd.Series(v, dtype=float).dropna().iloc[-1] / pd.Series(v, dtype=float).dropna().iloc[-53] - 1) * 100
                    for k, v in px["series"].items() if k != "_MARKET" and pd.Series(v, dtype=float).notna().sum() > 60})
    idx = pd.Series(px["series"]["_MARKET"], dtype=float).dropna()
    countries = chain["country"].value_counts()
    edges = pd.read_csv(d / "edges.csv", comment="#")
    base = {}
    if (r / "event_role_weighted.csv").exists():
        er = pd.read_csv(r / "event_role_weighted.csv")
        for role in ("hit", "down1"):
            v = er.loc[er.role == role, "pct3"].dropna()
            if len(v):
                base[role] = {"n": int(len(v)), "mean": round(float(v.mean()), 1), "fell": int((v < 0).sum())}
    screen = json.loads((r / "screen.json").read_text()) if (r / "screen.json").exists() else {}
    ch = m.get("changes", [])
    return {"id": market, "name": m["name"], "intro": m["intro"], "stages": [st["stages"][t]["title"] for t in m["tiers"]],
            "companies": int(len(chain)), "links": int(len(edges)), "countries": int(countries.size),
            "top_country": [str(countries.index[0]), int(countries.iloc[0])],
            "revenue": float(rev.sum()), "net": float(net.sum()), "net_margin": round(float(net.sum() / rev.sum() * 100), 1),
            "growth_med": round(float(col("revenueGrowth").median() * 100), 1), "gross_med": round(float(col("grossMargins").median() * 100), 1),
            "pe_med": round(float(col("trailingPE")[lambda s: s > 0].median()), 1),
            "price_1y_med": round(float(y1.median()), 1), "index_name": m["index_name"],
            "index_1y": round(float((idx.iloc[-1] / idx.iloc[-53] - 1) * 100), 1) if len(idx) > 60 else None,
            "vol_1y": round(float(basket.iloc[-52:].std() * np.sqrt(52) * 100), 1),
            "max_drawdown": round(float((curve - curve.cummax()).min() * 100), 1),
            "lifecycle_total": m.get("lifecycle_total"), "events": base,
            "open_blocks": sum(1 for x in ch if x[1] == "blocks"), "open_delays": sum(1 for x in ch if x[1] == "delays"), "open_changes": len(ch),
            "choke": sum(len(s["choke"]) for s in st["stages"].values()),
            "candidates": [k for k, v in screen.items() if v["candidate"]],
            "tickers": {cid: t for cid, t in chain["ticker"].items()}, "names": chain["name"].to_dict()}


def main() -> None:
    order = ["chips", "ai", "robotics", "energy", "minerals", "medical"]
    markets = {m: x for m in order if (x := one(m))}
    seen = defaultdict(list)
    for mk, x in markets.items():
        for cid, t in x["tickers"].items():
            seen[t.split(".")[0] if t.endswith((".TA",)) else t].append((mk, cid, x["names"][cid]))
    bridges = sorted(([v[0][2], [a for a, _, _ in v], {a: b for a, b, _ in v}] for v in seen.values() if len({a for a, _, _ in v}) > 1),
                     key=lambda b: (-len(b[1]), b[0]))
    for x in markets.values():
        x.pop("tickers"), x.pop("names")
    out = {"order": list(markets), "markets": markets, "bridges": bridges}
    (BASE / "map" / "site" / "data" / "compare.json").write_text(json.dumps(out, ensure_ascii=False))
    for mk, x in markets.items():
        print(f"{mk:9s} {x['companies']} cos, revenue ${x['revenue'] / 1e12:.2f}T, net margin {x['net_margin']}%, growth {x['growth_med']}%, "
              f"vol {x['vol_1y']}%, 1y {x['price_1y_med']}%, candidates {len(x['candidates'])}")
    print("companies in more than one market:", len(bridges), [b[0] for b in bridges[:12]])


if __name__ == "__main__":
    main()
