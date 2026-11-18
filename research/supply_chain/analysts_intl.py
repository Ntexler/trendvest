"""Analyst accuracy and target changes outside the US, through the companies' New York listings.

Yahoo keeps analyst history only for New York listings (home listings such as 2330.TW, SAP.DE or NICE.TA return
nothing, checked 2026-11-13). Many Israeli, Chinese, European and Asian companies trade in New York too, and the
analysts covering those listings are measured here with the same method as analysts.py and analyst_changes.py:
  accuracy: 12-month target vs. the price 12 months later (split-adjusted, no dividends)
  changes:  the stock's move vs. SPY on the day a target is raised or cut, and 5/20/60 trading days after
Note: covers mostly US brokers' analysts; local analysts at home are not in this data.

    python -m research.supply_chain.analysts_intl     -> results/analyst_intl.json
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .analysts import score, summary

BASE = Path(__file__).parent
OUT = BASE / "results" / "analyst_intl.json"
REGIONS = {
    "israel": ["TEVA", "NICE", "CHKP", "CYBR", "MNDY", "WIX", "TSEM", "ICL", "ESLT", "NVMI", "CAMT", "GLBE", "SEDG", "FVRR", "INMD"],
    "china": ["BABA", "JD", "BIDU", "PDD", "NIO", "LI", "XPEV", "BILI", "NTES", "TME", "YUMC", "ZTO", "BEKE", "TCOM"],
    "europe": ["ASML", "SAP", "NVO", "SHEL", "AZN", "UL", "BP", "TTE", "SNY", "GSK", "DEO", "NVS", "ING", "BCS"],
    "asia_other": ["TSM", "SONY", "INFY", "HDB", "IBN", "TM", "MUFG", "HMC", "SMFG", "WIT", "KB"],
}
H = [1, 5, 20, 60]


def tstat(df, col):
    s = df.groupby("d0")[col].mean().dropna()
    return float(s.mean() / s.std() * np.sqrt(len(s))) if len(s) > 2 and s.std() > 0 else float("nan")


def changes(T: pd.DataFrame, px: pd.DataFrame) -> pd.DataFrame:
    T = T.sort_values("date").copy()
    T["firm"] = T["firm"].fillna("?")
    T["prev"] = T.groupby(["ticker", "firm"])["target"].shift()
    T["prev_date"] = T.groupby(["ticker", "firm"])["date"].shift()
    T["chg"] = np.where((T.date - T.prev_date).dt.days <= 400, T.target / T.prev - 1, np.nan)
    T["kind"] = np.select([T.chg > 0.02, T.chg < -0.02, T.chg.isna()], ["raise", "cut", "new"], "same")
    T = T[T.kind != "same"]
    near = T.groupby("ticker")["date"].transform(lambda s: [((s - x).abs().dt.days <= 2).sum() - 1 for x in s])
    T["wave"] = near > 0
    idx, s = px.index, px["SPY"].to_numpy()
    rows = []
    for r in T.itertuples():
        i = idx.searchsorted(r.date.normalize())
        if r.ticker not in px or i < 1 or i >= len(idx):
            continue
        p = px[r.ticker].to_numpy()
        if np.isnan(p[i]) or np.isnan(p[i - 1]):
            continue
        row = {"ticker": r.ticker, "region": r.region, "d0": idx[i], "kind": r.kind, "wave": r.wave,
               "day0": (p[i] / p[i - 1] - 1) - (s[i] / s[i - 1] - 1)}
        for h in H:
            row[f"a{h}"] = (p[i + h] / p[i] - 1) - (s[i + h] / s[i] - 1) if i + h < len(idx) and not np.isnan(p[i + h]) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def cblock(x):
    out = {"n": int(len(x)), "day0_mean": round(float(x.day0.mean() * 100), 2), "day0_t": round(tstat(x, "day0"), 1)}
    for h in (5, 20, 60):
        out[f"after{h}_mean"] = round(float(x[f"a{h}"].mean() * 100), 2)
        out[f"after{h}_t"] = round(tstat(x, f"a{h}"), 1)
    return out


def main() -> None:
    import yfinance as yf
    region = {t: r for r, ts in REGIONS.items() for t in ts}
    px = yf.download(sorted(region) + ["SPY"], start="2014-06-01", auto_adjust=False, progress=False)["Close"]
    frames, failed = [], []
    for t in region:
        try:
            tk = yf.Ticker(t)
            ud = tk.upgrades_downgrades
            if ud is None or ud.empty or t not in px:
                failed.append(t)
                continue
            f = score(t, px[t].dropna(), tk.splits, ud)
            f["region"] = region[t]
            frames.append(f)
        except Exception:  # noqa: BLE001
            failed.append(t)
        time.sleep(2)
    A = pd.concat([f for f in frames if len(f)])
    A.to_csv(BASE / "results" / "analyst_targets_intl.csv", index=False)
    S = A.dropna(subset=["realized"])
    C = changes(A, px)
    res = {"failed": failed, "accuracy": {"all": summary(S), **{r: summary(g) for r, g in S.groupby("region")}},
           "promise_60plus": {r: summary(g[g.implied > 0.6]) for r, g in S.groupby("region") if (g.implied > 0.6).sum() >= 20},
           "changes": {}}
    for r, g in [("all", C)] + list(C.groupby("region")):
        for k in ("raise", "cut"):
            x = g[(g.kind == k) & ~g.wave]
            if len(x) >= 30:
                res["changes"][f"{r} · {k} alone"] = cblock(x)
    us = json.loads((BASE / "results" / "analyst_accuracy.json").read_text())["all"]
    res["us_for_comparison"] = us
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    print("failed", failed)
    for k, v in res["accuracy"].items():
        print("ACC", k.ljust(12), v)
    print("US ", us)
    for k, v in res["promise_60plus"].items():
        print("60+", k.ljust(12), v)
    for k, v in res["changes"].items():
        print("CHG", k.ljust(26), v)


if __name__ == "__main__":
    main()
