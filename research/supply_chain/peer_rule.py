"""Backtest of an automatic order: "when X jumps, buy its twin at the twin's next open".

Leader moves more than 2 of its usual daily moves (company-specific, vs its home index) -> buy the same-segment twin
at the twin's next open (an opening-auction order), sell at that day's close, or hold 5 sessions.
Costs per side, for a trade of TRADE_USD: broker (Interactive Brokers list prices from fees_il.json), exchange taxes
(engine.js MARKET_COSTS), currency conversion, and an assumed bid-ask cost for large companies.
Honesty rules: the phenomenon was found on 2017-2026 as a whole, so the rule is judged on two halves separately
(2017-2021 and 2022-2026); a result that only holds in one half is not a result.

    python -m research.supply_chain.peer_rule
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import markets as MK
from .peer_leadlag import ORDER, universe

BASE = Path(__file__).parent
OUT = BASE / "results" / "peer_rule.json"
SPREAD = 0.0005                      # assumed half bid-ask cost per side for large companies
TAX = {"": (0, 0.0000206), "L": (0.005, 0), "PA": (0.004, 0), "MI": (0.002, 0), "HK": (0.001, 0.001), "TW": (0, 0.003),
       "TWO": (0, 0.003), "KS": (0, 0.002), "KQ": (0, 0.002), "SS": (0, 0.0005), "SZ": (0, 0.0005)}   # (buy, sell)
BROKER = {"": ("share", 0.005, 1.0), "T": ("pct", 0.0008, 0.6), "HK": ("pct", 0.0008, 2.3), "KS": ("pct", 0.0006, 3.0),
          "KQ": ("pct", 0.0006, 3.0)}   # (kind, rate, minimum in USD); others: 0.05% min ~3.3 USD (EUR 3)


def cost(ticker: str, price_usd: float, trade: float) -> float:
    """Round-trip cost as a fraction of the trade."""
    ex = MK.suffix(ticker)
    kind, rate, mn = BROKER.get(ex, ("pct", 0.0005, 3.3))
    com = max(mn, rate * trade / max(price_usd, 1e-9)) if kind == "share" else max(mn, rate * trade)
    buy, sell = TAX.get(ex, (0, 0))
    fx = 0 if ex == "" else 2 * max(0.00002 * trade, 2.0) / trade
    return 2 * com / trade + buy + sell + 2 * SPREAD + fx


def main() -> None:
    import yfinance as yf
    U = universe()
    bench = sorted({MK.benchmark(t) for t in U.ticker})
    raw = yf.download(sorted(set(U.ticker) | set(bench)), start="2016-01-01", auto_adjust=True, progress=False)
    O, C = raw["Open"], raw["Close"]
    info = {}
    for t in U.ticker:
        if t not in C or C[t].notna().sum() < 500:
            continue
        o, c = O[t], C[t]
        ok = o.notna() & c.notna()
        o, c = o[ok], c[ok]
        cb = C[MK.benchmark(t)].reindex(c.index).ffill()
        ab = (c.pct_change() - cb.pct_change())
        info[t] = {"o": o, "c": c, "z": ab / ab.rolling(250, min_periods=60).std().shift(), "close": MK.close_utc(t, c.index)}
    U = U[U.ticker.isin(info)]
    # baseline: buying the same twins at ANY open (no signal), same holding periods, same halves
    base = {}
    for t in U.ticker.unique():
        o, c = info[t]["o"], info[t]["c"]
        d1, d5 = c / o - 1, c.shift(-4) / o - 1
        for half, m in (("2017-2021", (c.index >= "2017-01-01") & (c.index < "2022-01-01")), ("2022-2026", c.index >= "2022-01-01")):
            base.setdefault(half, {"day": [], "hold5": []})
            base[half]["day"].append(d1[m].dropna()); base[half]["hold5"].append(d5[m].dropna())
    baseline = {h: {k: round(float(pd.concat(v).mean() * 100), 3) for k, v in d.items()} for h, d in base.items()}
    print("baseline (no signal, gross):", baseline)
    trades = []
    for seg, g in U.groupby("seg"):
        for a in g.itertuples():
            A = info[a.ticker]
            for b in g.itertuples():
                if a.ticker == b.ticker or (a.region, b.region) not in ORDER:
                    continue
                B = info[b.ticker]
                sig = A["z"][A["z"].abs() > 2].dropna()
                if sig.empty:
                    continue
                pos = B["close"].searchsorted(A["close"][A["z"].index.get_indexer(sig.index)], side="right")
                for (d, z), j in zip(sig.items(), pos):
                    if j + 20 >= len(B["c"]) or d < pd.Timestamp("2017-01-01"):
                        continue
                    o, c1, c5 = B["o"].iloc[j], B["c"].iloc[j], B["c"].iloc[j + 4]
                    extra = {f"h{k}": B["c"].iloc[j + k - 1] / o - 1 for k in (1, 3, 5, 10, 20)}
                    trades.append({"leader": a.name, "twin": b.name, "twin_t": b.ticker, "dir": f"{a.region}→{b.region}", "seg": seg,
                                   "date": B["c"].index[j], "up": z > 0, "z": z, "day": c1 / o - 1, "hold5": c5 / o - 1, **extra,
                                   "gap": o / B["c"].iloc[j - 1] - 1})
    T = pd.DataFrame(trades).sort_values("z", key=abs, ascending=False).drop_duplicates(["twin_t", "date", "up"])   # one trade per twin per day
    # per-twin baselines for every horizon, and each twin's whole-period result (to split winners from losers)
    bl = []
    for t in T.twin_t.unique():
        o, c = info[t]["o"], info[t]["c"]
        row = {"twin_t": t, "whole": float(c[c.index >= "2017-01-01"].iloc[-1] / c[c.index >= "2017-01-01"].iloc[0] - 1)}
        for k in (1, 3, 5, 10, 20):
            r = (c.shift(-(k - 1)) / o - 1)
            for half, m in (("2017-2021", (c.index >= "2017-01-01") & (c.index < "2022-01-01")), ("2022-2026", c.index >= "2022-01-01")):
                row[f"b{k}_{half}"] = float(r[m].mean())
        bl.append(row)
    BL = pd.DataFrame(bl)
    T.merge(BL, on="twin_t").to_csv(BASE / "results" / "peer_trades.csv", index=False)
    T["half"] = np.where(T.date < "2022-01-01", "2017-2021", "2022-2026")
    px_usd = {t: 100.0 for t in T.twin_t.unique()}                       # share price only matters for the US per-share fee
    res = {"assumptions": {"spread_per_side": SPREAD, "trade_usd": [3000, 10000]}, "baseline_gross_pct": baseline, "results": {}}
    for trade in (3000, 10000):
        T[f"cost{trade}"] = T.twin_t.map(lambda t: cost(t, px_usd[t], trade))
        for side, sub in (("buy after a jump", T[T.up]), ("sell or avoid after a drop", T[~T.up])):
            sgn = 1 if side.startswith("buy") else -1
            for h in ("day", "hold5"):
                for half, x in [("all", sub)] + list(sub.groupby("half")):
                    gross = sgn * x[h]
                    net = gross - x[f"cost{trade}"]
                    key = f"${trade} · {side} · {'open to close' if h == 'day' else 'open, hold 5 days'} · {half}"
                    res["results"][key] = {"trades": int(len(x)), "gross_mean_pct": round(float(gross.mean() * 100), 3),
                                           "net_mean_pct": round(float(net.mean() * 100), 3), "won_pct": round(float((net > 0).mean() * 100), 1),
                                           "t": round(float(net.mean() / net.std() * np.sqrt(len(net))), 2) if len(net) > 2 else None,
                                           "gap_paid_pct": round(float(sgn * x.gap.mean() * 100), 2)}
    # where it works best, net, buy side, open to close, $10k, by direction and by half
    best = {}
    for (d, half), x in T[T.up].groupby(["dir", "half"]):
        net = x.day - x.cost10000
        best[f"{d} · {half}"] = {"trades": int(len(x)), "net_mean_pct": round(float(net.mean() * 100), 3), "won_pct": round(float((net > 0).mean() * 100), 1)}
    res["by_direction_buy_day_10k"] = best
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for k, v in res["results"].items():
        if "$10000" in k:
            print(k, v)
    for k, v in best.items():
        print(k, v)


if __name__ == "__main__":
    main()
