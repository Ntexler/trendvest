"""Attention spikes on Wikipedia as a signal, and attention as a filter on the twin trade.

Spike: yesterday's page views >= 3x the median of the 56 days before (and >= 500 views). Views of day d are complete at
midnight UTC, so the trade is at the next open after that (Asia: same calendar day d+1; US/Europe: d+1).
Return: next open -> close 1/5/20 sessions later, minus the company's home index. t clustered by date. Both halves.
Literature: Da, Engelberg & Gao (2011) - attention brings a short rise that later reverses; Moat et al. (2013).
Twin filter: twin trades (peer_trades.csv) split by the twin's own Wikipedia attention on the day before the trade.

    python -m research.crowd.wiki_signal     -> data/wiki_signal.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.supply_chain import markets as MK

D = Path(__file__).parent / "data"
SC = Path(__file__).parents[1] / "supply_chain"
K = (1, 5, 20)


def tday(e, dates):
    s = e.groupby(dates).mean()
    return float(s.mean() / s.std() * np.sqrt(len(s))) if len(s) > 2 and s.std() > 0 else float("nan")


def block(x, k=K):
    return {"n": int(len(x)), **{f"excess{h}": round(float(x[f"x{h}"].mean() * 100), 2) for h in k},
            **{f"t{h}": round(tday(x[f"x{h}"], x.date), 2) for h in k}}


def main() -> None:
    import yfinance as yf
    W = pd.read_csv(D / "wiki_views.csv").dropna()
    W["date"] = pd.to_datetime(W.date.astype(int).astype(str))
    V = W.pivot_table(index="date", columns="ticker", values="views").sort_index()
    ratio = V / V.shift().rolling(56, min_periods=40).median()
    spike = (ratio >= 3) & (V >= 500)
    tick = list(V.columns)
    bench = sorted({MK.benchmark(t) for t in tick})
    px = yf.download(tick + bench, start="2016-01-01", auto_adjust=True, progress=False)
    O, C = px["Open"], px["Close"]
    rows = []
    for t in tick:
        if t not in C or C[t].notna().sum() < 300:
            continue
        o, c = O[t].dropna(), C[t].dropna()
        idx = c.index.intersection(o.index)
        o, c = o[idx], c[idx]
        b = MK.benchmark(t)
        ob, cb = O[b].reindex(idx).ffill(), C[b].reindex(idx).ffill()
        for d in spike.index[spike[t].fillna(False)]:
            i = idx.searchsorted(d + pd.Timedelta(days=1))
            if i + max(K) >= len(idx) or d < pd.Timestamp("2016-04-01"):
                continue
            r = {"ticker": t, "date": idx[i], "ratio": float(ratio.at[d, t])}
            for k in K:
                r[f"x{k}"] = (c.iloc[i + k - 1] / o.iloc[i] - 1) - (cb.iloc[i + k - 1] / ob.iloc[i] - 1)
            rows.append(r)
    R = pd.DataFrame(rows).dropna()
    R["half"] = np.where(R.date < "2021-07-01", "2016-2021", "2021-2026")
    res = {"spikes": block(R), **{f"spikes · {h}": block(x) for h, x in R.groupby("half")},
           "spikes ratio >= 10": block(R[R.ratio >= 10])}
    # twin filter
    T = pd.read_csv(SC / "results" / "peer_trades.csv", parse_dates=["date"])
    T = T[T.up].copy()
    T["half"] = np.where(T.date < "2022-01-01", "2017-2021", "2022-2026")
    for k in (5, 10):
        T[f"x{k}"] = T[f"h{k}"] - np.where(T.half == "2017-2021", T[f"b{k}_2017-2021"], T[f"b{k}_2022-2026"])
    prev = ratio.shift()          # the twin's attention the day before its trade day (known at the open)
    T["att"] = [prev[t].get(d, np.nan) if t in prev else np.nan for t, d in zip(T.twin_t, T.date)]
    T = T.dropna(subset=["att"])
    q = T.att.quantile([1 / 3, 2 / 3]).to_numpy()
    T["grp"] = np.select([T.att <= q[0], T.att >= q[1]], ["quiet", "noticed"], "middle")
    res["twin_by_attention_cutoffs"] = [round(float(x), 2) for x in q]
    for g, x in T.groupby("grp"):
        res[f"twin · {g}"] = block(x, (5, 10))
        for h, y in x.groupby("half"):
            res[f"twin · {g} · {h}"] = block(y, (5, 10))
    (D / "wiki_signal.json").write_text(json.dumps(res, indent=1))
    for k, v in res.items():
        print(k.ljust(30), v)


if __name__ == "__main__":
    main()
