"""Check a researched market before anything is computed from it.

    MARKET=energy python -m research.supply_chain.validate
"""

from __future__ import annotations

import json
import sys

import pandas as pd

from . import graph as G


def problems() -> list[str]:
    out: list[str] = []
    need = ["companies.csv", "edges.csv", "events.csv", "stages.json", "market.json"]
    missing = [f for f in need if not (G.DATA / f).exists()]
    if missing:
        return [f"missing files: {', '.join(missing)}"]
    c = G.load_companies()
    e = pd.read_csv(G.DATA / "edges.csv", comment="#")
    ev = pd.read_csv(G.DATA / "events.csv", comment="#")
    st = json.loads((G.DATA / "stages.json").read_text())
    m = json.loads((G.DATA / "market.json").read_text())
    ids = set(c.index)
    if c.index.duplicated().any():
        out.append(f"duplicate company ids: {list(c.index[c.index.duplicated()])}")
    tiers = m.get("tiers", [])
    bad_tier = sorted(set(c["tier"]) - set(tiers) - {"control"})
    if bad_tier:
        out.append(f"tiers in companies.csv not listed in market.json: {bad_tier}")
    for t in tiers:
        if t not in st["stages"]:
            out.append(f"stage '{t}' missing from stages.json")
        for k in ("plain", "time"):
            if t not in m.get(k, {}):
                out.append(f"market.json '{k}' has no entry for stage '{t}'")
    unknown = sorted((set(e["supplier"]) | set(e["customer"])) - ids)
    if unknown:
        out.append(f"edges use unknown ids: {unknown}")
    for col in ("critical", "confidence", "share_pct", "valid_from", "evidence_year"):
        if col not in e:
            out.append(f"edges.csv lacks column {col}")
    if "confidence" in e and not set(e["confidence"]) <= {"high", "medium", "low"}:
        out.append(f"unexpected confidence values: {sorted(set(e['confidence']))}")
    for _, r in ev.iterrows():
        bad = [h for h in str(r["hit"]).split(";") if h not in ids]
        if bad:
            out.append(f"event {r['id']} hits unknown ids: {bad}")
        if pd.isna(pd.to_datetime(r["ts_utc"], utc=True, errors="coerce")):
            out.append(f"event {r['id']} has an unreadable timestamp: {r['ts_utc']}")
    if not set(ev["quality"]) <= {"best", "ok", "avoid"}:
        out.append(f"unexpected event quality values: {sorted(set(ev['quality']))}")
    src = {**st.get("sources", {}), **m.get("sources", {})}
    used = set()
    for s in st["stages"].values():
        used |= {x[-1] for x in s["facts"]} | {x[-1] for x in s["pulse"]} | {x[-1] for x in s["choke"]}
    used |= {x[2] for x in st.get("clock", [])} | {x[4] for x in st.get("calendar", []) if x[4]}
    used |= {x[4] for x in m.get("lifecycle", [])} | {x[4] for x in m.get("history", [])} | {x[7] for x in m.get("changes", [])}
    used |= {x[2] for x in m.get("kpis", [])}
    lost = sorted(k for k in used if k and k not in src)
    if lost:
        out.append(f"source keys used but not defined: {lost}")
    ev_ids = set(ev["id"])
    bad_ev = sorted({h[5] for h in m.get("history", []) if h[5] and h[5] not in ev_ids})
    if bad_ev:
        out.append(f"history points to unknown event ids: {bad_ev}")
    for k in ("name", "intro", "definition", "chain_title", "index_name", "index_ticker", "kpis", "lifecycle", "history", "changes"):
        if not m.get(k):
            out.append(f"market.json lacks '{k}'")
    return out


if __name__ == "__main__":
    p = problems()
    print(f"{G.MARKET}: " + ("ok" if not p else f"{len(p)} problem(s)"))
    for x in p:
        print(" -", x)
    sys.exit(1 if p else 0)
