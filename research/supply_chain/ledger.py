"""The forecast ledger: every forecast is written down before the outcome exists, never edited,
and scored later. This is the only evidence that cannot be contaminated by hindsight.

A forecast is created when a company has a shock (see shocks.py) and a linked neighbour's
next five sessions are still in the future. It says: over sessions 1-5 after the shock reached
the neighbour's market, the neighbour moves in the SAME direction as the shock, by about the
historical average. Two baselines are stored with it: "no effect", and the same-stage stranger.

Records are chained: each line stores the hash of the previous line, so a later edit is detectable.

    python -m research.supply_chain.ledger make     # add forecasts for fresh shocks
    python -m research.supply_chain.ledger score    # score forecasts whose window has closed
    python -m research.supply_chain.ledger report
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import graph as G
from . import markets as MK
from . import shocks as S
from .run import all_prices

DIR = Path(__file__).parent / "ledger" / G.MARKET
DIR.mkdir(parents=True, exist_ok=True)
F, SC = DIR / "forecasts.jsonl", DIR / "scores.jsonl"
WINDOW, LOOKBACK = 5, 6      # forecast sessions 1..5; consider shocks from the last 6 sessions


def _read(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def _append(p: Path, rec: dict) -> None:
    rows = _read(p)
    rec["prev"] = rows[-1]["hash"] if rows else "genesis"
    rec["hash"] = hashlib.sha256(json.dumps(rec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    with p.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def verify(p: Path) -> bool:
    prev = "genesis"
    for r in _read(p):
        h = r.pop("hash")
        if r["prev"] != prev or hashlib.sha256(json.dumps(r, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16] != h:
            return False
        prev = h
    return True


def history_expectation() -> dict:
    """Average signed move of linked neighbours over sessions 1-5, from the shock library (sigma units)."""
    p = G.RESULTS / "shock_pairs.csv"
    d = pd.read_csv(p)
    for k in ("linked", "placebo"):
        d[f"{k}_w"] = (d[f"{k}_d5"] * np.sqrt(6) - d[f"{k}_d0"]) / np.sqrt(5)
    ev = d.groupby(["relation", "event"])[["linked_w", "placebo_w"]].mean()
    out = {}
    for rel, g in ev.groupby(level=0):
        out[rel] = {"expected_sig": round(float(g["linked_w"].mean()), 3), "stranger_sig": round(float(g["placebo_w"].dropna().mean()), 3),
                    "same_direction_rate": round(float((g["linked_w"] > 0).mean()), 3), "events": int(len(g))}
    return out


def _context():
    companies = G.load_companies()
    chain = companies[companies["tier"] != "control"]
    prices = all_prices(companies)
    earnings = S.load_earnings(chain)
    z = S.abnormal_z(prices, chain)
    return chain, earnings, z


def make() -> None:
    chain, earnings, z = _context()
    shocks = S.find_shocks(z, chain, earnings)
    exp = history_expectation()
    edges = G.load_edges()
    have = {(r["source"], r["shock_date"], r["target"]) for r in _read(F)}
    last = max(s.index.max() for s in z.values())
    n = 0
    for _, s in shocks[shocks.date >= last - pd.tseries.offsets.BDay(LOOKBACK)].iterrows():
        for y, rel in S.neighbours(s["company"], edges):
            if y not in z or (s["company"], str(s["date"].date()), y) in have:
                continue
            closes = MK.close_utc(chain.loc[y, "ticker"], z[y].index)
            j = int(closes.searchsorted(s["close_utc"], side="left"))      # neighbour's day 0
            known = len(z[y]) - 1 - j                                      # sessions after day 0 already seen
            if known >= 1:                                                 # window has started: too late to forecast honestly
                continue
            _append(F, {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": s["company"],
                        "shock_date": str(s["date"].date()), "shock_kind": s["kind"], "shock_z": round(s["z"], 2), "target": y,
                        "relation": rel, "window": f"sessions 1-{WINDOW} after the shock reaches the target's market",
                        "target_day0": str(z[y].index[j].date()) if j < len(z[y]) else None,
                        "predicted_direction": "up" if s["z"] > 0 else "down",
                        "expected_signed_sig": exp[rel]["expected_sig"], "baseline_stranger_sig": exp[rel]["stranger_sig"],
                        "history_same_direction_rate": exp[rel]["same_direction_rate"], "history_events": exp[rel]["events"],
                        "prices_known_until": str(z[y].index.max().date())})
            n += 1
    print(f"{n} new forecasts; ledger now holds {len(_read(F))}; chain intact: {verify(F)}")


def score() -> None:
    chain, _, z = _context()
    done = {r["forecast"] for r in _read(SC)}
    n = 0
    for r in _read(F):
        if r["hash"] in done or r["target"] not in z:
            continue
        s = z[r["target"]]
        src_close = MK.close_utc(chain.loc[r["source"], "ticker"], pd.DatetimeIndex([pd.Timestamp(r["shock_date"])]))[0]
        j = int(MK.close_utc(chain.loc[r["target"], "ticker"], s.index).searchsorted(src_close, side="left"))
        if j + WINDOW >= len(s):
            continue                                                       # window not finished yet
        move = float(s.to_numpy()[j + 1:j + 1 + WINDOW].sum() / np.sqrt(WINDOW))
        signed = move if r["predicted_direction"] == "up" else -move
        _append(SC, {"forecast": r["hash"], "scored_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "actual_signed_sig": round(signed, 3), "same_direction": bool(signed > 0),
                     "window_end": str(s.index[j + WINDOW].date())})
        n += 1
    print(f"{n} forecasts scored; {len(_read(SC))} scored in total")


def report() -> None:
    f, s = _read(F), _read(SC)
    print(f"forecasts: {len(f)}, scored: {len(s)}, chains intact: {verify(F)} / {verify(SC)}")
    if s:
        d = pd.DataFrame(s)
        print(f"same direction: {d.same_direction.mean():.0%} of {len(d)}; mean signed move {d.actual_signed_sig.mean():+.2f} sigma")


if __name__ == "__main__":
    {"make": make, "score": score, "report": report}[sys.argv[1] if len(sys.argv) > 1 else "report"]()
