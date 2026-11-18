"""Run the News Impact study.

    pip install -r research/news_impact/requirements.txt
    python -m research.news_impact.run                 # default universe, last 2 years
    python -m research.news_impact.run --start 2023-01-01 --only NVDA TSLA

Outputs go to research/news_impact/results/:
    profiles.csv     one row per ticker: the News Impact Profile
    events.csv       every detected news shock with its reaction metrics
    response.csv     average abnormal volatility on days -5..+10 around a shock
    lead_lag.csv     corr(news shock today, abnormal volatility at lag k)
    prediction.json  out-of-sample test: does news help predict tomorrow's big move?
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from . import metrics as M
from .data import load_news, load_prices

RESULTS = Path(__file__).parent / "results"

# ticker -> (GDELT query, market benchmark)
UNIVERSE = {
    # US
    "NVDA": ("nvidia", "SPY"),
    "TSLA": ("tesla", "SPY"),
    "PLTR": ("palantir", "SPY"),
    "AMD": ('("advanced micro devices" OR "Lisa Su")', "SPY"),
    "META": ('("Meta Platforms" OR Zuckerberg)', "SPY"),
    "BA": ("boeing", "SPY"),
    # Israel (Tel Aviv listings, benchmark TA-125)
    "TEVA.TA": ('("Teva Pharmaceutical" OR "Teva Pharma")', "^TA125.TA"),
    "ESLT.TA": ('"Elbit Systems"', "^TA125.TA"),
    "LUMI.TA": ('("Bank Leumi" OR "Leumi")', "^TA125.TA"),
    "NICE.TA": ('"NICE Ltd"', "^TA125.TA"),
}


def response_curve(df: pd.DataFrame, events: list[pd.Timestamp]) -> pd.DataFrame:
    paths = []
    for d in events:
        i = df.index.get_loc(d)
        w = df.iloc[i - M.PRE: i + M.POST + 1]
        paths.append((w["ar"].abs() / df["sigma"].iloc[i]).to_numpy())
    arr = np.array(paths)
    return pd.DataFrame({"day": range(-M.PRE, M.POST + 1),
                         "mean_av": arr.mean(0), "median_av": np.median(arr, 0)})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2024-11-01")
    ap.add_argument("--end", default="2026-11-01")
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    # price history starts earlier so beta / sigma windows are warm on day one
    pstart = date(start.year - 1, start.month, 1)

    universe = {k: v for k, v in UNIVERSE.items() if not args.only or k in args.only}
    benches = sorted({b for _, b in universe.values()})
    prices = load_prices(list(universe) + benches, pstart, end)

    RESULTS.mkdir(exist_ok=True)
    rows, evs, lls, curves, frames = [], [], [], [], {}
    for t, (query, bench) in universe.items():
        print(f"{t}: loading news for {query} ...")
        news = load_news(query, start, end)
        if news.empty or "articles" not in news:
            print(f"  ! no news for {t}, skipped")
            continue
        df = M.build_daily_frame(prices["Close"][t], prices["Close"][bench],
                                 prices["Volume"][t], news)
        df = df[df.index >= pd.Timestamp(start)]
        frames[t] = df
        row, ev, ll = M.profile(t, df)
        rows.append(row)
        if len(ev):
            evs.append(ev)
            c = response_curve(df, list(ev["date"]))
            c.insert(0, "ticker", t)
            curves.append(c)
        lls.append(ll.rename(t))
        print(f"  {row['events']} shocks, impact x{row.get('impact_x', float('nan')):.2f}, "
              f"peak day {row.get('peak_day_med')}, settle day {row.get('settle_day_med')}")

    prof = pd.DataFrame(rows).round(3)
    prof.to_csv(RESULTS / "profiles.csv", index=False)
    if evs:
        pd.concat(evs).round(3).to_csv(RESULTS / "events.csv", index=False)
        allc = pd.concat(curves)
        allc.round(3).to_csv(RESULTS / "response.csv", index=False)
    pd.concat(lls, axis=1).round(3).to_csv(RESULTS / "lead_lag.csv", index_label="lag")
    pred = M.prediction_test(frames)
    (RESULTS / "prediction.json").write_text(json.dumps(pred, indent=2, default=float))

    pd.set_option("display.width", 200)
    print("\n=== News Impact Profiles ===")
    print(prof.to_string(index=False))
    if evs:
        print("\n=== Average abnormal volatility around a news shock (all tickers) ===")
        print(allc.groupby("day")[["mean_av", "median_av"]].mean().round(2).T.to_string())
    print("\n=== Prediction test (out of sample) ===")
    print(json.dumps(pred, indent=2, default=float))


if __name__ == "__main__":
    main()
