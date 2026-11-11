"""Run every step for one market, in order. Each step is skipped if its output already exists.

    MARKET=medical python -m research.supply_chain.pipeline
"""

from __future__ import annotations

import sys

from . import graph as G


def main() -> None:
    from . import validate
    p = validate.problems()
    if p:
        print(f"{G.MARKET}: not valid, stopping:")
        for x in p:
            print(" -", x)
        sys.exit(1)
    from . import fetch
    fetch.profiles()
    fetch.prices()
    if not (G.DATA / "news.json").exists():
        fetch.news()
    G.RESULTS.mkdir(parents=True, exist_ok=True)
    if not (G.RESULTS / "event_company_weighted.csv").exists():
        sys.argv = ["run", "--weighted"]
        from . import run
        run.main()
    sys.argv = ["x"]
    from . import baskets, screen
    baskets.builder()
    res = screen.run()
    print("candidates:", [k for k, v in res.items() if v["candidate"]], "logged:", screen.log_candidates(res))
    from . import build_map
    build_map.main()


if __name__ == "__main__":
    main()
