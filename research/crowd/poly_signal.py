"""Polymarket "will X beat its EPS estimate?" markets: are they right, and do they tell us anything about the stock?

For each market: p = the last traded price of "Yes" at least 18 hours before the market's end date (before the report).
  calibration   how often "Yes" won, by p bucket; Brier score vs. always guessing the average
  stock         the report reaction = close the day after the end date / close the day before it, minus SPY
  tradable?     buy the stock the day before the report when p is high vs. low: reaction by p bucket

    python -m research.crowd.poly_signal      -> data/poly_signal.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

D = Path(__file__).parent / "data"
NAMES = {"broadcom": "AVGO", "nvidia": "NVDA", "apple": "AAPL", "microsoft": "MSFT", "tesla": "TSLA", "amazon": "AMZN",
         "meta": "META", "alphabet": "GOOGL", "google": "GOOGL", "netflix": "NFLX", "oracle": "ORCL", "micron": "MU", "palantir": "PLTR",
         "coinbase": "COIN", "amd": "AMD", "intel": "INTC", "salesforce": "CRM", "adobe": "ADBE", "costco": "COST", "walmart": "WMT"}


def ticker(q: str):
    m = re.search(r"\(([A-Z]{1,5}(?:\.[A-Z])?)\)", q)
    if m:
        return m.group(1).replace(".", "-")
    for k, v in NAMES.items():
        if re.search(rf"\b{k}\b", q.lower()):
            return v
    return None


def main() -> None:
    import yfinance as yf
    M = json.loads((D / "poly_earnings.json").read_text())
    rows = []
    for m in M:
        t = ticker(m["question"] or "")
        if not t or not m["history"] or not m["end"]:
            continue
        end = pd.Timestamp(m["end"])
        h = [x for x in m["history"] if pd.Timestamp(x["t"], unit="s", tz="UTC") <= end - pd.Timedelta(hours=18)]
        if not h:
            continue
        rows.append({"ticker": t, "end": end.tz_localize(None).normalize(), "p": float(h[-1]["p"]), "won": bool(m["yes_won"]),
                     "volume": float(m["volume"] or 0)})
    P = pd.DataFrame(rows)
    px = yf.download(sorted(P.ticker.unique()) + ["SPY"], start="2024-06-01", auto_adjust=True, progress=False)["Close"]
    idx = px.index

    def react(r):
        if r.ticker not in px:
            return np.nan
        i = idx.searchsorted(r.end)
        if i < 1 or i + 1 >= len(idx):
            return np.nan
        a, s = px[r.ticker], px["SPY"]
        return (a.iloc[i + 1] / a.iloc[i - 1] - 1) - (s.iloc[i + 1] / s.iloc[i - 1] - 1)
    P["reaction"] = P.apply(react, axis=1)
    P = P.dropna(subset=["reaction"])
    base = P.won.mean()
    P["bucket"] = pd.cut(P.p, [0, 0.5, 0.7, 0.85, 0.95, 1.0001], labels=["<50%", "50-70%", "70-85%", "85-95%", "95%+"])
    res = {"markets": int(len(P)), "companies": int(P.ticker.nunique()), "period": [str(P.end.min().date()), str(P.end.max().date())],
           "yes_rate": round(float(base * 100), 1),
           "brier_market": round(float(((P.p - P.won) ** 2).mean()), 4), "brier_always_average": round(float(((base - P.won) ** 2).mean()), 4),
           "by_bucket": {str(b): {"n": int(len(x)), "avg_price": round(float(x.p.mean() * 100), 1), "beat_rate": round(float(x.won.mean() * 100), 1),
                                  "reaction_mean": round(float(x.reaction.mean() * 100), 2)} for b, x in P.groupby("bucket", observed=True)},
           "reaction_if_beat": round(float(P[P.won].reaction.mean() * 100), 2), "reaction_if_miss": round(float(P[~P.won].reaction.mean() * 100), 2),
           "corr_price_vs_reaction": round(float(np.corrcoef(P.p, P.reaction)[0, 1]), 3),
           "corr_surprise_vs_reaction": round(float(np.corrcoef(P.won.astype(float) - P.p, P.reaction)[0, 1]), 3)}
    (D / "poly_signal.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
