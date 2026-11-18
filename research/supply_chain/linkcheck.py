"""Free, price-based checks of the map itself (many more data points than rare disasters).

1. Do linked companies move together more than unlinked ones?  Weekly abnormal returns
   (weekly sidesteps time-zone asynchrony), with the sector-wide move removed.
2. "Customer momentum" (Cohen & Frazzini 2008) in miniature: does this week's abnormal
   return of a company's customers predict the company's abnormal return NEXT week?
   Compared against the same test with randomly re-wired links.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import graph as G
from . import markets as MK


def weekly_abnormal(prices: pd.DataFrame, companies: pd.DataFrame) -> pd.DataFrame:
    wk = prices.resample("W-FRI").last()
    out = {}
    for cid, c in companies.iterrows():
        t, b = c["ticker"], MK.benchmark(c["ticker"])
        if t not in wk or b not in wk:
            continue
        r, rm = np.log(wk[t]).diff(), np.log(wk[b]).diff()
        beta = (r.rolling(104, min_periods=40).cov(rm) / rm.rolling(104, min_periods=40).var()).shift(1)
        out[cid] = r - beta * rm
    ar = pd.DataFrame(out)
    ar = ar.sub(ar.mean(axis=1), axis=0)      # remove the common (sector-wide) move each week
    return ar.dropna(how="all")


def pair_comovement(ar: pd.DataFrame, edges: pd.DataFrame) -> dict:
    corr = ar.corr(min_periods=100)
    linked = {tuple(sorted(p)) for p in zip(edges.supplier, edges.customer)
              if p[0] in corr and p[1] in corr}
    ids = list(corr.columns)
    lv, uv = [], []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            v = corr.loc[a, b]
            if np.isfinite(v):
                (lv if tuple(sorted((a, b))) in linked else uv).append(v)
    lv, uv = np.array(lv), np.array(uv)
    return {"linked_pairs": len(lv), "unlinked_pairs": len(uv),
            "mean_corr_linked": float(lv.mean()), "mean_corr_unlinked": float(uv.mean()),
            "share_of_unlinked_below_linked_mean": float((uv < lv.mean()).mean())}


def _lead_lag_stat(ar: pd.DataFrame, partners: dict[str, list[str]]) -> tuple[float, float, int]:
    """Fama-MacBeth style: each week, cross-sectional corr between partners' AR(t) and own AR(t+1)."""
    sig = pd.DataFrame({c: ar[[p for p in ps if p in ar]].mean(axis=1)
                        for c, ps in partners.items() if c in ar and any(p in ar for p in ps)})
    nxt = ar[sig.columns].shift(-1)
    cs = []
    for d in sig.index:
        x, y = sig.loc[d], nxt.loc[d]
        ok = x.notna() & y.notna()
        if ok.sum() >= 8:
            cs.append(np.corrcoef(x[ok], y[ok])[0, 1])
    cs = np.array(cs)
    return float(cs.mean()), float(cs.mean() / (cs.std(ddof=1) / np.sqrt(len(cs)))), len(cs)


def customer_momentum(ar: pd.DataFrame, edges: pd.DataFrame, n_shuffle: int = 200, seed: int = 3) -> dict:
    cust = edges.groupby("supplier")["customer"].apply(list).to_dict()   # my customers
    supp = edges.groupby("customer")["supplier"].apply(list).to_dict()   # my suppliers
    m_c, t_c, n = _lead_lag_stat(ar, cust)
    m_s, t_s, _ = _lead_lag_stat(ar, supp)
    rng = np.random.default_rng(seed)
    ids = list(ar.columns)
    sims = []
    for _ in range(n_shuffle):
        fake = {s: list(rng.choice([i for i in ids if i != s], size=len(c), replace=False))
                for s, c in cust.items()}
        sims.append(_lead_lag_stat(ar, fake)[0])
    sims = np.array(sims)
    return {"weeks": n,
            "customers_lead_suppliers_corr": m_c, "customers_lead_suppliers_t": t_c,
            "suppliers_lead_customers_corr": m_s, "suppliers_lead_customers_t": t_s,
            "random_links_corr_mean": float(sims.mean()), "random_links_corr_sd": float(sims.std()),
            "share_of_random_maps_beating_real": float((sims >= m_c).mean())}
