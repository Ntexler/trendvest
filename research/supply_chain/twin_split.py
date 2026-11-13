"""Two more cuts of the twin trades (results/peer_trades.csv from peer_rule.py):

1. Was the leader's jump an earnings report or something else? Reports are scheduled and widely read; other news
   (a deal, a regulator, a rumour) may travel more slowly to a twin abroad.
2. The same company listed twice (an American share and its home share): after the American share jumps, does the home
   share still drift after its own next open? If the plainest possible copy is fully priced at the open, a residual
   among twins is more likely slow-moving information than a data quirk.

    python -m research.supply_chain.twin_split     -> results/twin_split.json
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import markets as MK
from .peer_rule import cost

BASE = Path(__file__).parent
OUT = BASE / "results" / "twin_split.json"
K = (1, 5, 10)
ADR = [("TSM", "2330.TW"), ("SONY", "6758.T"), ("TM", "7203.T"), ("MUFG", "8306.T"), ("HMC", "7267.T"), ("BABA", "9988.HK"),
       ("JD", "9618.HK"), ("BIDU", "9888.HK"), ("INFY", "INFY.NS"), ("HDB", "HDFCBANK.NS"), ("IBN", "ICICIBANK.NS"),
       ("ASML", "ASML.AS"), ("SAP", "SAP.DE"), ("NVO", "NOVO-B.CO"), ("SHEL", "SHEL.L"), ("AZN", "AZN.L"),
       ("TEVA", "TEVA.TA"), ("NICE", "NICE.TA"), ("ESLT", "ESLT.TA"), ("ICL", "ICL.TA"), ("TSEM", "TSEM.TA")]


def tday(e, dates):
    s = e.groupby(dates).mean()
    return float(s.mean() / s.std() * np.sqrt(len(s))) if len(s) > 2 and s.std() > 0 else float("nan")


def earnings_split() -> dict:
    T = pd.read_csv(BASE / "results" / "peer_trades.csv", parse_dates=["date"])
    T = T[T.up].copy()
    T["half"] = np.where(T.date < "2022-01-01", "2017-2021", "2022-2026")
    for k in K:
        T[f"x{k}"] = T[f"h{k}"] - np.where(T.half == "2017-2021", T[f"b{k}_2017-2021"], T[f"b{k}_2022-2026"])
    name2 = {}
    earn = {}
    for d in sorted((BASE / "data").iterdir()):
        if (d / "companies.csv").exists():
            c = pd.read_csv(d / "companies.csv", comment="#")
            for r in c.itertuples():
                name2.setdefault(r.name, (d.name, r.id))
        if (d / "earnings.json").exists():
            for cid, v in json.loads((d / "earnings.json").read_text()).items():
                earn[(d.name, cid)] = pd.DatetimeIndex([pd.Timestamp(x).tz_convert("UTC").tz_localize(None).normalize() for x in v])
    def is_report(r):
        e = earn.get(name2.get(r.leader))
        if e is None or len(e) == 0:
            return np.nan
        lag = (r.date - e).days
        return bool(((lag >= 1) & (lag <= 4)).any())   # report in the 1-4 calendar days before the twin's trade day
    T["report"] = [is_report(r) for r in T.itertuples()]
    out = {"leaders_with_calendar_pct": round(float(T.report.notna().mean() * 100), 1)}
    for lab, x in (("leader jumped on its earnings report", T[T.report == True]),     # noqa: E712
                   ("leader jumped on other news", T[T.report == False])):            # noqa: E712
        for half, y in [("all", x)] + list(x.groupby("half")):
            out[f"{lab} · {half}"] = {"trades": int(len(y)), **{f"excess{k}": round(float(y[f"x{k}"].mean() * 100), 3) for k in K},
                                      **{f"t{k}": round(tday(y[f"x{k}"], y.date), 2) for k in K}}
    return out


def same_company() -> dict:
    import yfinance as yf
    tick = sorted({x for p in ADR for x in p})
    bench = sorted({MK.benchmark(t) for t in tick})
    raw = yf.download(tick + bench, start="2016-01-01", auto_adjust=True, progress=False)
    O, C = raw["Open"], raw["Close"]
    rows = []
    for us, home in ADR:
        if us not in C or home not in C or C[home].notna().sum() < 500:
            continue
        a = C[us].dropna()
        ab = a.pct_change() - C["^GSPC"].reindex(a.index).ffill().pct_change()
        z = ab / ab.rolling(250, min_periods=60).std().shift()
        o, c = O[home], C[home]
        ok = o.notna() & c.notna() & (o > 0)
        o, c = o[ok], c[ok]
        hb = MK.benchmark(home)
        ob, cb = O[hb].reindex(c.index).ffill(), C[hb].reindex(c.index).ffill()
        close_a, close_h = MK.close_utc(us, a.index), MK.close_utc(home, c.index)
        sig = z[(z.abs() > 2) & (z.index >= "2017-01-01")].dropna()
        j = close_h.searchsorted(close_a[a.index.get_indexer(sig.index)], side="right")
        for (d, zz), jj in zip(sig.items(), j):
            if jj < 1 or jj + max(K) >= len(c):
                continue
            s = 1 if zz > 0 else -1
            row = {"pair": f"{us}/{home}", "date": c.index[jj], "z": zz, "cost": cost(home, 100.0, 10000),
                   "gap": s * ((o.iloc[jj] / c.iloc[jj - 1] - 1) - (ob.iloc[jj] / cb.iloc[jj - 1] - 1))}
            for k in K:
                row[f"x{k}"] = s * ((c.iloc[jj + k - 1] / o.iloc[jj] - 1) - (cb.iloc[jj + k - 1] / ob.iloc[jj] - 1))
            rows.append(row)
    D = pd.DataFrame(rows)
    D["half"] = np.where(D.date < "2022-01-01", "2017-2021", "2022-2026")
    out = {}
    for half, x in [("all", D)] + list(D.groupby("half")):
        out[half] = {"events": int(len(x)), "gap_in_direction_pct": round(float(x.gap.mean() * 100), 3),
                     **{f"after_open{k}_pct": round(float(x[f"x{k}"].mean() * 100), 3) for k in K},
                     **{f"t{k}": round(tday(x[f"x{k}"], x.date), 2) for k in K}, "cost_pct": round(float(x.cost.mean() * 100), 3)}
    out["by_pair_after_open5"] = {p: round(float(x.x5.mean() * 100), 2) for p, x in D.groupby("pair")}
    return out


def main() -> None:
    res = {"earnings_vs_other": earnings_split(), "same_company_two_listings": same_company()}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
