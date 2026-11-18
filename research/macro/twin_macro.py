"""Do central-bank days change the twin signal? (check of 2026-11-15)

Dates: Fed decision days (federalreserve.gov statement links, 2016-2026) and Bank of Japan decision days (boj.or.jp
statement links, 2011-2026), saved in data/. US CPI release dates could not be fetched (bls.gov blocks cloud addresses).
A twin trade is a "macro day" trade when the Asian leader jumped on a BoJ decision day or on the first Asian session
after a Fed decision (the Fed decides in the US afternoon, Asia trades next).

    python -m research.macro.twin_macro
"""
from pathlib import Path

import pandas as pd

from research.supply_chain.twin_combo import load
from research.supply_chain.twin_split import tday

D = Path(__file__).parent / "data"


def main() -> None:
    fomc = pd.to_datetime((D / "fomc_decisions.txt").read_text().split())
    boj = set(pd.to_datetime((D / "boj_decisions.txt").read_text().split()))
    after_fomc = {d + pd.offsets.BDay(1) for d in fomc}
    T = load()
    T = T[T.date >= "2017-01-01"]
    T["fomc"] = T.date.isin(after_fomc)
    T["boj"] = T.date.isin(boj)
    T["macro"] = T.fomc | T.boj
    for lab, S in (("all twins led from Asia", T[T.dir.str.startswith("asia")]), ("experiment rule: US twin, opened flat/down", T[T.gapf & T.us])):
        print(lab)
        for k, m in (("macro day", S.macro), ("  day after Fed", S.fomc), ("  BoJ day", S.boj), ("ordinary day", ~S.macro)):
            x = S[m]
            print(f"   {k:16} n={len(x):5d}  x10={x.x10.mean() * 100:5.2f}% (t {tday(x.x10, x.date):4.1f})  net10={(x.x10 - x.cost).mean() * 100:5.2f}%")


if __name__ == "__main__":
    main()
