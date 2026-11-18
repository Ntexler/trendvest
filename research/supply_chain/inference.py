"""What is likely to happen next: unusual states found by fixed rules, each with its historical record.

The division of labour is the whole design:
    rules   find the state           (detectors below; no judgment, same answer every run)
    history says how often it ended  (base rates, computed from our own data, pooled over markets)
    ledger  keeps the claim          (dated, testable, hash-chained, scored when its date passes)
    writer  only phrases it          (writer.py: template, or a model that may not add numbers)

A card is published only when history actually leans one way (enough cases and a clear gap from the
plain average). When it does not, the state is counted under "checked, nothing to say".

    python -m research.supply_chain.inference base                 # recompute base rates (all markets)
    MARKET=chips python -m research.supply_chain.inference detect  # states -> cards -> claims
    MARKET=chips python -m research.supply_chain.inference score   # score claims whose date passed
    MARKET=chips python -m research.supply_chain.inference report
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import graph as G

BASE = Path(__file__).parent
RATES = BASE / "results" / "base_rates.json"
LEDGER = BASE / "ledger" / G.MARKET
CLAIMS, SCORES = LEDGER / "claims.jsonl", LEDGER / "claim_scores.jsonl"

MIN_CASES, MIN_GAP = 30, 10.0        # publish only with this many past cases and this gap (points) from the plain average
GROWTH_BUCKETS = [(50, None), (25, 50)]                      # revenue growth vs a year earlier, percent
RUN_UP, DROP = 100.0, -40.0          # one-year price change relative to the market index, percent
YEAR, HALF = 52, 26                  # weeks
DEADLINE_DAYS = 100                  # dated changes this close are shown


# ---------------------------------------------------------------- history: base rates

def _all_weekly() -> dict[str, pd.DataFrame]:
    out = {}
    for d in sorted((BASE / "data").iterdir()):
        p = d / "prices_weekly.json"
        if p.exists():
            w = json.loads(p.read_text())
            out[d.name] = pd.DataFrame(w["series"], index=pd.to_datetime(w["dates"])).astype(float)
    return out


def _rel(frame: pd.DataFrame, weeks: int) -> pd.DataFrame:
    """Price change over `weeks`, relative to the market index, percent."""
    r = frame / frame.shift(weeks)
    return (r.div(r["_MARKET"], axis=0) - 1).drop(columns="_MARKET") * 100


def _vol(frame: pd.DataFrame) -> pd.DataFrame:
    return np.log(frame.drop(columns="_MARKET")).diff().rolling(HALF).std() * np.sqrt(52) * 100


def base_growth() -> dict:
    """After revenue grew this fast, what was growth a year later? US chip filers, quarterly, SEC."""
    sec = json.loads((BASE / "data" / "chips" / "pulses.json").read_text())["sec"]
    rows = []
    for co, v in sec.items():
        s = pd.Series(v["rev_q"]).astype(float)
        g = (s / s.shift(4) - 1) * 100
        for now, later in zip(g.iloc[:-4], g.iloc[4:]):
            if np.isfinite(now) and np.isfinite(later):
                rows.append((co, now, later))
    d = pd.DataFrame(rows, columns=["co", "now", "later"])
    out = {"source": "SEC quarterly revenue, 30 US-listed chip companies", "cases_all": len(d),
           "slowed_all_pct": round(float((d.later < d.now).mean() * 100), 1), "buckets": []}
    for lo, hi in GROWTH_BUCKETS:
        b = d[(d.now >= lo) & (d.now < (hi or 1e9))]
        out["buckets"].append({"lo": lo, "hi": hi, "cases": len(b), "companies": int(b.co.nunique()),
                               "median_now": round(float(b.now.median()), 1), "median_later": round(float(b.later.median()), 1),
                               "slowed_pct": round(float((b.later < b.now).mean() * 100), 1),
                               "halved_pct": round(float((b.later < b.now / 2).mean() * 100), 1)})
    return out


def base_price() -> dict:
    """After a year far ahead of (or behind) the index, how did the next half-year go against the index?"""
    rows, seen = [], set()
    for m, f in _all_weekly().items():
        past, nxt = _rel(f, YEAR), _rel(f, HALF).shift(-HALF)
        for co in past.columns:
            if co in seen:                                   # a company listed in two markets counts once
                continue
            seen.add(co)
            for t in past.index[YEAR::HALF]:                 # every half-year: outcome windows do not overlap
                a, b = past.at[t, co], nxt.at[t, co]
                if np.isfinite(a) and np.isfinite(b):
                    rows.append((co, a, b))
    d = pd.DataFrame(rows, columns=["co", "past", "next"])

    def stat(b):
        return {"cases": len(b), "companies": int(b.co.nunique()), "beat_index_pct": round(float((b.next > 0).mean() * 100), 1),
                "median_next": round(float(b.next.median()), 1)}
    return {"source": "weekly prices, six markets, five years; today's company list (companies that vanished are missing)",
            "all": stat(d), "run_up": {"threshold": RUN_UP, **stat(d[d.past >= RUN_UP])}, "drop": {"threshold": DROP, **stat(d[d.past <= DROP])}}


def base_vol() -> dict:
    """Does a jumpy half-year predict the next one? Top third of its market by price swings."""
    hit = n = 0
    for m, f in _all_weekly().items():
        v = _vol(f)
        rank = v.rank(axis=1, pct=True)
        for t in rank.index[HALF::HALF][:-1]:
            a, b = rank.loc[t], rank.shift(-HALF).loc[t]
            ok = a.notna() & b.notna() & (a > 2 / 3)
            n += int(ok.sum())
            hit += int((b[ok] > 2 / 3).sum())
    return {"source": "weekly prices, six markets, five years", "cases": n, "stayed_pct": round(hit / n * 100, 1), "plain_pct": 33.3}


def base() -> dict:
    out = {"computed": str(date.today()), "growth": base_growth(), "price": base_price(), "vol": base_vol()}
    RATES.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out


# ---------------------------------------------------------------- today: detectors

def _informative(cases: int, pct: float, plain: float) -> bool:
    return cases >= MIN_CASES and abs(pct - plain) >= MIN_GAP


def _strength(cases: int, gap: float) -> str:
    return "strong" if cases >= 50 and gap >= 20 else "medium" if gap >= 15 else "weak"


def _context() -> dict:
    companies = G.load_companies()
    edges = G.load_edges()
    w = json.loads((G.DATA / "prices_weekly.json").read_text())
    return {"companies": companies, "edges": edges,
            "profiles": json.loads((G.DATA / "profiles.json").read_text()),
            "weekly": pd.DataFrame(w["series"], index=pd.to_datetime(w["dates"])).astype(float),
            "stages": json.loads((G.DATA / "stages.json").read_text()),
            "market": json.loads((G.DATA / "market.json").read_text())}


def _around(co: str, cx: dict) -> dict:
    e, c = cx["edges"], cx["companies"]
    name = lambda x: c.loc[x, "name"] if x in c.index else x
    tier = c.loc[co, "tier"]
    stage = cx["stages"]["stages"].get(tier, {})
    return {"company": co, "name": name(co), "tier": tier, "stage": stage.get("title", tier), "stage_rhythm": stage.get("badge", ""),
            "suppliers": [name(x) for x in e[e.customer == co].supplier.unique()][:6],
            "customers": [name(x) for x in e[e.supplier == co].customer.unique()][:6]}


def _open_changes(cx: dict, tier: str) -> list[dict]:
    return [{"title": ch[3], "detail": ch[4], "status": ch[6], "source": ch[7]} for ch in cx["market"]["changes"] if ch[2] == tier][:3]


def detect_growth(cx: dict, rates: dict) -> tuple[list[dict], int]:
    cards, quiet = [], 0
    for co in cx["companies"].index:
        g = (cx["profiles"].get(co, {}).get("info") or {}).get("revenueGrowth")
        if co not in cx["companies"].index or cx["companies"].loc[co, "tier"] == "control" or g is None:
            continue
        g *= 100
        b = next((b for b in rates["growth"]["buckets"] if g >= b["lo"] and g < (b["hi"] or 1e9)), None)
        if not b:
            continue
        if not _informative(b["cases"], b["slowed_pct"], rates["growth"]["slowed_all_pct"]):
            quiet += 1
            continue
        cards.append({"detector": "growth", **_around(co, cx),
                      "see": {"growth_pct": round(g, 1)},
                      "past": {"bucket_lo": b["lo"], "bucket_hi": b["hi"], "cases": b["cases"], "companies": b["companies"],
                               "slowed_pct": b["slowed_pct"], "halved_pct": b["halved_pct"], "median_later": b["median_later"],
                               "plain_pct": rates["growth"]["slowed_all_pct"], "source": rates["growth"]["source"]},
                      "strength": _strength(b["cases"], b["slowed_pct"] - rates["growth"]["slowed_all_pct"]),
                      "claim": {"metric": "revenue_growth_pct", "op": "<", "value": round(g, 1), "weeks": YEAR},
                      "refute": _open_changes(cx, cx["companies"].loc[co, "tier"])})
    return cards, quiet


def detect_price(cx: dict, rates: dict) -> tuple[list[dict], int]:
    cards, quiet = [], 0
    rel = _rel(cx["weekly"], YEAR).iloc[-1]
    plain = rates["price"]["all"]["beat_index_pct"]
    for co, r in rel.items():
        if co not in cx["companies"].index or not np.isfinite(r):
            continue
        kind = "run_up" if r >= RUN_UP else "drop" if r <= DROP else None
        if not kind:
            continue
        b = rates["price"][kind]
        if not _informative(b["cases"], b["beat_index_pct"], plain):
            quiet += 1
            continue
        up = b["beat_index_pct"] > plain
        cards.append({"detector": "price_" + kind, **_around(co, cx),
                      "see": {"rel_year_pct": round(float(r), 1), "index": cx["market"].get("index_name", "")},
                      "past": {"cases": b["cases"], "companies": b["companies"], "beat_index_pct": b["beat_index_pct"],
                               "median_next": b["median_next"], "plain_pct": plain, "source": rates["price"]["source"]},
                      "strength": _strength(b["cases"], abs(b["beat_index_pct"] - plain)),
                      "claim": {"metric": "rel_price_pct", "op": ">" if up else "<", "value": 0, "weeks": HALF},
                      "refute": _open_changes(cx, cx["companies"].loc[co, "tier"])})
    return cards, quiet


def detect_vol(cx: dict, rates: dict) -> tuple[list[dict], int]:
    b = rates["vol"]
    v = _vol(cx["weekly"]).iloc[-1].dropna()
    v = v[[c for c in v.index if c in cx["companies"].index]]
    top = v[v.rank(pct=True) > 2 / 3].sort_values(ascending=False)
    if not _informative(b["cases"], b["stayed_pct"], b["plain_pct"]):
        return [], len(top)
    cut = float(v.quantile(2 / 3))
    return [{"detector": "vol", **_around(co, cx),
             "see": {"vol_pct": round(float(x), 1), "market_median_vol_pct": round(float(v.median()), 1)},
             "past": {"cases": b["cases"], "stayed_pct": b["stayed_pct"], "plain_pct": b["plain_pct"], "source": b["source"]},
             "strength": _strength(b["cases"], b["stayed_pct"] - b["plain_pct"]),
             "claim": {"metric": "vol_top_third", "op": "=", "value": 1, "weeks": HALF, "cut_now": round(cut, 1)},
             "refute": []} for co, x in top.head(3).items()], 0      # the three jumpiest only: the rest add nothing new


def detect_dates(cx: dict) -> list[dict]:
    """Dated changes that come due soon. Not a forecast: a date, who stands next to it, and the source."""
    today, cards = date.today(), []
    c = cx["companies"]
    for ch in cx["market"]["changes"]:
        try:
            d = datetime.strptime(str(ch[5])[:7], "%Y-%m").date()
        except ValueError:
            continue
        end = (d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)     # last day of that month
        if not (today <= end <= today + timedelta(days=DEADLINE_DAYS)):
            continue
        tier = ch[2]
        stage = cx["stages"]["stages"].get(tier, {})
        cards.append({"detector": "date", "company": None, "name": None, "tier": tier, "stage": stage.get("title", tier),
                      "stage_rhythm": stage.get("badge", ""), "suppliers": [], "customers": [],
                      "exposed": list(c[c.tier == tier].name)[:8],
                      "see": {"title": ch[3], "detail": ch[4], "month": str(ch[5])[:7], "status": ch[6], "kind": ch[0], "effect": ch[1],
                              "source": ch[7], "verified": bool(ch[8]) if len(ch) > 8 else False},
                      "past": None, "strength": "date", "claim": None, "refute": []})
    return cards


def market_growth(cards: list[dict], cx: dict, rates: dict) -> list[dict]:
    """When many companies are in the same state it is one story about the market, not thirty about companies."""
    g = sorted((k for k in cards if k["detector"] == "growth"), key=lambda k: -k["see"]["growth_pct"])
    mapped = int((cx["companies"]["tier"] != "control").sum())
    if len(g) < max(5, mapped * 0.15):
        return []
    stages: dict[str, int] = {}
    for k in g:
        stages[k["stage"]] = stages.get(k["stage"], 0) + 1
    return [{"detector": "market_growth", "company": None, "name": None, "tier": None, "stage": "", "stage_rhythm": "",
             "suppliers": [], "customers": [], "strength": "strong", "claim": None, "refute": [],
             "see": {"count": len(g), "mapped": mapped, "median_growth_pct": round(float(np.median([k["see"]["growth_pct"] for k in g])), 1),
                     "fastest": [[k["name"], k["see"]["growth_pct"]] for k in g[:5]],
                     "by_stage": sorted(stages.items(), key=lambda x: -x[1])},
             "past": {"buckets": rates["growth"]["buckets"], "plain_pct": rates["growth"]["slowed_all_pct"],
                      "source": rates["growth"]["source"]}}]


def _choose(cards: list[dict], per_kind: int = 3) -> None:
    """What the page shows first. Everything is still written to the ledger and listed behind 'all claims'."""
    seen: dict[str, int] = {}
    for k in sorted(cards, key=lambda k: -abs(next(iter(k["see"].values()))) if k["company"] else 0):
        if not k["company"]:
            k["show"] = True
            continue
        if k["detector"] == "growth" and (k["past"]["bucket_lo"] < 50):
            k["show"] = False
            continue
        seen[k["detector"]] = seen.get(k["detector"], 0) + 1
        k["show"] = seen[k["detector"]] <= per_kind


def detect() -> dict:
    if not RATES.exists():
        base()
    rates = json.loads(RATES.read_text())
    cx = _context()
    cards, quiet = [], 0
    for fn in (detect_growth, detect_price, detect_vol):
        c, q = fn(cx, rates)
        cards += c
        quiet += q
    cards += detect_dates(cx)
    cards += market_growth(cards, cx, rates)
    _choose(cards)
    order = {"market_growth": 0, "date": 1, "growth": 2, "price_run_up": 3, "price_drop": 3, "vol": 4}
    cards.sort(key=lambda k: (not k["show"], order[k["detector"]], -abs(next(iter(k["see"].values()))) if k["company"] else 0))
    as_of = str(cx["weekly"].index[-1].date())
    logged = 0
    for k in cards:
        k["id"] = f"{k['detector']}:{k['company'] or k['see'].get('title', G.MARKET)}"
        k["as_of"] = as_of
        if k["claim"]:
            k["claim"]["due"] = str(cx["weekly"].index[-1].date() + timedelta(weeks=k["claim"]["weeks"]))
            logged += _log_claim(k)
            k["claim"]["ledger"] = _open_claim(k["id"])
    from . import writer
    writer.write_all(cards, cx["market"])
    out = {"market": G.MARKET, "as_of": as_of, "rates_computed": rates["computed"], "checked_nothing_to_say": quiet,
           "rules": {"min_cases": MIN_CASES, "min_gap_points": MIN_GAP}, "record": record(), "cards": cards}
    G.RESULTS.mkdir(parents=True, exist_ok=True)
    (G.RESULTS / "inference.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"{G.MARKET}: {len(cards)} cards ({quiet} states checked with nothing to say), {logged} new claims; "
          f"writer: {writer.MODE}")
    return out


# ---------------------------------------------------------------- the ledger: claims and their scores

def _read(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def _scored() -> set[str]:
    return {r["claim"] for r in _read(SCORES)}


def _open_claim(card_id: str) -> dict | None:
    done = _scored()
    for r in reversed(_read(CLAIMS)):
        if r["card"] == card_id and r["hash"] not in done:
            return {"hash": r["hash"], "created": r["created_utc"][:10], "due": r["due"]}
    return None


def _log_claim(card: dict) -> int:
    """One open claim per card: while it is open nothing new is written, so a claim cannot be restated after the fact."""
    if _open_claim(card["id"]):
        return 0
    from .ledger import _append
    LEDGER.mkdir(parents=True, exist_ok=True)
    _append(CLAIMS, {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "card": card["id"],
                     "detector": card["detector"], "company": card["company"], "as_of": card["as_of"], "see": card["see"],
                     "claim": {k: v for k, v in card["claim"].items() if k != "ledger"}, "due": card["claim"]["due"],
                     "history": {k: card["past"][k] for k in card["past"] if k != "source"}})
    return 1


def _outcome(r: dict, cx: dict) -> float | None:
    co, m, w = r["company"], r["claim"]["metric"], cx["weekly"]
    if m == "revenue_growth_pct":
        g = (cx["profiles"].get(co, {}).get("info") or {}).get("revenueGrowth")
        return None if g is None else round(g * 100, 1)
    if co not in w.columns:
        return None
    win = w.loc[pd.Timestamp(r["as_of"]):pd.Timestamp(r["due"])]
    if len(win) < r["claim"]["weeks"] * 0.9:
        return None
    if m == "rel_price_pct":
        return round(float((win[co].iloc[-1] / win[co].iloc[0]) / (win["_MARKET"].iloc[-1] / win["_MARKET"].iloc[0]) - 1) * 100, 1)
    if m == "vol_top_third":
        v = (np.log(win.drop(columns="_MARKET")).diff().std() * np.sqrt(52) * 100).dropna()
        return float(v.rank(pct=True).get(co, np.nan) > 2 / 3)
    return None


def score() -> None:
    cx, done, n = _context(), _scored(), 0
    from .ledger import _append
    for r in _read(CLAIMS):
        if r["hash"] in done or date.fromisoformat(r["due"]) > date.today():
            continue
        actual = _outcome(r, cx)
        if actual is None:
            continue
        op, val = r["claim"]["op"], r["claim"]["value"]
        hit = actual < val if op == "<" else actual > val if op == ">" else actual == val
        _append(SCORES, {"claim": r["hash"], "scored_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "actual": actual, "hit": bool(hit)})
        n += 1
    print(f"{G.MARKET}: {n} claims scored; {len(_read(SCORES))} scored in total")


def record() -> dict:
    from .ledger import verify
    c, s = _read(CLAIMS), _read(SCORES)
    by = {}
    kind = {r["hash"]: r["detector"] for r in c}
    for r in s:
        d = by.setdefault(kind.get(r["claim"], "?"), {"scored": 0, "hit": 0})
        d["scored"] += 1
        d["hit"] += int(r["hit"])
    return {"claims": len(c), "scored": len(s), "hit": sum(int(r["hit"]) for r in s), "by_detector": by,
            "next_due": min((r["due"] for r in c if r["hash"] not in _scored()), default=None),
            "chain_intact": verify(CLAIMS) and verify(SCORES)}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "base":
        print(json.dumps(base(), indent=1, ensure_ascii=False))
    elif cmd == "report":
        print(json.dumps(record(), indent=1, ensure_ascii=False))
    else:
        {"detect": detect, "score": score}[cmd]()
