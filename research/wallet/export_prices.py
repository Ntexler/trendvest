"""Daily prices for the virtual wallet: real closes (not adjusted), dividends, and the shekel rate of every currency.

The wallet must pay dividends and charge tax on them, so prices here are NOT dividend-adjusted.
Output (served with the site): map/site/data/wallet_px.json

    python -m research.wallet.export_prices            # last 2 years, every company in every market
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1] / "supply_chain"
OUT = ROOT / "map" / "site" / "data" / "wallet_px.json"
MINOR = {"ILA": ("ILS", 100), "GBp": ("GBP", 100), "GBX": ("GBP", 100), "ZAc": ("ZAR", 100)}


def companies() -> dict[str, dict]:
    out = {}
    for d in sorted((ROOT / "data").iterdir()):
        if not (d / "companies.csv").exists():
            continue
        c = pd.read_csv(d / "companies.csv", comment="#")
        prof = json.loads((d / "profiles.json").read_text()) if (d / "profiles.json").exists() else {}
        for r in c.itertuples():
            if r.tier == "control" or r.ticker in out:
                continue
            cur = (prof.get(r.id, {}).get("info") or {}).get("currency")
            out[r.ticker] = {"name": r.name, "cur": cur, "markets": [d.name]}
        for r in c.itertuples():
            if r.ticker in out and d.name not in out[r.ticker]["markets"]:
                out[r.ticker]["markets"].append(d.name)
    return out


def main(years: int = 2) -> None:
    import yfinance as yf
    cos = companies()
    start = date.today() - timedelta(days=365 * years + 10)
    tick = sorted(cos)
    raw = yf.download(tick, start=str(start), auto_adjust=False, actions=True, progress=False, group_by="column", threads=True)
    close, divs = raw["Close"], raw["Dividends"]
    days = close.index[close.notna().sum(axis=1) > len(tick) * 0.2]
    close = close.loc[days]
    curs = sorted({MINOR.get(c["cur"], (c["cur"], 1))[0] for c in cos.values() if c["cur"]} - {"ILS"})
    # every rate through the dollar: Yahoo has USD<x> for almost every currency, <x>ILS only for some
    pairs = ["USDILS=X"] + [f"USD{c}=X" for c in curs if c != "USD"]
    fxraw = yf.download(pairs, start=str(start), progress=False)["Close"]
    fx = fxraw.reindex(days).ffill().bfill()
    out = {"dates": [str(d.date()) for d in days], "fx": {}, "co": {}}
    for c in curs:
        s = fx["USDILS=X"] if c == "USD" else fx["USDILS=X"] / fx.get(f"USD{c}=X", pd.Series(dtype=float))
        if s is not None and s.notna().all():
            out["fx"][c] = [round(float(v), 6) for v in s]
    missing = []
    for t in tick:
        s = close[t] if t in close else None
        if s is None or s.notna().sum() < 50:
            missing.append(t)
            continue
        cur, div = MINOR.get(cos[t]["cur"], (cos[t]["cur"], 1)) if cos[t]["cur"] else ("USD", 1)
        if cur != "ILS" and cur not in out["fx"]:
            missing.append(t)
            continue
        dv = divs[t].loc[pd.Timestamp(start):] if t in divs else pd.Series(dtype=float)
        out["co"][t] = {"name": cos[t]["name"], "cur": cur, "unit": div, "markets": cos[t]["markets"],
                        "px": [None if pd.isna(v) else round(float(v) / div, 4) for v in s.ffill()],
                        "div": [[str(i.date()), round(float(v) / div, 4)] for i, v in dv[dv > 0].items()]}
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"{len(out['co'])} companies, {len(days)} days, {len(out['fx'])} currencies, "
          f"{OUT.stat().st_size // 1024} KB; missing: {missing}")


if __name__ == "__main__":
    main()
