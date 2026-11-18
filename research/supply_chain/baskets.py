"""Does a basket balanced with the supply-chain map get hurt less than a basket of popular names?

Baskets are built by fixed rules from the map and company size only (never from event outcomes):
  popular   the 8 largest by market value among chip designers, makers and equipment firms
  one_each  the largest company by revenue in each of the 7 stages
  balanced  like one_each plus one, but at most 2 per country and no two holdings that
            depend critically on the same supplier
  all       every company in the chain (the yardstick)
Each is equal-weighted. Two questions:
  1. Around the 10 catalogued disruptions: how much did each basket lose (raw return, local
     currency) after 3 and 10 sessions, and at the worst point inside 10 sessions?
  2. Over 2016-2026: weekly volatility, deepest fall from a peak, worst week.
1,000 random 8-stock baskets give the spread to compare against.

    python -m research.supply_chain.baskets
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import graph as G
from . import markets as MK
from .run import all_prices

HERE = Path(__file__).parent


def build(chain: pd.DataFrame, info: dict, edges: pd.DataFrame) -> dict[str, list[str]]:
    cap = lambda c: info[c]["info"].get("marketCapUSD") or 0          # noqa: E731
    rev = lambda c: info[c]["info"].get("revenueUSD") or 0            # noqa: E731
    crit = edges[edges["critical"].astype(str).isin(["1", "1.0"])].groupby("customer")["supplier"].apply(set).to_dict()
    popular = sorted(chain.index, key=cap, reverse=True)[:8] if G.MARKET != "chips" else \
        sorted([c for c in chain.index if chain.loc[c, "tier"] in ("design", "manufacturing", "equipment")], key=cap, reverse=True)[:8]
    tiers = G.market()["tiers"]
    by_tier = {t: sorted(chain.index[chain["tier"] == t], key=rev, reverse=True) for t in tiers}
    one_each = [by_tier[t][0] for t in tiers]
    balanced: list[str] = []

    def ok(c):
        country = sum(chain.loc[x, "country"] == chain.loc[c, "country"] for x in balanced) < 2
        shared = any(crit.get(c, set()) & crit.get(x, set()) for x in balanced)
        direct = any(c in crit.get(x, set()) or x in crit.get(c, set()) for x in balanced)
        return country and not shared and not direct
    for t in tiers + [max(tiers, key=lambda t: len(by_tier[t]))]:
        pick = next((c for c in by_tier[t] if c not in balanced and ok(c)), None)
        if pick:
            balanced.append(pick)
    return {"popular": popular, "one_each": one_each, "balanced": balanced, "all": list(chain.index)}


def event_returns(prices: pd.DataFrame, chain: pd.DataFrame, events: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Per event: company x [r3, r10, worst] raw log returns from the last close before the event."""
    out = {}
    for ev_id, e in events.iterrows():
        rows = {}
        for cid, c in chain.iterrows():
            s = prices[c["ticker"]].dropna()
            i = MK.day0_position(c["ticker"], s.index, e["ts_utc"])
            if i is None or i < 1 or i + 10 >= len(s):
                continue
            path = np.log(s.iloc[i:i + 11].to_numpy() / s.iloc[i - 1])
            rows[cid] = {"r3": path[3], "r10": path[10], "worst": path.min()}
        if rows:                       # an event too recent to have ten sessions after it is skipped
            out[ev_id] = pd.DataFrame(rows).T * 100
    return out


def main() -> None:
    companies = G.load_companies()
    chain = companies[companies["tier"] != "control"]
    info = json.loads((G.DATA / "profiles.json").read_text())
    edges = G.load_edges()
    prices = all_prices(companies)
    baskets = build(chain, info, edges)
    events = G.events()
    events = events[events["quality"] != "avoid"]
    er = event_returns(prices, chain, events)
    wk = np.log(prices[list(chain["ticker"])].resample("W-FRI").last().loc["2016-01-01":]).diff()
    wk.columns = chain.index
    rng = np.random.default_rng(5)
    randoms = [list(rng.choice(chain.index, 8, replace=False)) for _ in range(1000)]

    def stats(members):
        ev = pd.DataFrame({k: v.reindex(members).mean() for k, v in er.items()}).T      # event x metric
        r = wk[members].mean(axis=1).dropna()
        curve = r.cumsum()
        corr = wk[members].corr().to_numpy()
        return {"event_r3": ev["r3"].mean(), "event_r10": ev["r10"].mean(), "event_worst": ev["worst"].mean(),
                "worst_event_r3": ev["r3"].min(), "events_down_r3": int((ev["r3"] < 0).sum()),
                "vol_year": r.std() * np.sqrt(52) * 100, "max_drawdown": (curve - curve.cummax()).min() * 100,
                "worst_week": r.min() * 100, "avg_corr": corr[np.triu_indices_from(corr, 1)].mean(),
                "return_year": r.mean() * 52 * 100}
    rnd = pd.DataFrame([stats(m) for m in randoms])
    rows = []
    crit = edges[edges["critical"].astype(str).isin(["1", "1.0"])]
    for name, members in baskets.items():
        s = stats(members)
        s["basket"], s["n"] = name, len(members)
        s["depends_on_TSMC"] = sum(m in set(crit.loc[crit.supplier == "TSMC", "customer"]) or m == "TSMC" for m in members)
        s["countries"] = chain.loc[members, "country"].nunique()
        for k in ("event_r3", "event_worst", "vol_year", "max_drawdown"):
            better = (rnd[k] > s[k]) if k in ("vol_year",) else (rnd[k] < s[k])
            s[f"{k}_beats_random"] = float(better.mean())      # share of random baskets that did worse
        rows.append(s)
    res = pd.DataFrame(rows).set_index("basket")
    res.round(3).to_csv(G.RESULTS / "baskets.csv")
    pd.set_option("display.width", 250, "display.max_columns", 30)
    for k, v in baskets.items():
        if k != "all":
            print(f"{k}: {', '.join(v)}")
    print(res[["n", "countries", "depends_on_TSMC", "event_r3", "event_r10", "event_worst", "worst_event_r3", "events_down_r3",
               "vol_year", "max_drawdown", "worst_week", "avg_corr", "return_year"]].round(1).to_string())
    print("\nshare of 1,000 random 8-stock baskets that did WORSE:")
    print(res[[c for c in res if c.endswith("_beats_random")]].round(2).to_string())
    print("\nrandom baskets, median:", rnd.median().round(1).to_dict())
    per = pd.DataFrame({b: pd.Series({k: v.reindex(m)["r3"].mean() for k, v in er.items()}) for b, m in baskets.items()})
    print("\n3-session return by event (%):\n", per.round(1).to_string())


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Portfolio builder: three baskets by risk level, same balancing rule, different pick inside each stage
# ---------------------------------------------------------------------------
def builder() -> dict:
    """calm = the least volatile company of each stage (last 12 months), steady = the largest by
    revenue, bold = the most volatile. All three obey the map rule: one per stage plus one,
    at most 2 per country, no two holdings that depend critically on the same supplier."""
    companies = G.load_companies()
    chain = companies[companies["tier"] != "control"]
    info = json.loads((G.DATA / "profiles.json").read_text())
    edges = G.load_edges()
    prices = all_prices(companies)
    px = prices[list(chain["ticker"])]
    px.columns = chain.index
    daily = np.log(px).diff()
    vol1y = (daily.iloc[-252:].std() * np.sqrt(252) * 100).dropna()
    chain = chain.loc[[c for c in chain.index if c in vol1y.index and px[c].notna().sum() > 800]]
    tiers = G.market()["tiers"]
    crit = edges[edges["critical"].astype(str).isin(["1", "1.0"])]
    cmap = crit.groupby("customer")["supplier"].apply(set).to_dict()
    rev = lambda c: info.get(c, {}).get("info", {}).get("revenueUSD") or 0      # noqa: E731
    keys = {"calm": lambda c: vol1y[c], "steady": lambda c: -rev(c), "bold": lambda c: -vol1y[c]}
    events = G.events()
    events = events[events["quality"] != "avoid"]
    er = event_returns(prices, chain, events)
    wk = np.log(px[chain.index].resample("W-FRI").last().loc["2016-01-01":]).diff()

    def pick(key):
        out: list[str] = []

        def ok(c):
            return sum(chain.loc[x, "country"] == chain.loc[c, "country"] for x in out) < 2 and \
                not any(cmap.get(c, set()) & cmap.get(x, set()) or c in cmap.get(x, set()) or x in cmap.get(c, set()) for x in out)
        by = {t: sorted(chain.index[chain["tier"] == t], key=key) for t in tiers}
        for t in tiers + [max(tiers, key=lambda t: len(by[t]))]:
            p = next((c for c in by[t] if c not in out and ok(c)), None)
            if p:
                out.append(p)
        return out

    def describe(members):
        r = wk[members].mean(axis=1).dropna()
        curve = r.cumsum()
        ev = {k: float(v.reindex(members)["r3"].mean()) for k, v in er.items()}
        top_sup = crit[crit.customer.isin(members)].groupby("supplier").size().sort_values(ascending=False)
        return {"members": members,
                "vol_now": round(float((daily[members].iloc[-252:].mean(axis=1).std()) * np.sqrt(252) * 100), 1),
                "vol_hist": round(float(r.std() * np.sqrt(52) * 100), 1),
                "max_drawdown": round(float((curve - curve.cummax()).min() * 100), 1),
                "return_year": round(float(r.mean() * 52 * 100), 1),
                "events_r3": {k: round(v, 1) for k, v in ev.items() if not np.isnan(v)},
                "countries": chain.loc[members, "country"].value_counts().to_dict(),
                "shared_supplier": [str(top_sup.index[0]), int(top_sup.iloc[0])] if len(top_sup) else None}
    cap = lambda c: info.get(c, {}).get("info", {}).get("marketCapUSD") or 0     # noqa: E731
    out = {k: describe(pick(f)) for k, f in keys.items()}
    out["popular"] = describe(sorted(chain.index, key=cap, reverse=True)[:8])
    (G.RESULTS / "builder.json").write_text(json.dumps(out, indent=1))
    return out
