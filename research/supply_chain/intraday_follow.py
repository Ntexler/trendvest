"""Can an investor who watches the screen catch the follow-through within the hour, while both markets are open?

Free hourly bars (Yahoo, ~3 years back) for every company in our maps, its home index, and a few companies listed twice
(the same company in Tel Aviv / Europe and New York). While two exchanges are open together (Europe and New York in the
New York morning; Tel Aviv and New York 16:30-17:25 Israel time; Hong Kong and Europe in the European morning) a jump in
one company can be seen live, and the other one bought within minutes.

Signal: in one hour the leader moves more than 2.5 of its usual hourly moves, beyond its home index.
Trade:  buy (or sell, for a drop) the follower at the open of its next hourly bar that starts within 60 minutes of the
        signal; hold 1 bar, or to the follower's close that day. Everything measured beyond the follower's own index.
Costs:  round trip as in peer_rule.cost (broker, taxes, half spread x2, currency) for a $10,000 trade.
Families: same segment, other region (twins); same segment, same region (competitors); the same company, two listings.

    python -m research.supply_chain.intraday_follow     -> results/intraday_follow.json
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import markets as MK
from .peer_leadlag import REGION
from .peer_rule import cost

BASE = Path(__file__).parent
OUT = BASE / "results" / "intraday_follow.json"
DUAL = [("TEVA", "TEVA.TA"), ("NICE", "NICE.TA"), ("ESLT", "ESLT.TA"), ("ICL", "ICL.TA"), ("TSEM", "TSEM.TA"),
        ("ASML", "ASML.AS"), ("SAP", "SAP.DE"), ("NVO", "NOVO-B.CO"), ("SHEL", "SHEL.L"), ("BP", "BP.L"), ("TTE", "TTE.PA"),
        ("SNY", "SAN.PA"), ("AZN", "AZN.L"), ("UL", "ULVR.L"), ("RIO", "RIO.L"), ("BHP", "BHP.AX"), ("HSBC", "HSBA.L")]
Z = 2.5


def companies() -> pd.DataFrame:
    rows = []
    for d in sorted((BASE / "data").iterdir()):
        if (d / "companies.csv").exists():
            c = pd.read_csv(d / "companies.csv", comment="#")
            c["market"] = d.name
            rows.append(c)
    c = pd.concat(rows)
    c = c[c.tier != "control"].drop_duplicates("ticker")
    c["seg"] = c.market + ":" + c.segment
    c["region"] = c.ticker.map(lambda t: REGION(MK.suffix(t)))
    return c


def pairs() -> list[tuple[str, str, str]]:
    c = companies()
    out = set()
    for seg, g in c.groupby("seg"):
        for a in g.itertuples():
            for b in g.itertuples():
                if a.ticker != b.ticker:
                    out.add((a.ticker, b.ticker, "competitor, same region" if a.region == b.region else "twin, other region"))
    for a, b in DUAL:
        out.add((a, b, "same company, two listings"))
        out.add((b, a, "same company, two listings"))
    return sorted(out)


def bars(raw: pd.DataFrame, t: str) -> pd.DataFrame | None:
    if t not in raw["Close"]:
        return None
    d = pd.DataFrame({"o": raw["Open"][t], "c": raw["Close"][t]}).dropna()
    d = d[(d.o > 0) & (d.c > 0)]
    if len(d) < 300:
        return None
    d.index = d.index.tz_convert("UTC")
    d["day"] = d.index.normalize()
    d["r"] = d.c / d.o - 1
    return d


def main() -> None:
    import yfinance as yf
    P = pairs()
    tick = sorted({x for a, b, _ in P for x in (a, b)})
    bench = sorted({MK.benchmark(t) for t in tick})
    raw = yf.download(tick + bench, period="730d", interval="60m", progress=False, threads=True)
    B = {t: bars(raw, t) for t in tick + bench}
    info = {}
    for t in tick:
        d, b = B[t], B.get(MK.benchmark(t))
        if d is None or b is None:
            continue
        d = d.join(b[["o", "c", "r"]].rename(columns={"o": "bo", "c": "bc", "r": "br"}), how="left")
        d["ab"] = d.r - d.br.fillna(0)
        d["z"] = d.ab / d.ab.rolling(400, min_periods=150).std().shift()
        info[t] = d
    rows = []
    for a, b, fam in P:
        if a not in info or b not in info:
            continue
        A, F = info[a], info[b]
        sig = A[A.z.abs() > Z]
        if sig.empty:
            continue
        end = sig.index + pd.Timedelta(minutes=60)
        j = F.index.searchsorted(end, side="left")
        ok = j < len(F)
        for (ts, s), jj in zip(sig[ok].iterrows(), j[ok]):
            e = F.iloc[jj]
            if F.index[jj] - end[sig.index.get_loc(ts)] > pd.Timedelta(minutes=60):
                continue                                   # follower not open within the hour: not a live trade
            same = F[(F.day == e.day) & (F.index >= F.index[jj])]
            last = same.iloc[-1]
            sgn = 1 if s.z > 0 else -1
            bo, b1, bl = e.bo, e.bc, last.bc
            r1 = (e.c / e.o - 1) - ((b1 / bo - 1) if pd.notna(bo) and bo > 0 else 0)
            rd = (last.c / e.o - 1) - ((bl / bo - 1) if pd.notna(bo) and bo > 0 else 0)
            rows.append({"fam": fam, "leader": a, "follower": b, "dir": f"{REGION(MK.suffix(a))}→{REGION(MK.suffix(b))}",
                         "ts": F.index[jj], "date": e.day, "z": s.z, "x1": sgn * r1, "xd": sgn * rd,
                         "cost": cost(b, 100.0, 10000)})
    D = pd.DataFrame(rows).sort_values("z", key=abs, ascending=False).drop_duplicates(["fam", "follower", "ts"])

    def tday(e, dates):
        s = e.groupby(dates).mean()
        return float(s.mean() / s.std() * np.sqrt(len(s))) if len(s) > 2 and s.std() > 0 else float("nan")

    def block(x):
        return {"trades": int(len(x)), "days": int(x.date.nunique()),
                "follow_next_hour_pct": round(float(x.x1.mean() * 100), 3), "t_hour": round(tday(x.x1, x.date), 2),
                "follow_to_close_pct": round(float(x.xd.mean() * 100), 3), "t_close": round(tday(x.xd, x.date), 2),
                "cost_pct": round(float(x.cost.mean() * 100), 3),
                "net_to_close_pct": round(float((x.xd - x.cost).mean() * 100), 3),
                "won_after_cost_pct": round(float(((x.xd - x.cost) > 0).mean() * 100), 1)}
    res = {"period": [str(D.ts.min()), str(D.ts.max())], "threshold_z": Z, "families": {}, "by_direction": {}}
    for fam, g in D.groupby("fam"):
        res["families"][fam] = block(g)
        for d, x in g.groupby("dir"):
            if len(x) >= 30:
                res["by_direction"][f"{fam} · {d}"] = block(x)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(res["period"])
    for k, v in list(res["families"].items()) + list(res["by_direction"].items()):
        print(k.ljust(52), v)


if __name__ == "__main__":
    main()
