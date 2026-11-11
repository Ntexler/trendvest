"""Run the supply-chain spillover study.

    python -m research.supply_chain.run            # all events marked best/ok
    python -m research.supply_chain.run --best     # only the cleanest events

Outputs in research/supply_chain/results/:
    event_company.csv  every (event, company): role, day 0 on its own exchange, abnormal moves
    event_role.csv     average per (event, role)
    summary.csv        the headline table: per role, how big / how fast / how reliable
    linkcheck.json     price-based validation of the map itself
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

from ..news_impact.data import load_prices
from . import graph as G
from . import linkcheck as L
from . import markets as MK
from . import spillover as S

RESULTS = Path(__file__).parent / "results"


def all_prices(companies: pd.DataFrame) -> pd.DataFrame:
    tickers = sorted(set(companies["ticker"]) | {MK.benchmark(t) for t in companies["ticker"]})
    return load_prices(tickers, date(2014, 6, 1), date.today())["Close"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--best", action="store_true")
    ap.add_argument("--weighted", action="store_true", help="pass shocks only through material links")
    args = ap.parse_args()
    companies = G.load_companies()
    prices = all_prices(companies)
    missing = [t for t in companies["ticker"] if t not in prices or prices[t].dropna().empty]
    if missing:
        print("! no price data for:", missing)

    real, per_event, summary = S.run(prices, quality=("best",) if args.best else ("best", "ok"),
                                     weighted=args.weighted)
    tag = "_weighted" if args.weighted else ""
    RESULTS.mkdir(exist_ok=True)
    real.round({c: 4 for c in real.select_dtypes("number").columns}).to_csv(RESULTS / f"event_company{tag}.csv", index=False)
    per_event.round(4).to_csv(RESULTS / f"event_role{tag}.csv", index=False)
    summary.round(3).to_csv(RESULTS / f"summary{tag}.csv")

    # the map check uses chain companies only; the control group would dilute "unlinked" pairs
    ar = L.weekly_abnormal(prices, companies[companies["tier"] != "control"])
    edges = G.load_edges()
    link = {"pair_comovement": L.pair_comovement(ar, edges),
            "customer_momentum": L.customer_momentum(ar, edges)}
    (RESULTS / "linkcheck.json").write_text(json.dumps(link, indent=2))

    pd.set_option("display.width", 250, "display.max_columns", 40)
    print("\n=== Spillover by role (abnormal move in sigma units; one observation per event) ===")
    show = ["events", "expected", "mean_sig_d0", "mean_sig_d1", "mean_sig_d3", "mean_sig_d10",
            "pct_d3", "t_d3", "placebo_p_d3", "hit_rate_d3", "peak_day", "half_day",
            "given_back_by_d10", "pre_move_sig"]
    print(summary[[c for c in show if c in summary]].round(2).to_string())
    print("\n=== Map validation from prices ===")
    print(json.dumps(link, indent=2))


if __name__ == "__main__":
    main()
