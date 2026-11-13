"""After a leader's earnings jump: is the twin's drift bigger when the twin's OWN report is coming soon?
(Thomas & Zhang 2008: investors under-use a peer's report when pricing a firm that reports later.)
Reads results/peer_trades.csv (buy after a jump) and the official earnings calendars in data/*/earnings.json.

    python -m research.supply_chain.twin_report     -> results/twin_report.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .twin_split import tday

BASE = Path(__file__).parent
K = (1, 5, 10)


def main() -> None:
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

    def lag_to(key, date, lo, hi):
        e = earn.get(key)
        if e is None or len(e) == 0:
            return np.nan
        g = (e - date).days
        return bool(((g >= lo) & (g <= hi)).any())
    T["leader_report"] = [lag_to(byname.get(r.leader), r.date, -4, -1) for r in T.itertuples()]
    T["twin_soon"] = [lag_to(bytick.get(r.twin_t), r.date, 0, 14) for r in T.itertuples()]
    T["twin_has_cal"] = [bytick.get(t) in earn for t in T.twin_t]
    X = T[(T.leader_report == True) & T.twin_has_cal]  # noqa: E712
    res = {}
    for lab, x in (("twin reports within 2 weeks", X[X.twin_soon == True]), ("twin reports later", X[X.twin_soon == False])):  # noqa: E712
        for half, y in [("all", x)] + list(x.groupby("half")):
            res[f"{lab} · {half}"] = {"trades": int(len(y)), **{f"excess{k}": round(float(y[f"x{k}"].mean() * 100), 3) for k in K},
                                      **{f"t{k}": round(tday(y[f"x{k}"], y.date), 2) for k in K}}
    (BASE / "results" / "twin_report.json").write_text(json.dumps(res, indent=1))
    for k, v in res.items():
        print(k.ljust(42), v)


if __name__ == "__main__":
    main()
