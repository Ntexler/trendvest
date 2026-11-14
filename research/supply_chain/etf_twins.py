"""The twin effect without survivorship bias: the same test on sector funds instead of today's companies.

A sector fund (ETF) holds every company of its sector at the time, including the ones that later collapse, so a
result here cannot come from having picked today's winners. Twins: the same sector in different regions,
e.g. US semiconductors (SOXX) -> Korean semiconductors (KODEX 091160) / Taiwan tech (0052) / Japan electric & precision
(1625); US energy (XLE) -> European oil & gas (EXH1) -> Japan energy resources (1618).

Same measures as peer_leadlag/peer_rule: a sector-specific jump in the leader (vs its home index, > 2 usual moves),
then the follower at its next open: the gap, the day, and holding 5 days against the follower's no-signal baseline.

    python -m research.supply_chain.etf_twins     -> results/etf_twins.json
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import markets as MK
from .peer_leadlag import ORDER, REGION

BASE = Path(__file__).parent
OUT = BASE / "results" / "etf_twins.json"
SECTORS = {   # fund ticker -> what it holds (names checked against the fund issuers' tickers; see README in results)
    "semis": ["SOXX", "SMH", "091160.KS", "0052.TW", "1625.T", "512480.SS", "EXV3.DE"],
    "energy": ["XLE", "EXH1.DE", "1618.T"],
    "metals": ["XME", "COPX", "EXV6.DE", "1623.T", "512400.SS"],
    "health": ["XLV", "IBB", "EXV4.DE", "1621.T"],
    "banks": ["KRE", "XLF", "EXV1.DE", "091170.KS", "1631.T"],
    "industrials": ["XLI", "EXH4.DE", "1624.T"],
    "utilities": ["XLU", "EXH9.DE", "1627.T"],
    "chemicals": ["XLB", "EXV7.DE", "1620.T"],
    "autos": ["EXV5.DE", "1622.T"],
}
COST = {"americas": 0.0016, "europe": 0.0022, "asia": 0.0040}    # round trip: broker + spread (+ sale taxes in KR/TW/CN)


def main() -> None:
    import yfinance as yf
    funds = sorted({t for v in SECTORS.values() for t in v})
    bench = sorted({MK.benchmark(t) for t in funds})
    raw = yf.download(funds + bench, start="2016-01-01", auto_adjust=True, progress=False)
    O, C = raw["Open"], raw["Close"]
    P = {}
    for t in funds:
        if t not in C or C[t].notna().sum() < 400:
            continue
        o, c = O[t], C[t]
        ok = o.notna() & c.notna() & (o > 0)
        o, c = o[ok], c[ok]
        b = MK.benchmark(t)
        ob, cb = O[b].reindex(c.index).ffill(), C[b].reindex(c.index).ffill()
        ab = c.pct_change() - cb.pct_change()
        P[t] = pd.DataFrame({"o": o, "c": c, "z": ab / ab.rolling(250, min_periods=60).std().shift(),
                             "gap": (o / c.shift() - 1) - (ob / cb.shift() - 1), "day": (c / o - 1) - (cb / ob - 1),
                             "h5": c.shift(-4) / o - 1, "close": MK.close_utc(t, c.index)}, index=c.index)
    rows, base = [], {}
    for t, d in P.items():
        base[t] = d[d.index >= "2017-01-01"]
    for sec, ts in SECTORS.items():
        ts = [t for t in ts if t in P]
        for a in ts:
            for b in ts:
                ra, rb = REGION(MK.suffix(a)), REGION(MK.suffix(b))
                if a == b or (ra, rb) not in ORDER:
                    continue
                A, B = P[a], P[b]
                sig = A[(A.z.abs() > 2) & (A.index >= "2017-01-01")]
                j = B["close"].searchsorted(sig["close"].to_numpy(), side="right")
                ok = j < len(B) - 5
                for (d, s), jj in zip(sig[ok].iterrows(), j[ok]):
                    r = B.iloc[jj]
                    rows.append({"sector": sec, "leader": a, "follower": b, "dir": f"{ra}→{rb}", "date": B.index[jj], "up": s.z > 0,
                                 "z": s.z, "gap": r.gap, "day": r.day, "h5": r.h5, "base5": base[b].h5.mean(), "cost": COST[rb]})
    D = pd.DataFrame(rows).dropna(subset=["h5"])
    D = D.sort_values("z", key=abs, ascending=False).drop_duplicates(["follower", "date", "up"])   # one trade per fund per day
    D["half"] = np.where(D.date < "2022-01-01", "2017-2021", "2022-2026")

    def block(x):
        s = np.where(x.up, 1, -1)
        return {"events": int(len(x)), "same_dir_gap": round(float((np.sign(x.gap) == s).mean() * 100), 1),
                "same_dir_day": round(float((np.sign(x.day) == s).mean() * 100), 1),
                "hold5_after_jump_pct": round(float(x[x.up].h5.mean() * 100), 3), "baseline5_pct": round(float(x[x.up].base5.mean() * 100), 3),
                "excess5_after_jump_pct": round(float((x[x.up].h5 - x[x.up].base5).mean() * 100), 3),
                "excess5_after_drop_pct": round(float((x[~x.up].h5 - x[~x.up].base5).mean() * 100), 3),
                "net_vs_cash_after_jump_pct": round(float((x[x.up].h5 - x[x.up].cost).mean() * 100), 3),
                "t_excess_jump": round(float(((x[x.up].h5 - x[x.up].base5).mean()) / (x[x.up].h5.std() / np.sqrt(max(1, x.up.sum())))), 2),
                "t_by_day": round(float((lambda e: e.mean() / e.std() * np.sqrt(len(e)))((x[x.up].h5 - x[x.up].base5).groupby(x[x.up].date).mean())), 2)}
    res = {"funds_used": sorted(P), "all": block(D), "by_half": {h: block(g) for h, g in D.groupby("half")},
           "by_sector": {s: block(g) for s, g in D.groupby("sector")}, "by_direction": {d: block(g) for d, g in D.groupby("dir")}}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print("funds:", len(P), sorted(P))
    print("ALL", res["all"])
    for k in ("by_half", "by_direction", "by_sector"):
        for n, v in res[k].items():
            print(k, n, v)


if __name__ == "__main__":
    main()
