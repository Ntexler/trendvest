"""How optimistic are analysts' 12-month price targets, measured on our own companies.

For every price target an analyst published (Yahoo upgrades/downgrades history, US listings only):
  implied   = target / price that day - 1           what the analyst expected over 12 months
  realized  = price 12 months later / price that day - 1
  gap       = implied - realized                      positive = the analyst was too optimistic
  reached   = did the price touch the target at any close within the 12 months
Targets are put on today's share basis (stock splits); prices are split-adjusted closes without dividends.
Only targets whose 12 months have fully passed are scored.

    python -m research.supply_chain.analysts    -> results/analyst_accuracy.json
"""

from __future__ import annotations

import json
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).parent
OUT = BASE / "results" / "analyst_accuracy.json"
START = "2015-01-01"


def us_tickers() -> dict[str, str]:
    out = {}
    for d in sorted((BASE / "data").iterdir()):
        if (d / "companies.csv").exists():
            c = pd.read_csv(d / "companies.csv", comment="#")
            for r in c.itertuples():
                if "." not in r.ticker and r.tier != "control":
                    out[r.ticker] = r.name
    return out


def score(ticker: str, close: pd.Series, splits: pd.Series, ud: pd.DataFrame) -> pd.DataFrame:
    ud = ud[(ud["currentPriceTarget"] > 0)].copy()
    ud.index = pd.to_datetime(ud.index).tz_localize(None).normalize()
    ud = ud[ud.index >= START]
    # a target set before a split is in old shares: divide by every split that came after it
    for d, ratio in splits.items():
        d = pd.Timestamp(d).tz_localize(None)
        ud.loc[ud.index < d, "currentPriceTarget"] /= ratio
    rows = []
    last_ok = close.index[-1] - pd.Timedelta(days=365)
    for d, r in ud.iterrows():
        if d > last_ok:
            continue
        i = close.index.searchsorted(d)
        if i >= len(close):
            continue
        p0 = close.iloc[i]
        j = close.index.searchsorted(close.index[i] + pd.Timedelta(days=365))
        if j >= len(close):
            continue
        window = close.iloc[i:j + 1]
        t = r["currentPriceTarget"]
        implied, realized = t / p0 - 1, close.iloc[j] / p0 - 1
        rows.append({"ticker": ticker, "date": d, "firm": r["Firm"], "implied": implied, "realized": realized,
                     "reached": bool((window >= t).any()) if t >= p0 else bool((window <= t).any())})
    return pd.DataFrame(rows)


def summary(d: pd.DataFrame) -> dict:
    gap = (d.implied - d.realized) * 100
    up = d[d.implied > 0]
    return {"targets": int(len(d)), "companies": int(d.ticker.nunique()),
            "implied_median": round(float(d.implied.median() * 100), 1), "realized_median": round(float(d.realized.median() * 100), 1),
            "gap_median": round(float(gap.median()), 1), "gap_mean": round(float(gap.mean()), 1),
            "too_high_pct": round(float((gap > 0).mean() * 100), 1),
            "reached_pct": round(float(up.reached.mean() * 100), 1) if len(up) else None,
            "abs_error_median": round(float((d.implied - d.realized).abs().median() * 100), 1)}


def main() -> None:
    import yfinance as yf
    tick = us_tickers()
    px = yf.download(list(tick), start="2014-06-01", auto_adjust=False, progress=False)["Close"]
    frames, failed = [], []
    for t in tick:
        try:
            tk = yf.Ticker(t)
            ud = None
            for attempt in range(4):                     # Yahoo rate-limits bursts: wait and retry
                try:
                    ud = tk.upgrades_downgrades
                    break
                except Exception:  # noqa: BLE001
                    time.sleep(8 * (attempt + 1))
            if ud is None or ud.empty or t not in px:
                failed.append(t)
                continue
            frames.append(score(t, px[t].dropna(), tk.splits, ud))
        except Exception:  # noqa: BLE001
            failed.append(t)
        time.sleep(1.5)
    d = pd.concat([f for f in frames if len(f)])
    d["year"] = d.date.dt.year
    by_co = {t: summary(g) for t, g in d.groupby("ticker") if len(g) >= 20}
    out = {"computed": str(date.today()), "method": __doc__.split("\n\n")[1], "all": summary(d),
           "by_year": {int(y): summary(g) for y, g in d.groupby("year")},
           "by_size_of_promise": {k: summary(g) for k, g in d.groupby(pd.cut(d.implied * 100, [-100, 0, 15, 30, 60, 1000],
                                  labels=["below today", "0-15%", "15-30%", "30-60%", "60%+"]), observed=True)},
           "by_company": by_co, "names": tick, "failed": failed}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    a = out["all"]
    print(f"{a['targets']} targets on {a['companies']} US companies. Median promise {a['implied_median']}%, "
          f"median result {a['realized_median']}%, median gap {a['gap_median']} points; too high {a['too_high_pct']}%; "
          f"reached {a['reached_pct']}%. failed: {len(failed)}")
    for k, v in out["by_size_of_promise"].items():
        print(f"  promise {k:12s} n={v['targets']:6d} realized med {v['realized_median']:6.1f}%  gap med {v['gap_median']:6.1f}  reached {v['reached_pct']}")
    if "MU" in by_co:
        print("MU:", by_co["MU"])


if __name__ == "__main__":
    main()
