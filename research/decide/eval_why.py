"""Jev vs. the keyword rules on the headlines we already have (results/<market>/why.json). Run once the key is set.

For each big move with headlines and no official report/chain event: ask Jev, keep the rules' answer, and write
  results/jev_eval.json   agreement, how sure Jev was, latency, cost estimate, fallbacks
  results/jev_eval.csv    every day where they disagree, with the headlines, for a person to judge who was right
A small sample is enough to decide (default 200 days, chosen at random with a fixed seed).

    TYPESAFE_API_KEY=... python -m research.decide.eval_why [--n 200]
"""
from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

from research.decide.why_kind import classify, client
from research.supply_chain.why import kind as rules_kind

BASE = Path(__file__).parents[1] / "supply_chain"
OUT = BASE / "results"


def days() -> list[tuple]:
    out = []
    for f in sorted((BASE / "results").glob("*/why.json")):
        names = {}
        comp = BASE / "data" / f.parent.name / "companies.csv"
        if comp.exists():
            for r in csv.DictReader(line for line in comp.open() if not line.startswith("#")):
                names[r["id"]] = r["name"].split(" (")[0]
        for cid, moves in json.loads(f.read_text()).items():
            for m in moves:
                if m.get("news") and not m.get("earnings") and not (m.get("event") or {}).get("linked"):
                    out.append((f.parent.name, cid, names.get(cid, cid), m))
    return out


def main() -> None:
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 200
    j = client()
    if not j.enabled:
        sys.exit("Jev is off: set TYPESAFE_API_KEY (or TYPESAFE_VIA_PROXY=1 where the proxy adds the key).")
    D = days()
    random.Random(7).shuffle(D)
    rows, fall = [], 0
    for market, cid, name, m in D[:n]:
        rk = rules_kind(m["news"])
        c = classify(name, m["news"], rk, j)
        if c["source"] != "jev":
            fall += 1
            continue
        rows.append({"market": market, "company": name, "date": m["date"], "move": m.get("ret"), "rules": rk, "jev": c["kind"],
                     "confidence": c["confidence"], "about": c["about"], "tone": c["tone"],
                     "headlines": " | ".join(h["t"] for h in m["news"][:5])})
    agree = sum(r["rules"] == r["jev"] for r in rows)
    conf = sorted(r["confidence"] for r in rows)
    tone_ok = [r for r in rows if r["move"] is not None and r["tone"] is not None and abs(r["tone"]) >= 0.5]
    res = {"days_available": len(D), "asked": min(n, len(D)), "answered": len(rows), "fell_back": fall,
           "agree_with_rules_pct": round(agree / len(rows) * 100, 1) if rows else None,
           "jev_kinds": {k: sum(r["jev"] == k for r in rows) for k in ("report", "analyst", "deal", "regulation", "news")},
           "rules_kinds": {k: sum(r["rules"] == k for r in rows) for k in ("report", "analyst", "deal", "regulation", "news")},
           "median_confidence": conf[len(conf) // 2] if conf else None,
           "not_about_company_pct": round(sum(r["about"] < 0.4 for r in rows) / len(rows) * 100, 1) if rows else None,
           "tone_matches_move_direction_pct": round(sum((r["tone"] > 0) == (r["move"] > 0) for r in tone_ok) / len(tone_ok) * 100, 1) if tone_ok else None,
           "latency_ms": {"median": sorted(j.ms)[len(j.ms) // 2], "max": max(j.ms)} if j.ms else None,
           "note": "Agreement is not accuracy: read jev_eval.csv and mark who was right on the days they disagree."}
    (OUT / "jev_eval.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    with (OUT / "jev_eval.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]) + ["who_was_right"] if rows else ["empty"])
        w.writeheader()
        for r in rows:
            if r["rules"] != r["jev"]:
                w.writerow({**r, "who_was_right": ""})
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
