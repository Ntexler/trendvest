"""The daily run. One command refreshes every market and leaves the page data ready.

    python -m research.supply_chain.auto            # every market
    python -m research.supply_chain.auto chips ai   # only these
    python -m research.supply_chain.auto --no-fetch # recompute from the data already on disk

Order, per market (each market runs in its own process, because the market is chosen at import):
    1. fetch      prices every run; company profiles on Mondays (they change with quarterly reports)
    2. score      close every forecast and claim whose date has passed, BEFORE anything new is written
    3. forecasts  short-term shock forecasts (ledger.py)
    4. screen     cheap-and-growing candidates
    5. inference  states -> history -> cards -> claims
    6. page data  build_map; after all markets: compare
Base rates are recomputed once a week from all markets together.
A step that fails is reported and the run goes on; the exit code is non-zero if anything failed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).parent
ROOT = BASE.parent.parent
MARKETS = sorted(d.name for d in (BASE / "data").iterdir() if (d / "market.json").exists())

STEP = """
import sys
from research.supply_chain import graph as G
step = sys.argv[1]
if step == "fetch":
    from research.supply_chain import fetch
    fetch.prices()
    if sys.argv[2] == "1":
        fetch.profiles(refresh=True)
elif step == "score":
    from research.supply_chain import inference
    inference.score()
    if (G.RESULTS / "shock_pairs.csv").exists():
        from research.supply_chain import ledger
        ledger.score()
elif step == "forecasts":
    if (G.RESULTS / "shock_pairs.csv").exists():
        from research.supply_chain import ledger
        ledger.make()
elif step == "screen":
    from research.supply_chain import screen
    screen.log_candidates(screen.run())
elif step == "inference":
    from research.supply_chain import inference
    inference.detect()
elif step == "page":
    from research.supply_chain import build_map
    build_map.main()
"""


def run(market: str, step: str, *args: str) -> bool:
    r = subprocess.run([sys.executable, "-c", STEP, step, *args], cwd=ROOT, env={**os.environ, "MARKET": market},
                       capture_output=True, text=True)
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    print(f"  {step:10s} {'ok  ' if r.returncode == 0 else 'FAIL'} {tail if r.returncode == 0 else r.stderr.strip().splitlines()[-1]}")
    return r.returncode == 0


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fetch = "--no-fetch" not in sys.argv
    monday = date.today().weekday() == 0 or "--profiles" in sys.argv
    failed = []
    rates = BASE / "results" / "base_rates.json"
    for m in args or MARKETS:
        print(m)
        steps = ([("fetch", "1" if monday else "0")] if fetch else []) + [("score",), ("forecasts",), ("screen",)]
        failed += [(m, s[0]) for s in steps if not run(m, *s)]
    if monday or not rates.exists():                 # after the fetch, so history includes the newest week
        ok = subprocess.run([sys.executable, "-m", "research.supply_chain.inference", "base"], cwd=ROOT, capture_output=True).returncode == 0
        print("base rates", "ok" if ok else "FAIL")
        failed += [] if ok else [("all", "base")]
    for m in args or MARKETS:
        print(m)
        failed += [(m, s) for s in ("inference", "page") if not run(m, s)]
    ok = subprocess.run([sys.executable, "-m", "research.supply_chain.compare"], cwd=ROOT, capture_output=True).returncode == 0
    print("compare", "ok" if ok else "FAIL")
    if failed or not ok:
        print("failed:", failed)
        sys.exit(1)


if __name__ == "__main__":
    main()
