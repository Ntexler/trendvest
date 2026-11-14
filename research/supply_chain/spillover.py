"""Stage B: did past disruptions travel along the supply-chain map, how far and how fast?

For every event and every company in the map:
  * day 0 = first session of that company's own exchange that closes after the event (UTC)
  * abnormal return = return minus what the local market index explains (market model
    fitted on days -250..-11), in units of the stock's normal daily noise (sigma)
  * the company's ROLE is derived mechanically from the map (hit / customer / supplier /
    rival / control) and the expected direction is fixed in graph.EXPECTED_SIGN

Guards against fooling ourselves with ~20 events:
  * roles and expected signs are rule-based, not chosen after seeing results
  * statistics are computed on per-event averages (one observation per event per role)
  * placebo: the same calculation on random non-event dates gives the "no effect" spread
  * 'control' companies (in the universe but unrelated to the hit) are reported alongside
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import graph as G
from . import markets as MK

PRE, POST = 5, 10
HORIZONS = (0, 1, 3, 5, 10)


def company_paths(prices: pd.DataFrame, ticker: str, event_utc: pd.Timestamp):
    close = prices[ticker].dropna()
    bench = prices[MK.benchmark(ticker)].dropna()
    if len(close) < 300:
        return None
    i0 = MK.day0_position(ticker, close.index, event_utc)
    if i0 is None:
        return None
    res = MK.abnormal_returns(close, bench, i0, pre=PRE, post=POST)
    if res is None or not np.isfinite(res["ar"]).all() or res["sigma"] <= 0:
        return None
    return res


def study_event(ev_id: str, ev: pd.Series, companies: pd.DataFrame, prices: pd.DataFrame,
                ts: pd.Timestamp | None = None, edges: pd.DataFrame | None = None,
                weighted: bool = False) -> pd.DataFrame:
    ts = ts if ts is not None else ev["ts_utc"]
    if edges is None:
        edges = G.load_edges(as_of=str(ev["ts_utc"].date()))
    hit = [h for h in str(ev["hit"]).split(";") if h in companies.index]
    role = G.roles(hit, edges, companies, weighted=weighted)
    rows = []
    for cid, c in companies.iterrows():
        res = company_paths(prices, c["ticker"], ts)
        if res is None:
            continue
        sar = res["ar"] / res["sigma"]
        car = np.cumsum(sar[PRE:])                      # cumulative from day 0, in sigma units
        row = {"event": ev_id, "company": cid, "role": role[cid], "day0": res["day0"],
               "pre": sar[:PRE].sum() / np.sqrt(PRE)}
        for h in HORIZONS:
            row[f"scar{h}"] = car[h] / np.sqrt(h + 1)   # ~N(0,1) if nothing happened
            row[f"pct{h}"] = np.cumsum(res["ar"][PRE:])[h] * 100
        for k in range(POST + 1):
            row[f"path{k}"] = car[k]
        rows.append(row)
    return pd.DataFrame(rows)


def run(prices: pd.DataFrame, quality: tuple[str, ...] = ("best", "ok"), n_placebo: int = 200,
        seed: int = 7, weighted: bool = False):
    companies, events = G.load_companies(), G.events()
    events = events[events["quality"].isin(quality)]
    real = pd.concat([study_event(i, e, companies, prices, weighted=weighted) for i, e in events.iterrows()],
                     ignore_index=True)

    # one number per (event, role): the average company in that role
    cols = [f"scar{h}" for h in HORIZONS] + [f"pct{h}" for h in HORIZONS] + ["pre"] + \
           [f"path{k}" for k in range(POST + 1)]
    per_event = real.groupby(["event", "role"])[cols].mean().reset_index()

    # placebo: same events, same roles, but shifted to random dates far from the real one
    rng = np.random.default_rng(seed)
    plc = []
    for i, e in events.iterrows():
        edges = G.load_edges(as_of=str(e["ts_utc"].date()))
        for _ in range(n_placebo // max(len(events), 1) + 1):
            shift = int(rng.choice([-1, 1]) * rng.integers(40, 500))
            ts = e["ts_utc"] + pd.Timedelta(days=shift)
            if ts > pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=30):
                ts = e["ts_utc"] - pd.Timedelta(days=abs(shift))
            p = study_event(i, e, companies, prices, ts=ts, edges=edges, weighted=weighted)
            if len(p):
                plc.append(p.groupby("role")[[f"scar{h}" for h in HORIZONS]].mean())
    placebo = pd.concat(plc).reset_index()

    summary = []
    for role, g in per_event.groupby("role"):
        sign = G.EXPECTED_SIGN.get(role, 0)
        row = {"role": role, "events": len(g), "expected": {1: "up", -1: "down", 0: "none"}[sign],
               "companies_per_event": real[real.role == role].groupby("event").size().mean()}
        for h in HORIZONS:
            x = g[f"scar{h}"]
            row[f"mean_sig_d{h}"] = x.mean()
            row[f"t_d{h}"] = x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 else np.nan
            row[f"pct_d{h}"] = g[f"pct{h}"].mean()
            pl = placebo.loc[placebo.role == role, f"scar{h}"]
            # placebo spread of an average over the same number of events
            row[f"placebo_p_d{h}"] = np.nan
            if len(pl) > 30:
                sims = rng.choice(pl.to_numpy(), size=(4000, len(x))).mean(axis=1)
                row[f"placebo_p_d{h}"] = float((np.abs(sims) >= abs(x.mean())).mean())
        if sign:
            row["hit_rate_d3"] = float((np.sign(g["scar3"]) == sign).mean())
        path = g[[f"path{k}" for k in range(POST + 1)]].mean().to_numpy()
        peak = int(np.argmax(np.abs(path)))
        row["peak_day"] = peak
        row["half_day"] = int(np.argmax(np.abs(path) >= 0.5 * abs(path[peak])))
        row["given_back_by_d10"] = float(1 - path[-1] / path[peak]) if abs(path[peak]) > 1e-9 else np.nan
        row["pre_move_sig"] = g["pre"].mean()
        summary.append(row)
    order = ["hit", "down1", "down2", "up1", "up2", "rival", "control"]
    summary = pd.DataFrame(summary).set_index("role").reindex([o for o in order if o in per_event.role.unique()])
    return real, per_event, summary
