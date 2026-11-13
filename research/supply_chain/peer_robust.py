"""Robustness of the twin effect on single companies (reads results/peer_trades.csv from peer_rule.py).

For "buy the twin at its next open after the leader jumps", at holding periods of 1, 3, 5, 10 and 20 sessions:
  excess  = the trade's return minus the same twin's average return over the same holding period on any day of that half
  t       = clustered by trade date (a busy day counts once)
  net     = gross return minus round-trip costs for a $10,000 trade (peer_rule.cost)
Splits: the two halves; size of the leader's move; US-listed twin (cheapest to trade) vs others; and the twins that
LOST over 2017-2026 vs those that won. If the effect lives only among winners, it is survivorship, not information.

    python -m research.supply_chain.peer_robust      -> results/peer_robust.json
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .peer_rule import cost

BASE = Path(__file__).parent
IN, OUT = BASE / "results" / "peer_trades.csv", BASE / "results" / "peer_robust.json"
K = (1, 3, 5, 10, 20)


def tday(e: pd.Series, dates: pd.Series) -> float:
    s = e.groupby(dates).mean()
    return float(s.mean() / s.std() * np.sqrt(len(s))) if len(s) > 2 and s.std() > 0 else float("nan")


def main() -> None:
    T = pd.read_csv(IN, parse_dates=["date"])
    T = T[T.up]
    T["half"] = np.where(T.date < "2022-01-01", "2017-2021", "2022-2026")
    T["cost"] = T.twin_t.map(lambda t: cost(t, 100.0, 10000))
    T["us_twin"] = ~T.twin_t.str.contains(r"\.")
    T["winner"] = T.whole > T.drop_duplicates("twin_t").whole.median()
    T["big"] = T.z > 3
    for k in K:
        T[f"x{k}"] = T[f"h{k}"] - np.where(T.half == "2017-2021", T[f"b{k}_2017-2021"], T[f"b{k}_2022-2026"])

    def block(x):
        out = {"trades": int(len(x))}
        for k in K:
            out[f"excess{k}"] = round(float(x[f"x{k}"].mean() * 100), 3)
            out[f"t{k}"] = round(tday(x[f"x{k}"], x.date), 2)
            out[f"net{k}"] = round(float((x[f"h{k}"] - x.cost).mean() * 100), 3)
        return out
    res = {}
    for name, cond in [("all", None), ("2017-2021", T.half == "2017-2021"), ("2022-2026", T.half == "2022-2026"),
                       ("leader move 2-3", ~T.big), ("leader move over 3", T.big),
                       ("US-listed twin", T.us_twin), ("twin outside US", ~T.us_twin),
                       ("twins that won 2017-2026", T.winner), ("twins that lost 2017-2026", ~T.winner)]:
        x = T if cond is None else T[cond]
        res[name] = block(x)
        for h in ("2017-2021", "2022-2026"):
            if name not in ("all", "2017-2021", "2022-2026"):
                res[f"{name} · {h}"] = block(x[x.half == h])
    res["by_direction"] = {d: block(g) for d, g in T.groupby("dir")}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    hdr = "group".ljust(40) + "".join(f"  ex{k:>2}  t{k:>2} " for k in K)
    print(hdr)
    for n, v in list(res.items()) + list(res["by_direction"].items()):
        if n == "by_direction":
            continue
        print(n[:40].ljust(40) + "".join(f" {v[f'excess{k}']:+6.2f} {v[f't{k}']:+5.1f}" for k in K), " n", v["trades"], " net5", v["net5"])


if __name__ == "__main__":
    main()
