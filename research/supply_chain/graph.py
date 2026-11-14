"""The supply-chain map: companies (nodes) and supplier->customer links (edges),
both kept as plain CSV so they can be reviewed and edited by hand.

Every edge carries its evidence (source URL + date) so a backtest can use only the
links that were already documented before the event it is testing (point-in-time).
"""

from __future__ import annotations

import os
from collections import deque
from pathlib import Path

import pandas as pd

BASE = Path(__file__).parent
MARKET = os.environ.get("MARKET", "chips")     # one folder per market: data/<market>/, results/<market>/
DATA = BASE / "data" / MARKET
RESULTS = BASE / "results" / MARKET


def market() -> dict:
    import json
    return json.loads((DATA / "market.json").read_text())


def load_companies() -> pd.DataFrame:
    return pd.read_csv(DATA / "companies.csv", comment="#").set_index("id")


def load_edges(as_of: str | None = None, min_confidence: str = "low") -> pd.DataFrame:
    e = pd.read_csv(DATA / "edges.csv", comment="#")
    rank = {"low": 0, "medium": 1, "high": 2}
    e = e[e["confidence"].map(rank) >= rank[min_confidence]]
    if as_of is not None:
        # keep links known to exist at the time: structural links have valid_from, others
        # fall back to the evidence year
        start = pd.to_numeric(e["valid_from"], errors="coerce").fillna(
            pd.to_numeric(e["evidence_year"], errors="coerce"))
        e = e[start.fillna(0) <= pd.Timestamp(as_of).year]
    return e


def events() -> pd.DataFrame:
    ev = pd.read_csv(DATA / "events.csv", comment="#")
    ev["ts_utc"] = pd.to_datetime(ev["ts_utc"], utc=True)
    return ev.set_index("id")


def material_only(edges: pd.DataFrame, min_share: float = 10.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split links by the direction in which a shock can travel.

    downstream (supplier hit -> customer hurt): only links where the customer depends
        heavily on that supplier (critical = 1)
    upstream   (customer hit -> supplier hurt): only links where the customer is at
        least ``min_share`` percent of the supplier's revenue
    """
    down = edges[pd.to_numeric(edges["critical"], errors="coerce").fillna(0) == 1]
    up = edges[pd.to_numeric(edges["share_pct"], errors="coerce").fillna(0) >= min_share]
    return down, up


def roles(hit: list[str], edges: pd.DataFrame, companies: pd.DataFrame,
          max_hops: int = 2, weighted: bool = False) -> dict[str, str]:
    """Mechanical, pre-registered role of every company relative to the hit companies.

    hit            the companies whose own facilities/supply were disrupted
    down1, down2   customers of the hit companies, and their customers
    up1, up2       suppliers of the hit companies, and their suppliers
    rival          same segment as a hit company, not hit itself and not linked within max_hops
    control        everything else in the universe
    Nearest relation wins; downstream beats upstream on ties.
    """
    e_down, e_up = material_only(edges) if weighted else (edges, edges)
    down = e_down.groupby("supplier")["customer"].apply(set).to_dict()
    up = e_up.groupby("customer")["supplier"].apply(set).to_dict()

    def bfs(adj):
        dist, q = {h: 0 for h in hit}, deque(hit)
        while q:
            n = q.popleft()
            if dist[n] >= max_hops:
                continue
            for m in adj.get(n, ()):
                if m not in dist:
                    dist[m] = dist[n] + 1
                    q.append(m)
        return dist

    dd, du = bfs(down), bfs(up)
    hit_segments = set(companies.loc[[h for h in hit if h in companies.index], "segment"])
    out = {}
    for c in companies.index:
        if c in hit:
            out[c] = "hit"
        elif c in dd and dd[c] <= du.get(c, 99):
            out[c] = f"down{dd[c]}"
        elif c in du:
            out[c] = f"up{du[c]}"
        elif companies.loc[c, "segment"] in hit_segments:
            out[c] = "rival"
        else:
            out[c] = "control"
    return out


# Expected direction of the abnormal return, fixed BEFORE looking at any result.
EXPECTED_SIGN = {"hit": -1, "down1": -1, "down2": -1, "up1": -1, "up2": -1, "rival": +1, "control": 0}
