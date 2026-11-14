"""Other ways information may travel slowly between related companies, tested like the twins (peer_robust.py).

Families of pairs (leader -> follower):
  customer->supplier   a customer jumps; does its supplier follow?   (our supplier-customer map, all markets)
  supplier->customer   the other way
  big->small           the largest company of a segment jumps; do the smaller ones in the SAME region follow? (Hou 2007)
  twins                same segment, other region (the original finding, for comparison)
For each: buy the follower at its next open after the leader's company-specific jump (> 2 usual moves), hold 1/5/10 sessions;
excess = minus the follower's own average for that holding period in that half; t clustered by date; both halves.

    python -m research.supply_chain.follow       -> results/follow.json
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import graph as G  # noqa: F401  (keeps MARKET import side effects consistent)
from . import markets as MK
from .peer_leadlag import ORDER, REGION

BASE = Path(__file__).parent
OUT = BASE / "results" / "follow.json"
K = (1, 5, 10)


def companies() -> pd.DataFrame:
    rows = []
    for d in sorted((BASE / "data").iterdir()):
        if (d / "companies.csv").exists():
            c = pd.read_csv(d / "companies.csv", comment="#")
            c["market"] = d.name
            rows.append(c)
    c = pd.concat(rows)
    return c[c.tier != "control"]


def pairs() -> list[tuple[str, str, str]]:
    c = companies()
    tick = {(r.market, r.id): r.ticker for r in c.itertuples()}
    out = set()
    for d in sorted((BASE / "data").iterdir()):
        if (d / "edges.csv").exists():
            e = pd.read_csv(d / "edges.csv", comment="#")
            for r in e.itertuples():
                s, t = tick.get((d.name, r.supplier)), tick.get((d.name, r.customer))
                if s and t and s != t:
                    out.add((t, s, "customer->supplier"))
                    out.add((s, t, "supplier->customer"))
    c = c.drop_duplicates("ticker").copy()
    c["region"] = c.ticker.map(lambda t: REGION(MK.suffix(t)))
    prof = {}
    for d in sorted((BASE / "data").iterdir()):
        if (d / "profiles.json").exists():
            for k, v in json.loads((d / "profiles.json").read_text()).items():
                prof[(d.name, k)] = (v.get("info") or {}).get("marketCapUSD") or 0
    c["cap"] = [prof.get((r.market, r.id), 0) for r in c.itertuples()]
    c["seg"] = c.market + ":" + c.segment
    for (seg, reg), g in c.groupby(["seg", "region"]):
        if len(g) < 2:
            continue
        g = g.sort_values("cap", ascending=False)
        for small in g.ticker.iloc[1:]:
            out.add((g.ticker.iloc[0], small, "big->small"))
    for seg, g in c.groupby("seg"):
        for a in g.itertuples():
            for b in g.itertuples():
                if a.ticker != b.ticker and (a.region, b.region) in ORDER:
                    out.add((a.ticker, b.ticker, "twins"))
    return sorted(out)


def main() -> None:
    import yfinance as yf
    P = pairs()
    tick = sorted({x for a, b, _ in P for x in (a, b)})
    bench = sorted({MK.benchmark(t) for t in tick})
    raw = yf.download(tick + bench, start="2016-01-01", auto_adjust=True, progress=False)
    O, C = raw["Open"], raw["Close"]
    info, base = {}, {}
    for t in tick:
        if t not in C or C[t].notna().sum() < 500:
            continue
        o, c = O[t], C[t]
        ok = o.notna() & c.notna() & (o > 0)
        o, c = o[ok], c[ok]
        cb = C[MK.benchmark(t)].reindex(c.index).ffill()
        ab = c.pct_change() - cb.pct_change()
        info[t] = {"o": o, "c": c, "z": ab / ab.rolling(250, min_periods=60).std().shift(), "close": MK.close_utc(t, c.index)}
        base[t] = {}
        for k in K:
            r = c.shift(-(k - 1)) / o - 1
            base[t][("2017-2021", k)] = float(r[(c.index >= "2017-01-01") & (c.index < "2022-01-01")].mean())
            base[t][("2022-2026", k)] = float(r[c.index >= "2022-01-01"].mean())
    rows = []
    for a, b, fam in P:
        if a not in info or b not in info:
            continue
        A, B = info[a], info[b]
        sig = A["z"][(A["z"] > 2) & (A["z"].index >= "2017-01-01")].dropna()
        if sig.empty:
            continue
        pos = B["close"].searchsorted(A["close"][A["z"].index.get_indexer(sig.index)], side="right")
        for (d, z), j in zip(sig.items(), pos):
            if j + max(K) >= len(B["c"]):
                continue
            o = B["o"].iloc[j]
            half = "2017-2021" if B["c"].index[j] < pd.Timestamp("2022-01-01") else "2022-2026"
            row = {"fam": fam, "leader": a, "follower": b, "date": B["c"].index[j], "half": half, "z": z}
            for k in K:
                row[f"x{k}"] = B["c"].iloc[j + k - 1] / o - 1 - base[b][(half, k)]
            rows.append(row)
    D = pd.DataFrame(rows).sort_values("z", ascending=False).drop_duplicates(["fam", "follower", "date"])

    def tday(e, dates):
        s = e.groupby(dates).mean()
        return float(s.mean() / s.std() * np.sqrt(len(s))) if len(s) > 2 and s.std() > 0 else float("nan")
    res = {}
    for fam, g in D.groupby("fam"):
        for half, x in [("all", g)] + list(g.groupby("half")):
            res[f"{fam} · {half}"] = {"trades": int(len(x)), **{f"excess{k}": round(float(x[f"x{k}"].mean() * 100), 3) for k in K},
                                      **{f"t{k}": round(tday(x[f"x{k}"], x.date), 2) for k in K}}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for k, v in res.items():
        print(k.ljust(34), v)


if __name__ == "__main__":
    main()
