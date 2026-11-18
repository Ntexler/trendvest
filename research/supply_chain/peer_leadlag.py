"""Same square, different market: does a move in one company predict its twin's move on another exchange?

Peers = companies with the same segment (e.g. oil majors: ExxonMobil, Chevron, Shell, TotalEnergies, Equinor) listed in
different regions. Because markets close at different hours, a move in New York happens while Tokyo and Frankfurt are
shut; the question is what the twin does when its own market opens next.

For a leader A and a follower B (B's market opens after A's market closes):
  A's move     A's close-to-close return on its day, minus A's home index (the company-specific part)
  B's gap      B's next open vs. B's previous close, minus the same for B's home index   (hard for a private investor to catch)
  B's day      B's next close vs. B's next open, minus the same for B's index             (can be caught: buy/sell at the open)
Controls: the same B against a leader from the same region but a DIFFERENT segment (a "stranger").
Event view: A moves more than 2 of its usual daily moves -> how often B goes the same way.

    python -m research.supply_chain.peer_leadlag      -> results/peer_leadlag.json
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import markets as MK

BASE = Path(__file__).parent
OUT = BASE / "results" / "peer_leadlag.json"
REGION = lambda ex: "americas" if ex in ("", "TO", "SA", "SN") else "asia" if ex in ("T", "KS", "KQ", "TW", "TWO", "HK", "SS", "SZ", "NS", "JK", "AX") else "israel" if ex == "TA" else "europe"  # noqa: E731
# A's information reaches B's NEXT open in these directions (leader closes before follower opens)
ORDER = {("americas", "asia"), ("americas", "europe"), ("europe", "asia"), ("asia", "europe"), ("asia", "americas")}


def universe() -> pd.DataFrame:
    rows = []
    for d in sorted((BASE / "data").iterdir()):
        if (d / "companies.csv").exists():
            c = pd.read_csv(d / "companies.csv", comment="#")
            c["market"] = d.name
            rows.append(c)
    c = pd.concat(rows)
    c = c[c.tier != "control"].drop_duplicates("ticker")
    c["ex"] = c.ticker.map(lambda t: MK.suffix(t))
    c["region"] = c.ex.map(REGION)
    c["seg"] = c.market + ":" + c.segment
    multi = c.groupby("seg").region.nunique()
    return c[c.seg.isin(multi[multi >= 2].index) & (c.region != "israel")].reset_index(drop=True)


def main() -> None:
    import yfinance as yf
    U = universe()
    bench = sorted({MK.benchmark(t) for t in U.ticker})
    raw = yf.download(sorted(set(U.ticker) | set(bench)), start="2016-01-01", auto_adjust=True, progress=False)
    O, C = raw["Open"], raw["Close"]
    # per stock: abnormal close-to-close, gap and intraday, each minus its home index
    def parts(t):
        b = MK.benchmark(t)
        o, c, ob, cb = O[t], C[t], O[b], C[b]
        ok = c.notna() & o.notna()
        o, c = o[ok], c[ok]
        ob, cb = ob.reindex(c.index).ffill(), cb.reindex(c.index).ffill()
        cc = c.pct_change() - cb.pct_change()
        gap = (o / c.shift() - 1) - (ob / cb.shift() - 1)
        day = (c / o - 1) - (cb / ob - 1)
        close_utc = MK.close_utc(t, c.index)
        return pd.DataFrame({"cc": cc, "gap": gap, "day": day, "close": close_utc}, index=c.index).dropna()
    P = {t: parts(t) for t in U.ticker if t in C and C[t].notna().sum() > 500}
    U = U[U.ticker.isin(P)]

    def pair_rows(a, b):
        A, B = P[a], P[b]
        sd = A.cc.rolling(250, min_periods=60).std().shift()
        # each B session: the latest A session that closed before B's previous session ended + a margin for B's open.
        # Rule by region pairs (ORDER) guarantees A closes before B opens on the next B session.
        idx = B["close"].searchsorted(A["close"].to_numpy(), side="right")   # first B close after A close = B session that follows
        ok = idx < len(B)
        m = pd.DataFrame({"a": A.cc.to_numpy()[ok], "z": (A.cc / sd).to_numpy()[ok],
                          "gap": B.gap.to_numpy()[idx[ok]], "day": B.day.to_numpy()[idx[ok]], "cc": B.cc.to_numpy()[idx[ok]],
                          "date": B.index[idx[ok]]})
        return m[(m.date >= "2017-01-01")].dropna()

    res = {"segments": int(U.seg.nunique()), "companies": int(len(U)), "pairs": {}, "pooled": {}, "by_segment": {}}
    pooled, strangers = [], []
    for seg, g in U.groupby("seg"):
        seg_rows = []
        for a in g.itertuples():
            for b in g.itertuples():
                if a.ticker == b.ticker or (a.region, b.region) not in ORDER:
                    continue
                m = pair_rows(a.ticker, b.ticker)
                if len(m) < 300:
                    continue
                m["pair"] = f"{a.name} → {b.name}"
                m["dir"] = f"{a.region}→{b.region}"
                seg_rows.append(m)
                # stranger: a leader from A's region but another segment, matched by list position
                pool = U[(U.region == a.region) & (U.seg != seg)]
                if len(pool):
                    s = pool.iloc[hash(a.ticker + b.ticker) % len(pool)]
                    ms = pair_rows(s.ticker, b.ticker)
                    ms["dir"] = m["dir"].iloc[0]
                    strangers.append(ms)
        if seg_rows:
            S = pd.concat(seg_rows)
            pooled.append(S)
            big = S[S.z.abs() > 2]
            res["by_segment"][seg] = {"pairs": int(S.pair.nunique()), "obs": int(len(S)),
                                      "corr_gap": round(float(S.a.corr(S.gap)), 3), "corr_day": round(float(S.a.corr(S.day)), 3),
                                      "big_moves": int(len(big)),
                                      "same_dir_gap": round(float((np.sign(big.a) == np.sign(big.gap)).mean() * 100), 1) if len(big) else None,
                                      "same_dir_day": round(float((np.sign(big.a) == np.sign(big.day)).mean() * 100), 1) if len(big) else None,
                                      "names": sorted(set(g.name))}
    D, X = pd.concat(pooled), pd.concat(strangers)

    def stats(M, label):
        big = M[M.z.abs() > 2]
        follow = lambda col: float((big[col] * np.sign(big.a)).mean() * 100)  # noqa: E731
        return {"label": label, "obs": int(len(M)), "big_moves": int(len(big)),
                "corr_gap": round(float(M.a.corr(M.gap)), 3), "corr_day": round(float(M.a.corr(M.day)), 3),
                "same_dir_gap": round(float((np.sign(big.a) == np.sign(big.gap)).mean() * 100), 1),
                "same_dir_day": round(float((np.sign(big.a) == np.sign(big.day)).mean() * 100), 1),
                "follow_gap_pct": round(follow("gap"), 2), "follow_day_pct": round(follow("day"), 2)}
    res["pooled"]["peers"] = stats(D, "same square")
    res["pooled"]["strangers"] = stats(X, "stranger from the same region")
    res["by_direction"] = {d: stats(g, d) for d, g in D.groupby("dir")}
    res["by_year_peers"] = {int(y): stats(g, str(y)) for y, g in D.groupby(D.date.dt.year)}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for k, v in res["pooled"].items():
        print(k, v)
    for k, v in res["by_direction"].items():
        print(k, v)
    top = sorted(res["by_segment"].items(), key=lambda kv: -abs(kv[1]["corr_gap"]))[:10]
    for k, v in top:
        print(k, {x: v[x] for x in ("pairs", "big_moves", "corr_gap", "corr_day", "same_dir_gap", "same_dir_day")}, v["names"][:5])
    for y, v in res["by_year_peers"].items():
        print(y, v["same_dir_gap"], v["same_dir_day"], v["follow_day_pct"])


if __name__ == "__main__":
    main()
