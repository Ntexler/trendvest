"""Stage 1: a large library of company-level shocks, and how they spread to neighbours.

Disasters are rare (10 in our catalogue). Company shocks are not:
  earnings  the first session after an earnings announcement, when the stock's own
            abnormal move is at least EARN_Z sigmas
  move      any other day with an abnormal move of at least MOVE_Z sigmas

"Abnormal" = the stock's return minus what its local market index explains, in units of its
own normal daily noise, minus the median such move across the chain that day (so a
sector-wide jump is not counted as a company shock).

For each shock at company X we measure the neighbours over the next 0/1/3/5 sessions
(aligned per exchange): customers that depend on X, and suppliers for whom X is >=10% of
revenue. The response is "signed": positive = moved the same way as X.

Placebo (borrowed from TWSE-KG): for every linked neighbour we also measure a random
company from the SAME stage that is NOT linked to X. If linked neighbours do not respond
more than same-stage strangers, the map adds nothing beyond "they are in the same sector".

Rules were fixed before the first run: EARN_Z=2, MOVE_Z=3, cooldown 5 sessions, horizons 0/1/3/5.

    python -m research.supply_chain.shocks      -> data/earnings.json, results/shocks*.csv/json
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import graph as G
from . import markets as MK
from .run import all_prices

HERE = Path(__file__).parent
EARN_Z, MOVE_Z, COOLDOWN, HORIZONS = 2.0, 3.0, 5, (0, 1, 3, 5)


def load_earnings(companies: pd.DataFrame, refresh: bool = False) -> dict[str, list[str]]:
    """Earnings announcement timestamps (UTC ISO) per company id, cached."""
    path = HERE / "data" / "earnings.json"
    data = json.loads(path.read_text()) if path.exists() and not refresh else {}
    import yfinance as yf
    for cid, c in companies.iterrows():
        if cid in data:
            continue
        try:
            e = yf.Ticker(c["ticker"]).get_earnings_dates(limit=60)
            ts = [t.tz_convert("UTC").isoformat() for t in e.index if t < pd.Timestamp.now(tz=t.tz)]
            data[cid] = sorted(ts)
        except Exception:  # noqa: BLE001
            data[cid] = []
        path.write_text(json.dumps(data))
        time.sleep(0.4)
    return data


def abnormal_z(prices: pd.DataFrame, companies: pd.DataFrame) -> dict[str, pd.Series]:
    """Daily abnormal move in sigma units per company (no look-ahead: beta and sigma use past days only)."""
    z = {}
    for cid, c in companies.iterrows():
        t, b = c["ticker"], MK.benchmark(c["ticker"])
        df = pd.DataFrame({"p": prices[t], "m": prices[b]}).dropna()
        r, rm = np.log(df["p"]).diff(), np.log(df["m"]).diff()
        beta = (r.rolling(250, min_periods=120).cov(rm) / rm.rolling(250, min_periods=120).var()).shift(1)
        ar = r - beta * rm
        sigma = ar.rolling(120, min_periods=60).std().shift(1)
        z[cid] = (ar / sigma).dropna()
    wide = pd.DataFrame(z)
    med = wide.median(axis=1)                 # the chain-wide move of the day
    return {cid: (wide[cid] - med).dropna() for cid in wide}


def find_shocks(z: dict[str, pd.Series], companies: pd.DataFrame, earnings: dict) -> pd.DataFrame:
    rows = []
    for cid, s in z.items():
        ticker = companies.loc[cid, "ticker"]
        dates = s.index
        earn_pos = set()
        for ts in earnings.get(cid, []):
            p = MK.day0_position(ticker, dates, pd.Timestamp(ts))
            if p is not None:
                earn_pos.add(p)
        last = -99
        for i, v in enumerate(s.to_numpy()):
            near_earn = any(abs(i - p) <= 1 for p in earn_pos)
            kind = "earnings" if i in earn_pos and abs(v) >= EARN_Z else "move" if not near_earn and abs(v) >= MOVE_Z else None
            if kind and i - last > COOLDOWN:
                rows.append({"company": cid, "date": dates[i], "kind": kind, "z": float(v),
                             "close_utc": MK.close_utc(ticker, dates[i:i + 1])[0]})
                last = i
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def response(z: pd.Series, ticker: str, after: pd.Timestamp, earn_pos: set[int]) -> dict | None:
    """Neighbour's abnormal move from its first close at or after ``after``; None if its own earnings interfere."""
    closes = MK.close_utc(ticker, z.index)
    j = int(closes.searchsorted(after, side="left"))
    if j + max(HORIZONS) >= len(z) or j < 1:
        return None
    if any(j - 1 <= p <= j + max(HORIZONS) for p in earn_pos):
        return None
    c = np.cumsum(z.to_numpy()[j:j + max(HORIZONS) + 1])
    return {f"d{h}": c[h] / np.sqrt(h + 1) for h in HORIZONS}


def neighbours(x: str, edges: pd.DataFrame) -> list[tuple[str, str]]:
    down, up = G.material_only(edges)
    return [(c, "customer") for c in down.loc[down.supplier == x, "customer"]] + \
           [(s, "supplier") for s in up.loc[up.customer == x, "supplier"]]


def earn_positions(z, companies, earnings):
    out = {}
    for cid, s in z.items():
        t = companies.loc[cid, "ticker"]
        out[cid] = {p for ts in earnings.get(cid, []) if (p := MK.day0_position(t, s.index, pd.Timestamp(ts))) is not None}
    return out


def study(seed: int = 11):
    companies = G.load_companies()
    chain = companies[companies["tier"] != "control"]
    prices = all_prices(companies)
    earnings = load_earnings(chain)
    z = abnormal_z(prices, chain)
    shocks = find_shocks(z, chain, earnings)
    epos = earn_positions(z, chain, earnings)
    all_edges = G.load_edges()
    linked_any = {x: set(all_edges.loc[all_edges.supplier == x, "customer"]) | set(all_edges.loc[all_edges.customer == x, "supplier"])
                  for x in chain.index}
    rng = np.random.default_rng(seed)
    by_year: dict[int, pd.DataFrame] = {}
    rows = []
    for ev_id, s in shocks.iterrows():
        yr = s["date"].year
        if yr not in by_year:
            by_year[yr] = G.load_edges(as_of=f"{yr}-12-31")
        for y, rel in neighbours(s["company"], by_year[yr]):
            if y not in z:
                continue
            resp = response(z[y], chain.loc[y, "ticker"], s["close_utc"], epos[y])
            if resp is None:
                continue
            pool = [c for c in chain.index[chain["tier"] == chain.loc[y, "tier"]]
                    if c != y and c != s["company"] and c not in linked_any[s["company"]] and c in z]
            plc = None
            for cand in rng.permutation(pool)[:6]:
                plc = response(z[cand], chain.loc[cand, "ticker"], s["close_utc"], epos[cand])
                if plc is not None:
                    break
            sign = np.sign(s["z"])
            row = {"event": ev_id, "date": s["date"], "source": s["company"], "kind": s["kind"], "shock_z": s["z"],
                   "target": y, "relation": rel}
            for h in HORIZONS:
                row[f"linked_d{h}"] = sign * resp[f"d{h}"]
                row[f"placebo_d{h}"] = sign * plc[f"d{h}"] if plc else np.nan
            rows.append(row)
    pairs = pd.DataFrame(rows)
    return shocks, pairs


def summarise(pairs: pd.DataFrame) -> pd.DataFrame:
    """One observation per shock event (mean over its neighbours), then compare linked vs same-stage strangers."""
    out = []
    cuts = [("all", pairs)] + [(f"{k}", g) for k, g in pairs.groupby("relation")] + \
           [(f"{k}", g) for k, g in pairs.groupby("kind")] + \
           [("shock down", pairs[pairs.shock_z < 0]), ("shock up", pairs[pairs.shock_z > 0])] + \
           [(f"{r} / {k}", g) for (r, k), g in pairs.groupby(["relation", "kind"])]
    for name, g in cuts:
        ev = g.groupby("event")[[c for c in g if c.startswith(("linked_", "placebo_"))]].mean().dropna()
        row = {"cut": name, "events": len(ev), "pairs": len(g)}
        for h in HORIZONS:
            d = ev[f"linked_d{h}"] - ev[f"placebo_d{h}"]
            row[f"linked_d{h}"] = ev[f"linked_d{h}"].mean()
            row[f"placebo_d{h}"] = ev[f"placebo_d{h}"].mean()
            row[f"t_diff_d{h}"] = d.mean() / (d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 5 else np.nan
        row["same_dir_d1"] = (ev["linked_d1"] > 0).mean()
        row["same_dir_placebo_d1"] = (ev["placebo_d1"] > 0).mean()
        out.append(row)
    return pd.DataFrame(out)


def main() -> None:
    shocks, pairs = study()
    res = HERE / "results"
    shocks.to_csv(res / "shocks.csv", index=False)
    pairs.round(4).to_csv(res / "shock_pairs.csv", index=False)
    summ = summarise(pairs)
    summ.round(3).to_csv(res / "shock_summary.csv", index=False)
    by_year = pairs.assign(year=pd.to_datetime(pairs.date).dt.year).groupby("year").apply(
        lambda g: pd.Series({"events": g.event.nunique(), "linked_d1": g.linked_d1.mean(), "placebo_d1": g.placebo_d1.mean()}), include_groups=False)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(f"shocks: {len(shocks)} ({shocks.kind.value_counts().to_dict()}), {shocks.date.min().date()} .. {shocks.date.max().date()}")
    print(f"shocks with at least one measurable neighbour: {pairs.event.nunique()}, neighbour pairs: {len(pairs)}")
    print(summ.round(2).to_string(index=False))
    print(by_year.round(2).to_string())


if __name__ == "__main__":
    main()
