"""Stacking the twin-trade filters found so far, and what is left after costs.

Filters (each known at the twin's open, before buying):
  gap      the twin opened flat or down (it has not yet reacted)               - twin_attention.py
  report   the leader's jump came on its own earnings report                    - twin_split.py
  soon     the twin's own report is due within 2 weeks                           - twin_report.py
  us       the twin is listed in New York (cheap to trade, US hours)
  quiet    the twin's Wikipedia page views the day before were not above usual  - crowd/wiki_signal.py
Excess = twin's return from the open minus its own same-horizon average in that half; t clustered by trade date.
Net = excess minus a round trip for a $10,000 trade (peer_rule.cost).

    python -m research.supply_chain.twin_combo     -> results/twin_combo.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import markets as MK
from .peer_rule import cost
from .twin_split import tday

BASE = Path(__file__).parent
K = (5, 10, 20)


def load() -> pd.DataFrame:
    T = pd.read_csv(BASE / "results" / "peer_trades.csv", parse_dates=["date"])
    T = T[T.up].copy()
    T["half"] = np.where(T.date < "2022-01-01", "2017-2021", "2022-2026")
    for k in K:
        T[f"x{k}"] = T[f"h{k}"] - np.where(T.half == "2017-2021", T[f"b{k}_2017-2021"], T[f"b{k}_2022-2026"])
    byname, bytick, earn = {}, {}, {}
    for d in sorted((BASE / "data").iterdir()):
        if (d / "companies.csv").exists():
            for r in pd.read_csv(d / "companies.csv", comment="#").itertuples():
                byname.setdefault(r.name, (d.name, r.id))
                bytick.setdefault(r.ticker, (d.name, r.id))
        if (d / "earnings.json").exists():
            for cid, v in json.loads((d / "earnings.json").read_text()).items():
                earn[(d.name, cid)] = pd.DatetimeIndex([pd.Timestamp(x).tz_convert("UTC").tz_localize(None).normalize() for x in v])

    def near(key, date, lo, hi):
        e = earn.get(key)
        if e is None or len(e) == 0:
            return np.nan
        g = (e - date).days
        return bool(((g >= lo) & (g <= hi)).any())
    T["gapf"] = T.gap <= 0
    T["report"] = [near(byname.get(r.leader), r.date, -4, -1) for r in T.itertuples()]
    T["soon"] = [near(bytick.get(r.twin_t), r.date, 0, 14) for r in T.itertuples()]
    T["us"] = [MK.suffix(t) == "" for t in T.twin_t]
    T["cost"] = [cost(t, 100.0, 10000) for t in T.twin_t]
    wf = Path(__file__).parents[1] / "crowd" / "data" / "wiki_views.csv"
    T["quiet"] = np.nan
    if wf.exists():
        from research.crowd.wiki_signal import BAD
        W = pd.read_csv(wf).dropna()
        W = W[~W.ticker.isin(BAD)]
        W["date"] = pd.to_datetime(W.date.astype(int).astype(str))
        V = W.pivot_table(index="date", columns="ticker", values="views").sort_index()
        prev = (V / V.shift().rolling(56, min_periods=40).median()).shift()
        att = [prev[t].get(d, np.nan) if t in prev else np.nan for t, d in zip(T.twin_t, T.date)]
        T["quiet"] = pd.Series(att, index=T.index).map(lambda a: np.nan if pd.isna(a) else a <= 1.0)
    return T


def block(x):
    out = {"trades": int(len(x)), "days": int(x.date.nunique()), "cost": round(float(x.cost.mean() * 100), 2)}
    for k in K:
        out[f"x{k}"] = round(float(x[f"x{k}"].mean() * 100), 2)
        out[f"t{k}"] = round(tday(x[f"x{k}"], x.date), 2)
        out[f"net{k}"] = round(float((x[f"x{k}"] - x.cost).mean() * 100), 2)
    out["halves_x10"] = {h: [round(float(y.x10.mean() * 100), 2), round(tday(y.x10, y.date), 2), int(len(y))] for h, y in x.groupby("half")}
    return out


def main() -> None:
    T = load()
    combos = {
        "all twin trades": T.index == T.index,
        "gap": T.gapf,
        "us": T.us,
        "gap + us": T.gapf & T.us,
        "report": T.report == True,                               # noqa: E712
        "report + gap": (T.report == True) & T.gapf,             # noqa: E712
        "report + soon": (T.report == True) & (T.soon == True),  # noqa: E712
        "report + soon + gap": (T.report == True) & (T.soon == True) & T.gapf,  # noqa: E712
        "quiet": T.quiet == True,                                 # noqa: E712
        "gap + quiet": T.gapf & (T.quiet == True),               # noqa: E712
        "gap + not quiet": T.gapf & (T.quiet == False),          # noqa: E712
        "gap + us + quiet": T.gapf & T.us & (T.quiet == True),   # noqa: E712
    }
    res = {k: block(T[m]) for k, m in combos.items() if m.sum() >= 30}
    (BASE / "results" / "twin_combo.json").write_text(json.dumps(res, indent=1))
    for k, v in res.items():
        print(k.ljust(22), v)


if __name__ == "__main__":
    main()
