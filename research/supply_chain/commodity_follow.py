"""Does a jump in a raw material's price carry over to the companies that produce it, on any exchange?

Commodity futures (oil, gas, copper, gold, silver, uranium proxy) settle in the US afternoon, after Asia and Europe have
closed and before the next session anywhere. Signal: the futures price moves more than 2 of its usual daily moves.
Follower: each producer, bought at its NEXT open (the next calendar trading day), held 1/5/10 sessions.
Excess = minus the producer's own average for that holding period in that half; t clustered by date; both halves.
Also reported: the gap (what happened between the close and the open, which an investor cannot catch).

    python -m research.supply_chain.commodity_follow     -> results/commodity_follow.json
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).parent
OUT = BASE / "results" / "commodity_follow.json"
MAP = {"CL=F": ("oil", {"energy": ["oil-gas-major", "lng"]}), "NG=F": ("gas", {"energy": ["gas-producer", "lng"]}),
       "HG=F": ("copper", {"minerals": ["copper", "copper-smelting", "diversified-miner"]}),
       "GC=F": ("gold", {"minerals": ["gold", "royalty-streaming"]}), "SI=F": ("silver", {"minerals": ["royalty-streaming", "gold"]}),
       "ALI=F": ("aluminium", {"minerals": ["diversified-miner"]})}
K = (1, 5, 10)


def main() -> None:
    import yfinance as yf
    groups = {}
    for fut, (name, segs) in MAP.items():
        tick = []
        for m, ss in segs.items():
            c = pd.read_csv(BASE / "data" / m / "companies.csv", comment="#")
            tick += list(c[c.segment.isin(ss)].ticker)
        groups[fut] = sorted(set(tick))
    allt = sorted({t for v in groups.values() for t in v})
    raw = yf.download(sorted(MAP) + allt, start="2016-01-01", auto_adjust=True, progress=False)
    O, C = raw["Open"], raw["Close"]
    rows = []
    for fut, tick in groups.items():
        f = C[fut].dropna()
        f = f[f > 0]
        r = f.pct_change()
        z = r / r.rolling(250, min_periods=60).std().shift()
        sig = z[(z.abs() > 2) & (z.index >= "2017-01-01")].dropna()
        for t in tick:
            if t not in C or C[t].notna().sum() < 500:
                continue
            o, c = O[t], C[t]
            ok = o.notna() & c.notna() & (o > 0)
            o, c = o[ok], c[ok]
            base = {}
            for k in K:
                rr = c.shift(-(k - 1)) / o - 1
                base[("2017-2021", k)] = float(rr[(c.index >= "2017-01-01") & (c.index < "2022-01-01")].mean())
                base[("2022-2026", k)] = float(rr[c.index >= "2022-01-01"].mean())
            idx = c.index.searchsorted(sig.index, side="right")      # next trading day after the futures day
            for (d, zz), j in zip(sig.items(), idx):
                if j < 1 or j + max(K) >= len(c):
                    continue
                half = "2017-2021" if c.index[j] < pd.Timestamp("2022-01-01") else "2022-2026"
                s = 1 if zz > 0 else -1
                row = {"commodity": MAP[fut][0], "ticker": t, "date": c.index[j], "half": half, "up": zz > 0,
                       "gap_same": np.sign(o.iloc[j] / c.iloc[j - 1] - 1) == s}
                for k in K:
                    row[f"x{k}"] = s * (c.iloc[j + k - 1] / o.iloc[j] - 1 - base[(half, k)])   # in the commodity's direction
                rows.append(row)
    D = pd.DataFrame(rows)

    def tday(e, dates):
        s = e.groupby(dates).mean()
        return float(s.mean() / s.std() * np.sqrt(len(s))) if len(s) > 2 and s.std() > 0 else float("nan")

    def block(x):
        return {"trades": int(len(x)), "gap_same_dir_pct": round(float(x.gap_same.mean() * 100), 1),
                **{f"follow{k}": round(float(x[f"x{k}"].mean() * 100), 3) for k in K}, **{f"t{k}": round(tday(x[f"x{k}"], x.date), 2) for k in K}}
    res = {}
    for name, g in [("all", D)] + list(D.groupby("commodity")):
        res[name] = block(g)
        for h, x in g.groupby("half"):
            res[f"{name} · {h}"] = block(x)
        for u, x in g.groupby("up"):
            res[f"{name} · {'after a jump' if u else 'after a drop'}"] = block(x)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for k, v in res.items():
        print(k.ljust(30), v)


if __name__ == "__main__":
    main()
