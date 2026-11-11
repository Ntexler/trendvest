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
        nodes.append({"id": cid, "name": c["name"], "ticker": c["ticker"], "country": c["country"],
                      "tier": c["tier"], "segment": c["segment"], "sites": c["sites"],
                      "info": p["info"], "holders": hs, "people": ppl, "ev": ev})
    E = [{"s": e.supplier, "t": e.customer, "what": e.product, "share": str(e.share_pct).replace(".0", ""),
          "year": str(e.share_year).replace(".0", ""), "type": e.evidence_type, "conf": e.confidence,
          "url": e.source_url, "note": e.note} for e in edges.itertuples()]
    EV = [{"id": e.id, "name": e.name, "ts": e.ts_utc, "loc": e.location, "hit": e.hit.split(";"),
           "quality": e.quality, "confounder": e.confounder, "url": e.source_url, "note": e.note}
          for e in events.itertuples() if e.quality != "avoid"]
    return {"tiers": TIERS, "nodes": nodes, "edges": E, "events": EV}


def main() -> None:
    data = build()
    tpl = (HERE / "map" / "template.html").read_text()
    out = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False))
    (HERE / "map" / "chip_map.html").write_text(out)
    n_links = sum(1 for n in data["nodes"] for p in n["people"] if p["also"])
    print(len(data["nodes"]), "nodes,", len(data["edges"]), "edges,", len(data["events"]), "events;",
          n_links, "person name matches across companies;", len(out) // 1024, "KB")


if __name__ == "__main__":
    main()
