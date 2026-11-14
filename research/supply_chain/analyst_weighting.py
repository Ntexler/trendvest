"""Are analysts getting better, and does weighting them by their own record improve the forecast?

Monthly, 2016 to today, for every US company of ours with at least 3 analysts active in the last 120 days:
  plain     average of each firm's latest target, as a 12-month return from today's price
  weighted  the same, each firm weighted by 1 / its typical error so far (median absolute miss)
  adjusted  each firm's target minus its usual bias so far (median over-promise)
A firm's record at month m uses ONLY its targets whose 12 months ended before m: no look-ahead.
Scored against the price 12 months later, and against that minus the S&P 500 (to remove good and bad years).

Two questions per year (the "improvement" chart):
  error   median absolute miss of a single analyst target
  order   rank correlation, across companies, between the consensus and what happened (0 = no skill)

    python -m research.supply_chain.analyst_weighting   (needs results/analyst_targets.csv from analysts.py)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).parent
IN, OUT = BASE / "results" / "analyst_targets.csv", BASE / "results" / "analyst_weighting.json"
MIN_FIRM = 20


def main() -> None:
    import yfinance as yf
    T = pd.read_csv(IN, parse_dates=["date"])
    T["firm"] = T["firm"].fillna("?")
    px = yf.download(sorted(T.ticker.unique()) + ["SPY"], start="2014-06-01", auto_adjust=False, progress=False)["Close"].ffill()
    months = pd.date_range("2016-01-31", px.index[-1], freq="ME")
    rows = []
    for m in months:
        mm = px.index[px.index.searchsorted(m) - 1] if px.index.searchsorted(m) else px.index[0]
        later_i = px.index.searchsorted(mm + pd.Timedelta(days=365))
        has_future = later_i < len(px)
        done = T[(T.date <= m - pd.Timedelta(days=365)) & T.realized.notna()]
        g = done.groupby("firm")
        skill = pd.DataFrame({"ae": g.apply(lambda x: (x.implied - x.realized).abs().median(), include_groups=False),
                              "bias": g.apply(lambda x: (x.implied - x.realized).median(), include_groups=False), "n": g.size()})
        ae_all = (done.implied - done.realized).abs().median() if len(done) else 0.3
        bias_all = (done.implied - done.realized).median() if len(done) else 0.0
        act = T[(T.date > m - pd.Timedelta(days=120)) & (T.date <= m)].sort_values("date").groupby(["ticker", "firm"]).tail(1)
        spy_r = px["SPY"].iloc[later_i] / px.loc[mm, "SPY"] - 1 if has_future else np.nan
        for t, a in act.groupby("ticker"):
            if len(a) < 3 or t not in px or pd.isna(px.loc[mm, t]):
                continue
            imp = a.target.to_numpy() / px.loc[mm, t] - 1
            sk = skill.reindex(a.firm)
            ok = (sk.n >= MIN_FIRM).to_numpy()
            ae = np.where(ok, sk.ae.to_numpy(), ae_all)
            bias = np.where(ok, sk.bias.to_numpy(), bias_all)
            R = px[t].iloc[later_i] / px.loc[mm, t] - 1 if has_future else np.nan
            rows.append({"month": m, "ticker": t, "n": len(a), "plain": imp.mean(), "weighted": np.sum(imp / ae) / np.sum(1 / ae),
                         "adjusted": np.mean(imp - bias), "realized": R, "excess": R - spy_r, "known_firms": int(ok.sum())})
    D = pd.DataFrame(rows)
    S = D.dropna(subset=["realized"])
    S = S[S.month >= "2017-01-01"]                                   # firms need a year of record first
    res = {"months": int(S.month.nunique()), "observations": int(len(S)), "methods": {}}
    for k in ("plain", "weighted", "adjusted"):
        ic = S.groupby("month").apply(lambda x: x[k].rank().corr(x.realized.rank()), include_groups=False).dropna()
        icx = S.groupby("month").apply(lambda x: x[k].rank().corr(x.excess.rank()), include_groups=False).dropna()
        res["methods"][k] = {"abs_error_median": round(float((S[k] - S.realized).abs().median() * 100), 1),
                             "bias_median": round(float((S[k] - S.realized).median() * 100), 1),
                             "order_corr": round(float(ic.mean()), 3), "order_t": round(float(ic.mean() / ic.std() * np.sqrt(len(ic) / 12)), 2),
                             "order_corr_excess": round(float(icx.mean()), 3)}
    # the improvement chart, by year
    T2 = T.dropna(subset=["realized"])
    yr = {}
    for y, g in T2.groupby(T2.date.dt.year):
        s_y = S[S.month.dt.year == y]
        ic = s_y.groupby("month").apply(lambda x: x.plain.rank().corr(x.realized.rank()), include_groups=False).dropna() if len(s_y) else pd.Series(dtype=float)
        icw = s_y.groupby("month").apply(lambda x: x.weighted.rank().corr(x.realized.rank()), include_groups=False).dropna() if len(s_y) else pd.Series(dtype=float)
        yr[int(y)] = {"targets": int(len(g)), "single_abs_error": round(float((g.implied - g.realized).abs().median() * 100), 1),
                      "single_direction_right": round(float((np.sign(g.implied) == np.sign(g.realized)).mean() * 100), 1),
                      "order_corr_plain": None if ic.empty else round(float(ic.mean()), 3),
                      "order_corr_weighted": None if icw.empty else round(float(icw.mean()), 3)}
    res["by_year"] = yr
    # firms with the best and worst record over the whole period (at least 100 scored targets)
    fe = T2.groupby("firm").apply(lambda x: pd.Series({"n": len(x), "ae": (x.implied - x.realized).abs().median() * 100,
                                                      "bias": (x.implied - x.realized).median() * 100}), include_groups=False)
    fe = fe[fe.n >= 100].sort_values("ae")
    res["firms_best"] = fe.head(8).round(1).reset_index().to_dict("records")
    res["firms_worst"] = fe.tail(8).round(1).reset_index().to_dict("records")
    res["firm_spread"] = {"best_ae": round(float(fe.ae.min()), 1), "median_ae": round(float(fe.ae.median()), 1), "worst_ae": round(float(fe.ae.max()), 1), "firms": int(len(fe))}
    # today's consensus for each company, plain and weighted with the full record
    done = T2
    g = done.groupby("firm")
    skill = pd.DataFrame({"ae": g.apply(lambda x: (x.implied - x.realized).abs().median(), include_groups=False), "n": g.size()})
    last = px.index[-1]
    act = T[T.date > last - pd.Timedelta(days=120)].sort_values("date").groupby(["ticker", "firm"]).tail(1)
    now = {}
    for t, a in act.groupby("ticker"):
        if len(a) < 3 or t not in px:
            continue
        imp = a.target.to_numpy() / px[t].iloc[-1] - 1
        sk = skill.reindex(a.firm)
        ae = np.where((sk.n >= MIN_FIRM).to_numpy(), sk.ae.to_numpy(), (done.implied - done.realized).abs().median())
        now[t] = {"n": int(len(a)), "plain": round(float(imp.mean() * 100), 1), "weighted": round(float(np.sum(imp / ae) / np.sum(1 / ae) * 100), 1),
                  "low": round(float(imp.min() * 100), 1), "high": round(float(imp.max() * 100), 1)}
    res["now"] = now
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    print(json.dumps({k: res[k] for k in ("months", "observations", "methods", "firm_spread")}, indent=1))
    for y, v in yr.items():
        print(y, v)
    print("MU now:", now.get("MU"))


if __name__ == "__main__":
    main()
