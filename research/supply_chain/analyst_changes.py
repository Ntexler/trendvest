"""Do changes in analysts' price targets move the stock in the days after?

Event: one firm raises or cuts its 12-month target on one company (vs. that firm's previous target on it, set within
the past 400 days; first targets are "new"). Prices are split-adjusted daily closes; "excess" = minus the S&P 500.

  day 0       the first trading day on or after the publication date (includes the reaction to the news itself)
  after 1-20  from the close of day 0 onward: what an investor who read it that evening could still get

Changes are split into "alone" (no other firm changed its target on that company within 2 days either side) and
"in a wave" (usually around a quarterly report, when everyone updates at once).
Significance: results are averaged per calendar day first, then a t-statistic over days, so one busy day counts once.

    python -m research.supply_chain.analyst_changes     (uses results/analyst_targets.csv)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).parent
IN, OUT = BASE / "results" / "analyst_targets.csv", BASE / "results" / "analyst_changes.json"
H = [1, 5, 20, 60]


def tstat(df: pd.DataFrame, col: str) -> float:
    s = df.groupby("d0")[col].mean().dropna()
    return float(s.mean() / s.std() * np.sqrt(len(s))) if len(s) > 2 and s.std() > 0 else float("nan")


def main() -> None:
    import yfinance as yf
    T = pd.read_csv(IN, parse_dates=["date"]).sort_values("date")
    T["firm"] = T["firm"].fillna("?")
    T["prev"] = T.groupby(["ticker", "firm"])["target"].shift()
    T["prev_date"] = T.groupby(["ticker", "firm"])["date"].shift()
    T["chg"] = np.where((T.date - T.prev_date).dt.days <= 400, T.target / T.prev - 1, np.nan)
    T["kind"] = np.select([T.chg > 0.02, T.chg < -0.02, T.chg.isna()], ["raise", "cut", "new"], "same")
    T = T[T.kind != "same"]
    near = T.groupby("ticker")["date"].transform(lambda s: [((s - x).abs().dt.days <= 2).sum() - 1 for x in s])
    T["wave"] = near > 0
    px = yf.download(sorted(T.ticker.unique()) + ["SPY"], start="2014-06-01", auto_adjust=False, progress=False)["Close"]
    idx = px.index
    rows = []
    for r in T.itertuples():
        if r.ticker not in px:
            continue
        i = idx.searchsorted(r.date.normalize())
        if i < 1 or i >= len(idx):
            continue
        p, s = px[r.ticker].to_numpy(), px["SPY"].to_numpy()
        if np.isnan(p[i]) or np.isnan(p[i - 1]):
            continue
        row = {"ticker": r.ticker, "d0": idx[i], "kind": r.kind, "wave": r.wave, "chg": r.chg,
               "day0": (p[i] / p[i - 1] - 1) - (s[i] / s[i - 1] - 1)}
        for h in H:
            row[f"a{h}"] = (p[i + h] / p[i] - 1) - (s[i + h] / s[i] - 1) if i + h < len(idx) and not np.isnan(p[i + h]) else np.nan
        rows.append(row)
    D = pd.DataFrame(rows)
    D["year"] = D.d0.dt.year

    def block(x: pd.DataFrame) -> dict:
        out = {"n": int(len(x)), "day0_mean": round(float(x.day0.mean() * 100), 2), "day0_t": round(tstat(x, "day0"), 1)}
        for h in H:
            out[f"after{h}_mean"] = round(float(x[f"a{h}"].mean() * 100), 2)
            out[f"after{h}_t"] = round(tstat(x, f"a{h}"), 1)
            out[f"after{h}_up_pct"] = round(float((x[f"a{h}"] > 0).mean() * 100), 1)
        return out

    res = {"events": int(len(D)), "companies": int(D.ticker.nunique()), "groups": {}}
    for k in ("raise", "cut", "new"):
        for w, wn in ((False, "alone"), (True, "in_wave")):
            x = D[(D.kind == k) & (D.wave == w)]
            if len(x) > 50:
                res["groups"][f"{k}_{wn}"] = block(x)
    big = D[(D.kind == "raise") & (D.chg > 0.25) & ~D.wave]
    deep = D[(D.kind == "cut") & (D.chg < -0.20) & ~D.wave]
    res["groups"]["raise_over_25pct_alone"] = block(big) if len(big) > 30 else None
    res["groups"]["cut_over_20pct_alone"] = block(deep) if len(deep) > 30 else None
    # stability: the alone raise-minus-cut spread after 20 days, by year
    by_year = {}
    for y, g in D[~D.wave].groupby("year"):
        r_, c_ = g[g.kind == "raise"].a20.mean(), g[g.kind == "cut"].a20.mean()
        by_year[int(y)] = {"raise_after20": round(float(r_ * 100), 2), "cut_after20": round(float(c_ * 100), 2),
                           "spread": round(float((r_ - c_) * 100), 2), "n": int(len(g))}
    res["by_year_alone"] = by_year
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(f"{res['events']} target changes on {res['companies']} companies")
    for k, v in res["groups"].items():
        if v:
            print(f"{k:24s} n={v['n']:6d} day0 {v['day0_mean']:+.2f}% (t {v['day0_t']:+.1f}) | after5 {v['after5_mean']:+.2f}% (t {v['after5_t']:+.1f}) "
                  f"| after20 {v['after20_mean']:+.2f}% (t {v['after20_t']:+.1f}, up {v['after20_up_pct']}%) | after60 {v['after60_mean']:+.2f}% (t {v['after60_t']:+.1f})")
    for y, v in by_year.items():
        print(y, v)


if __name__ == "__main__":
    main()
