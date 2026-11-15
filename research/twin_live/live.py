"""The twin experiment, forward: the rule found in the research, run on days nobody has seen yet, with rules locked.

Rule (rules.json, locked when the experiment starts; changing it means a new experiment with a new id):
  1. A company in our maps listed in Asia RISES in one day by more than 2 of its usual daily moves beyond its home index.
  2. Its twin: same segment, listed in New York.
  3. At New York's next open (the same calendar day, Asia closes first): if the twin opens flat or down vs its last
     close, buy $10,000 (virtual) at the open price. At most one open trade per company.
  4. Sell at the close of the 10th trading day. No stop, no judgement.
  5. Costs: round trip as in the research (supply_chain.peer_rule.cost).
Control arm, same days: every twin (any exchange the research allows), no opening filter, same holding and costs.
Measured exactly as in the research: return from the open minus that twin's own usual 10-day return (frozen at lock).

Everything is recomputed from real prices on every run; a trade that has closed is written to ledger.csv once and
never recomputed. Safe to run any number of times a day.

    python -m research.twin_live.live            -> map/site/data/twin_live.json, ledger.csv
    python -m research.twin_live.live --lock     (once, at the start: writes the frozen baselines into rules.json)
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from research.supply_chain import markets as MK
from research.supply_chain.peer_leadlag import ORDER, universe
from research.supply_chain.peer_rule import cost

HERE = Path(__file__).parent
import os
RULES = Path(os.environ.get("TWIN_RULES", HERE / "rules.json"))          # overridable for tests only
LEDGER = Path(os.environ.get("TWIN_LEDGER", HERE / "ledger.csv"))
OUT = Path(os.environ.get("TWIN_OUT", HERE.parent / "supply_chain" / "map" / "site" / "data" / "twin_live.json"))
HOLD, Z, TRADE, NEED = 10, 2.0, 10000, 300
CITY = {"T": "טוקיו", "HK": "הונג קונג", "TW": "טייוואן", "TWO": "טייוואן", "KS": "סיאול", "KQ": "סיאול", "SS": "שנגחאי",
        "SZ": "שנג'ן", "NS": "מומבאי", "JK": "ג'קרטה", "AX": "סידני", "L": "לונדון", "PA": "פריז", "DE": "פרנקפורט",
        "AS": "אמסטרדם", "SW": "ציריך", "TA": "תל אביב", "": "ניו יורק", "TO": "טורונטו", "CO": "קופנהגן", "ST": "שטוקהולם"}


def rules_hash(r: dict) -> str:
    keep = {k: r[k] for k in ("id", "start", "hold", "z", "trade_usd", "one_open_per_company", "gap_rule")}
    return hashlib.sha256(json.dumps(keep, sort_keys=True).encode()).hexdigest()[:12]


def pairs(U: pd.DataFrame) -> list[tuple]:
    out = []
    for seg, g in U.groupby("seg"):
        for a in g.itertuples():
            for b in g.itertuples():
                if a.ticker != b.ticker and (a.region, b.region) in ORDER:
                    out.append((a.ticker, a.name, b.ticker, b.name, seg))
    return out


def download(tick, start):
    import yfinance as yf
    raw = yf.download(sorted(tick), start=start, auto_adjust=True, progress=False, threads=True)
    return raw["Open"], raw["Close"]


def series(O, C, t, now):
    if t not in C:
        return None
    o, c = O[t], C[t]
    ok = o.notna() & c.notna() & (o > 0)
    o, c = o[ok], c[ok]
    if len(c) < 70:
        return None
    close = MK.close_utc(t, c.index)
    done = close <= now                                     # drop a session that has not closed yet
    return o[done], c[done], close[done]


def lock() -> None:
    r = json.loads(RULES.read_text())
    if r.get("baseline10"):
        sys.exit("already locked; a change of rules is a new experiment (new id, new start)")
    U = universe()
    P = pairs(U)
    twins = sorted({p[2] for p in P})
    O, C = download(twins, "2021-12-01")
    now = pd.Timestamp(datetime.now(timezone.utc))
    base = {}
    for t in twins:
        s = series(O, C, t, now)
        if s is None:
            continue
        o, c, _ = s
        x = (c.shift(-(HOLD - 1)) / o - 1)[(c.index >= "2022-01-01")].dropna()
        if len(x) > 250:
            base[t] = round(float(x.mean()), 6)
    r["baseline10"] = base
    r["locked_at"] = now.isoformat()
    r["hash"] = rules_hash(r)
    RULES.write_text(json.dumps(r, ensure_ascii=False, indent=1))
    print("locked", r["hash"], len(base), "baselines")


def run(now: pd.Timestamp | None = None) -> dict:
    R = json.loads(RULES.read_text())
    if not R.get("baseline10") or R.get("hash") != rules_hash(R):
        sys.exit("rules.json is not locked or was changed after locking")
    now = now or pd.Timestamp(datetime.now(timezone.utc))
    start = pd.Timestamp(R["start"])
    U = universe()
    P = pairs(U)
    bench = sorted({MK.benchmark(t) for t in U.ticker})
    O, C = download(set(U.ticker) | set(bench) | {"SPY"}, "2025-01-01")
    S, Zs = {}, {}
    for t in U.ticker:
        s = series(O, C, t, now)
        if s is None:
            continue
        o, c, close = s
        cb = C[MK.benchmark(t)].reindex(c.index).ffill()
        ab = c.pct_change() - cb.pct_change()
        S[t] = (o, c, close)
        Zs[t] = (ab / ab.rolling(250, min_periods=60).std().shift(), ab)
    sp = series(O, C, "SPY", now)
    if sp is not None:
        S["SPY"] = sp
    us_dates = S["SPY"][1].index if "SPY" in S else None
    cand, pending = [], []
    for a, an, b, bn, seg in P:
        if a not in S or b not in S or b not in R["baseline10"]:
            continue
        z, ab = Zs[a]
        sig = z[(z > Z) & (z.index >= start - pd.Timedelta(days=5))].dropna()
        if sig.empty:
            continue
        ob, cb, closeb = S[b]
        closea = S[a][2]
        pos = closeb.searchsorted(closea[z.index.get_indexer(sig.index)], side="right")
        us = MK.suffix(b) == "" and U.set_index("ticker").region.get(a) == "asia"
        for (d, zz), j in zip(sig.items(), pos):
            row = {"leader": an, "leader_t": a, "city": CITY.get(MK.suffix(a), MK.suffix(a)), "leader_date": d.strftime("%Y-%m-%d"),
                   "jump": round(float(ab.loc[d]) * 100, 1), "z": round(float(zz), 2), "twin": bn, "twin_t": b, "seg": seg.split(":")[1], "us": bool(us)}
            if j >= len(cb):
                if us:
                    pending.append(row)
                continue
            if cb.index[j] < start:
                continue
            row.update(j=int(j), entry=cb.index[j].strftime("%Y-%m-%d"), gap=round(float(ob.iloc[j] / cb.iloc[j - 1] - 1) * 100, 2))
            cand.append(row)
    ledger = pd.read_csv(LEDGER, dtype=str) if LEDGER.exists() else pd.DataFrame()
    frozen = {(r.arm, r.twin_t, r.entry): r for r in ledger.itertuples()} if len(ledger) else {}
    out_trades, decisions, new_closed = [], [], []
    for arm in ("experiment", "control"):
        X = [c for c in cand if (c["us"] or arm == "control")]
        X.sort(key=lambda c: (c["entry"], -c["z"]))
        busy, seen = {}, set()
        if arm == "experiment":
            busy_exp = busy
        for c in X:
            key = (c["twin_t"], c["entry"])
            if key in seen:
                continue                                    # one trade per twin per day: the biggest jump leads
            seen.add(key)
            ob, cb, _ = S[c["twin_t"]]
            j = c["j"]
            why = None
            if arm == "experiment" and c["gap"] > 0:
                why = "opened_up"
            elif c["twin_t"] in busy and busy[c["twin_t"]] >= c["entry"]:
                why = "already_holding"
            if arm == "experiment":
                decisions.append({**{k: c[k] for k in ("leader", "city", "leader_date", "jump", "twin", "twin_t", "seg", "entry", "gap")},
                                  "bought": why is None, "why": why})
            if why:
                continue
            k = min(j + HOLD - 1, len(cb) - 1)
            busy[c["twin_t"]] = cb.index[j + HOLD - 1].strftime("%Y-%m-%d") if j + HOLD - 1 < len(cb) else "9999"
            fz = frozen.get((arm, c["twin_t"], c["entry"]))
            days = k - j + 1
            base = R["baseline10"][c["twin_t"]]
            px_in = float(ob.iloc[j])
            fee = cost(c["twin_t"], px_in if MK.suffix(c["twin_t"]) == "" else 100.0, TRADE)
            if fz is not None:
                t = {"arm": arm, "twin_t": c["twin_t"], "twin": c["twin"], "leader": c["leader"], "city": c["city"], "entry": c["entry"],
                     "exit": fz.exit, "days": HOLD, "ret": float(fz.ret), "excess": float(fz.excess), "net": float(fz.net), "spy": float(fz.spy), "closed": True}
            else:
                ret = float(cb.iloc[k] / ob.iloc[j] - 1)
                spy = np.nan
                if us_dates is not None:
                    so, sc = S["SPY"][0], S["SPY"][1]
                    i0, i1 = so.index.searchsorted(cb.index[j]), sc.index.searchsorted(cb.index[k])
                    if i1 < len(sc):
                        spy = float(sc.iloc[i1] / so.iloc[i0] - 1)
                excess = ret - base * days / HOLD
                t = {"arm": arm, "twin_t": c["twin_t"], "twin": c["twin"], "leader": c["leader"], "city": c["city"], "entry": c["entry"],
                     "exit": cb.index[k].strftime("%Y-%m-%d"), "days": days, "ret": ret, "excess": excess,
                     "net": excess - fee, "spy": spy, "closed": days == HOLD}
                if t["closed"]:
                    new_closed.append(t)
            out_trades.append(t)
    held = {t: e for t, e in busy_exp.items()}
    for p in pending:
        p["holding"] = held.get(p["twin_t"], "") >= p["leader_date"]
    if new_closed:
        add = pd.DataFrame(new_closed)[["arm", "twin_t", "entry", "exit", "ret", "excess", "net", "spy"]]
        pd.concat([ledger, add.astype(str)]).to_csv(LEDGER, index=False)
    T = pd.DataFrame(out_trades)

    def stats(x):
        x = x[x.closed] if len(x) else x
        n = int(len(x))
        if n == 0:
            return {"closed": 0}
        m, sd = float(x.net.mean()), float(x.net.std()) if n > 1 else float("nan")
        return {"closed": n, "mean_net_pct": round(m * 100, 2), "won_pct": round(float((x.net > 0).mean() * 100), 1),
                "t": round(m / sd * np.sqrt(n), 2) if n > 2 and sd > 0 else None,
                "sum_usd": round(float(x.net.sum() * TRADE)), "vs_spy_pct": round(float((x.ret - x.spy).mean() * 100), 2)}
    E = T[T.arm == "experiment"] if len(T) else T
    Cn = T[T.arm == "control"] if len(T) else T
    last_us = S["SPY"][1].index[-1].strftime("%Y-%m-%d") if "SPY" in S else None
    rnd = lambda v: None if v is None or (isinstance(v, float) and np.isnan(v)) else round(v * 100, 2)   # noqa: E731
    res = {
        "updated_utc": now.strftime("%Y-%m-%d %H:%M"), "last_us_session": last_us, "start": R["start"], "id": R["id"], "hash": R["hash"],
        "need": NEED, "backtest": R["backtest"], "rules_he": R["rules_he"],
        "experiment": stats(E), "control": stats(Cn),
        "pending": sorted(pending, key=lambda c: -c["z"]),
        "recent": sorted(decisions, key=lambda d: d["entry"], reverse=True)[:12],
        "open": [{**{k: t[k] for k in ("twin_t", "twin", "leader", "city", "entry", "days")}, "net_pct": rnd(t["excess"])}
                 for t in E[~E.closed].to_dict("records")] if len(E) else [],
        "closed": [{**{k: t[k] for k in ("twin_t", "twin", "leader", "city", "entry", "exit")}, "net_pct": rnd(t["net"])}
                   for t in E[E.closed].sort_values("exit", ascending=False).to_dict("records")] if len(E) else [],
    }
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    return res


if __name__ == "__main__":
    if "--lock" in sys.argv:
        lock()
    else:
        r = run(pd.Timestamp(sys.argv[sys.argv.index("--asof") + 1], tz="UTC") if "--asof" in sys.argv else None)
        print(json.dumps({k: r[k] for k in ("updated_utc", "last_us_session", "experiment", "control")}, ensure_ascii=False))
        print("pending", len(r["pending"]), "recent", len(r["recent"]), "open", len(r["open"]), "closed", len(r["closed"]))
