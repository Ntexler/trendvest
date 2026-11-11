"""Build the clickable supply-chain map (a single self-contained HTML page) from the CSV data.

    python -m research.supply_chain.build_map   ->  research/supply_chain/map/chip_map.html
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

from . import graph as G

HERE = Path(__file__).parent
TEMPLATE, OUTPUT = "app_template.html", "chip_map.html"   # the template is market-agnostic
TIERS = ["materials", "subsystems", "equipment", "manufacturing", "packaging", "design", "systems"]
INDEX_GIANTS = ("vanguard", "blackrock", "state street", "geode", "fmr", "jpmorgan", "morgan stanley",
                "norges", "capital", "invesco", "northern trust", "price (t.rowe)", "bank of america")


def norm_person(name: str) -> str:
    n = re.sub(r"\b(mr|ms|mrs|dr|prof)\.?\s", "", name.lower())
    n = re.sub(r"\b(ph\.?d\.?|cpa|j\.?d\.?|m\.?b\.?a\.?|b\.?sc\.?|m\.?sc\.?|jr\.?|iii|ii)\b", "", n)
    parts = sorted(p for p in re.split(r"[^a-z]+", n) if len(p) > 1)
    return " ".join(parts)


def build() -> dict:
    companies = G.load_companies()
    chain = companies[companies["tier"] != "control"]
    edges = G.load_edges().fillna("")
    profiles = json.loads((HERE / "data" / "profiles.json").read_text())
    events = pd.read_csv(HERE / "data" / "events.csv", comment="#").fillna("")
    res_path = HERE / "results" / "event_company.csv"
    res = pd.read_csv(res_path) if res_path.exists() else pd.DataFrame()

    people = defaultdict(set)      # normalised person -> companies
    holders = defaultdict(set)
    for cid, p in profiles.items():
        for o in p["officers"] + p["insiders"]:
            k = norm_person(o["name"])
            if len(k.split()) >= 2:
                people[k].add(cid)
        for h in p["holders"]:
            holders[h["name"]].add(cid)

    pulses = json.loads((HERE / "data" / "pulses.json").read_text())
    content = json.loads((HERE / "data" / "stages.json").read_text())
    il = re.compile(r"israel|rehovot|migdal|kiryat|nes ziona", re.I)
    prices = json.loads((HERE / "data" / "prices_weekly.json").read_text())
    news = json.loads((HERE / "data" / "news.json").read_text())
    news_he = json.loads((HERE / "data" / "market.json").read_text()).get("news_he", {})
    wres_path = HERE / "results" / "event_company_weighted.csv"
    wres = pd.read_csv(wres_path) if wres_path.exists() else pd.DataFrame()
    nodes = []
    for cid, c in chain.iterrows():
        p = profiles.get(cid, {"info": {}, "holders": [], "officers": [], "insiders": []})
        ppl, seen = [], set()
        for o in p["officers"] + p["insiders"]:
            k = norm_person(o["name"])
            if k in seen:
                continue
            seen.add(k)
            ppl.append({"n": o["name"], "t": o.get("title") or "",
                        "also": sorted(people[k] - {cid}) if k in people else []})
        hs = [{"n": h["name"], "p": h["pct"],
               "giant": any(g in h["name"].lower() for g in INDEX_GIANTS),
               "also": len(holders[h["name"]]) - 1} for h in p["holders"]]
        ev = {}
        if len(res):
            for _, r in res[res.company == cid].iterrows():
                ev[r["event"]] = {"role": r["role"], "d0": round(r["pct0"], 1), "d3": round(r["pct3"], 1),
                                  "d10": round(r["pct10"], 1), "day0": str(r["day0"])[:10]}
        pulse = {k: v for k, v in pulses["sec"].get(cid, {}).items() if k not in ("rev_q", "sec_name")}
        rq = pulses["sec"].get(cid, {}).get("rev_q")
        if rq:      # quarterly revenue for the pane under the price chart: [[period end, USD bn], ...]
            pulse["rev"] = [[k, round(v / 1e9, 2)] for k, v in list(rq.items())[-20:]]
        elif cid in pulses["monthly"]:
            pulse["rev"] = [[k + "-28", round(v / 1e9, 1)] for k, v in pulses["monthly"][cid]["series"].items()]
            pulse["rev_unit"] = "TWD"
        if cid in pulses["monthly"]:
            m = pulses["monthly"][cid]
            pulse["monthly"] = {"last": m["last_month"], "yoy": m["yoy_pct"],
                                "series": [round(v / 1e9, 2) for v in m["series"].values()],
                                "first": next(iter(m["series"]))}
        if len(wres):   # role when shocks pass only through material links
            for _, r in wres[wres.company == cid].iterrows():
                if r["event"] in ev:
                    ev[r["event"]]["w"] = r["role"]
        nodes.append({"id": cid, "name": c["name"], "ticker": c["ticker"], "country": c["country"],
                      "tier": c["tier"], "segment": c["segment"], "sites": c["sites"],
                      "israel": c["country"] == "IL" or bool(il.search(str(c["sites"]))),
                      "info": p["info"], "holders": hs, "people": ppl, "ev": ev, "pulse": pulse,
                      "px": prices["series"].get(cid, []),
                      "news": [dict(n, he=news_he.get(n["t"])) for n in news.get(cid, [])]})
    E = [{"s": e.supplier, "t": e.customer, "what": e.product, "share": str(e.share_pct).replace(".0", ""),
          "year": str(e.share_year).replace(".0", ""), "type": e.evidence_type, "conf": e.confidence,
          "crit": str(e.critical) in ("1", "1.0"), "url": e.source_url, "note": e.note} for e in edges.itertuples()]
    EV = [{"id": e.id, "name": e.name, "ts": e.ts_utc, "loc": e.location, "hit": e.hit.split(";"),
           "quality": e.quality, "confounder": e.confounder, "url": e.source_url, "note": e.note}
          for e in events.itertuples() if e.quality != "avoid"]
    agg = {}
    for t in TIERS:
        ns = [n for n in nodes if n["tier"] == t]
        tot = lambda k: sum(n["info"].get(k) or 0 for n in ns)          # noqa: E731
        gm = sorted(n["info"]["grossMargins"] for n in ns if n["info"].get("grossMargins") is not None)
        countries = defaultdict(int)
        for n in ns:
            countries[n["country"]] += 1
        agg[t] = {"n": len(ns), "countries": sorted(countries.items(), key=lambda x: -x[1]),
                  "employees": tot("fullTimeEmployees"), "revenue": tot("revenueUSD"), "net": tot("netIncomeUSD"),
                  "gm": gm[len(gm) // 2] if gm else None,
                  "top": [n["id"] for n in sorted(ns, key=lambda n: -(n["info"].get("revenueUSD") or 0))[:6]]}
    base = {}
    rp = HERE / "results" / "event_role_weighted.csv"
    if rp.exists():     # what happened in past events, per role: one value per event
        er = pd.read_csv(rp)
        for role, g in er.groupby("role"):
            v = g["pct3"].dropna()
            base[role] = {"n": int(len(v)), "mean": round(float(v.mean()), 1), "min": round(float(v.min()), 1),
                          "max": round(float(v.max()), 1), "fell": int((v < 0).sum()),
                          "d10": round(float(g["pct10"].mean()), 1),
                          "by_event": {e: round(float(x), 1) for e, x in zip(g["event"], g["pct3"])}}
    market = json.loads((HERE / "data" / "market.json").read_text())
    market.pop("news_he", None)
    content["sources"] = {**content["sources"], **market.pop("sources")}
    return {"tiers": TIERS, "nodes": nodes, "edges": E, "events": EV, "agg": agg, "market": market,
            "base": base, "dates": prices["dates"], "mkt": prices["series"]["_MARKET"], **content}


def main() -> None:
    data = build()
    tpl = (HERE / "map" / TEMPLATE).read_text()
    out = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False)).replace("__TITLE__", "מפת שרשרת השבבים")
    (HERE / "map" / OUTPUT).write_text(out)
    poster = (HERE / "map" / "infographic_template.html").read_text()
    (HERE / "map" / "stock_story.html").write_text(poster.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False)))
    n_links = sum(1 for n in data["nodes"] for p in n["people"] if p["also"])
    print(len(data["nodes"]), "nodes,", len(data["edges"]), "edges,", len(data["events"]), "events;",
          n_links, "person name matches across companies;", len(out) // 1024, "KB")


if __name__ == "__main__":
    main()
