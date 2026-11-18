"""Do twin trades work better when nobody was watching the twin? (attention; Hou & Moskowitz 2005, Da et al. 2011)
Attention proxy available for every exchange for free: the twin's trading volume on the trade day vs its own 50-day
average (volume of the opening day itself is NOT used to choose - only the previous day's volume, which is known at the open).
Also: the leader's jump size, and whether the twin already moved a lot in its opening gap (gap ate the news?).

    python -m research.supply_chain.twin_attention     -> results/twin_attention.json
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
    import yfinance as yf
    T = pd.read_csv(BASE / "results" / "peer_trades.csv", parse_dates=["date"])
    T = T[T.up].copy()
    T["half"] = np.where(T.date < "2022-01-01", "2017-2021", "2022-2026")
    for k in K:
        T[f"x{k}"] = T[f"h{k}"] - np.where(T.half == "2017-2021", T[f"b{k}_2017-2021"], T[f"b{k}_2022-2026"])
    V = yf.download(sorted(T.twin_t.unique()), start="2016-01-01", auto_adjust=True, progress=False)["Volume"]
    rel = (V / V.rolling(50, min_periods=20).mean().shift()).shift()          # yesterday's volume vs its usual: known at the open
    T["att"] = [rel[t].get(d, np.nan) if t in rel else np.nan for t, d in zip(T.twin_t, T.date)]
    T = T.dropna(subset=["att"])
    q = T.att.quantile([1 / 3, 2 / 3]).to_numpy()
    T["attention"] = np.select([T.att <= q[0], T.att >= q[1]], ["quiet twin (low volume)", "busy twin (high volume)"], "middle")
    T["gapq"] = np.select([T.gap <= 0, T.gap > 0.02], ["twin opened flat/down", "twin opened up >2%"], "twin opened up 0-2%")
    res = {"volume_cutoffs": [round(float(x), 2) for x in q]}
    for col in ("attention", "gapq"):
        for lab, x in T.groupby(col):
            for half, y in [("all", x)] + list(x.groupby("half")):
                res[f"{lab} · {half}"] = {"trades": int(len(y)), **{f"excess{k}": round(float(y[f"x{k}"].mean() * 100), 3) for k in K},
                                          **{f"t{k}": round(tday(y[f"x{k}"], y.date), 2) for k in K}}
    (BASE / "results" / "twin_attention.json").write_text(json.dumps(res, indent=1))
    for k, v in res.items():
        print(k.ljust(44), v)


if __name__ == "__main__":
    main()
