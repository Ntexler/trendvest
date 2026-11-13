"""Reddit r/wallstreetbets attention as a signal (daily top-50 by comments, tradestie.com, 2021-04 on).

Signals for ticker X on day d (data of day d is used from the NEXT trading day's open, so nothing is known too early):
  new entry   X is in the top 50 today and was absent for the previous 10 trading days
  surge       X's comments today >= 3x its average of the previous 20 trading days (absent = 0) and >= 50 comments
  top 5       X is among the 5 most discussed today
  bullish / bearish   the crowd's tone on that day (any appearance)
Return: from the next open to the close 1/5/20 trading days later, minus the S&P 500 (SPY) over the same span.
Cost of a round trip in a US stock ~0.13% (peer_rule.cost). Literature: Bradley, Hanousek, Jame & Xiao (2024).

    python -m research.crowd.wsb_signal      -> data/wsb_signal.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

D = Path(__file__).parent / "data"
K = (1, 5, 20)
COST = 0.0013


def tday(e, dates):
    s = e.groupby(dates).mean()
    return float(s.mean() / s.std() * np.sqrt(len(s))) if len(s) > 2 and s.std() > 0 else float("nan")


def main() -> None:
    import yfinance as yf
    W = pd.read_csv(D / "wsb_daily.csv").dropna(subset=["ticker"])
    W["date"] = pd.to_datetime(W.date)
    days = sorted(W.date.unique())
    C = W.pivot_table(index="date", columns="ticker", values="no_of_comments", aggfunc="sum").reindex(days).fillna(0)
    present = C > 0
    prior = present.shift().rolling(10, min_periods=10).sum()
    avg20 = C.shift().rolling(20, min_periods=20).mean()
    sig = {"new entry": present & (prior == 0), "surge": (C >= 3 * avg20) & (C >= 50) & (avg20 > 0),
           "top 5": W.pivot_table(index="date", columns="ticker", values="rank", aggfunc="min").reindex(days).le(5)}
    tick = sorted(C.columns)
    px = yf.download(tick + ["SPY"], start="2021-03-01", auto_adjust=True, progress=False)
    O, Cl = px["Open"], px["Close"]
    idx = Cl.index
    tone = W.set_index(["date", "ticker"]).sentiment
    rows = []
    for name, m in list(sig.items()) + [("any appearance", present)]:
        st = m.stack()
        st = st[st]
        for (d, t), _ in st.items():
            if t not in Cl or Cl[t].notna().sum() < 100:
                continue
            i = idx.searchsorted(d, side="right")              # next trading day after the comments' day
            if i + max(K) >= len(idx):
                continue
            o, so = O[t].iloc[i], O["SPY"].iloc[i]
            if not (o > 0):
                continue
            r = {"signal": name, "ticker": t, "date": idx[i], "tone": tone.get((d, t), "?")}
            for k in K:
                r[f"x{k}"] = (Cl[t].iloc[i + k - 1] / o - 1) - (Cl["SPY"].iloc[i + k - 1] / so - 1)
            rows.append(r)
    R = pd.DataFrame(rows).dropna(subset=[f"x{k}" for k in K])
    R["year"] = R.date.dt.year

    def block(x):
        return {"trades": int(len(x)), **{f"excess{k}": round(float(x[f"x{k}"].mean() * 100), 2) for k in K},
                **{f"median{k}": round(float(x[f"x{k}"].median() * 100), 2) for k in K},
                **{f"t{k}": round(tday(x[f"x{k}"], x.date), 2) for k in K}}
    res = {}
    for s, g in R.groupby("signal"):
        res[s] = block(g)
        for tn, x in g.groupby("tone"):
            if len(x) >= 50:
                res[f"{s} · {tn}"] = block(x)
        res[f"{s} · by year"] = {int(y): round(float(x.x20.mean() * 100), 2) for y, x in g.groupby("year")}
    res["cost_round_trip_pct"] = COST * 100
    (D / "wsb_signal.json").write_text(json.dumps(res, indent=1))
    for k, v in res.items():
        print(k.ljust(30), v)


if __name__ == "__main__":
    main()
