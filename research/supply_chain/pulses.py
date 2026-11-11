"""The "pulses" of the chain: how often money and goods move, measured from free data.

  monthly   Taiwan-listed companies report revenue every month (FinMind open API)
  quarterly US filers' XBRL facts at the SEC: revenue seasonality, days of inventory,
            purchase commitments, customer prepayments, remaining performance obligations
  lag       how many quarters one tier's revenue growth leads or trails another's

    python -m research.supply_chain.pulses      -> data/pulses.json
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from . import graph as G

OUT = Path(__file__).parent / "data" / "pulses.json"
UA = {"User-Agent": "TrendVestResearch/0.1 (personal research script)"}

# SEC central index keys for the US filers in the map (10-K filers only: quarterly XBRL facts)
CIK = {"AMAT": 6951, "LAM": 707549, "KLA": 319201, "TERADYNE": 97210, "ONTO": 704532, "MKS": 1049502,
       "AEIS": 927003, "UCTT": 1275014, "ICHOR": 1652535, "FORMFACTOR": 1039399, "ENTEGRIS": 1101302,
       "AXCELIS": 1113232, "INTEL": 50863, "NVDA": 1045810, "AMD": 2488, "QCOM": 804328, "AVGO": 1730168,
       "MRVL": 1835632, "MICRON": 723125, "AMKOR": 1047127, "SMCI": 1375365, "AAPL": 320193,
       "DELL": 1571996, "MSFT": 789019, "GOOGL": 1652044, "AMZN": 1018724, "META": 1326801, "TI": 97476,
       "LINDE": 1707925, "AIRPRODUCTS": 2969}
REV_TAGS = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"]
COGS_TAGS = ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"]


def taiwan_monthly(stock_id: str, tries: int = 4) -> pd.Series:
    for i in range(tries):
        s = _taiwan_monthly(stock_id)
        if len(s):
            return s
        time.sleep(8 * (i + 1))        # the open API throttles bursts
    return s


def _taiwan_monthly(stock_id: str) -> pd.Series:
    r = requests.get("https://api.finmindtrade.com/api/v4/data", timeout=40, headers=UA,
                     params={"dataset": "TaiwanStockMonthRevenue", "data_id": stock_id, "start_date": "2016-01-01"})
    d = pd.DataFrame(r.json().get("data", []))
    if d.empty:
        return pd.Series(dtype=float)
    idx = pd.to_datetime(d["revenue_year"].astype(str) + "-" + d["revenue_month"].astype(str) + "-01")
    return pd.Series(d["revenue"].to_numpy(float), index=idx).sort_index()


def _quarterly(units: list[dict]) -> pd.Series:
    """Turn 10-Q/10-K flow facts into a clean quarterly series (derive Q4 = year - 9 months)."""
    rows = [(pd.Timestamp(u["start"]), pd.Timestamp(u["end"]), float(u["val"])) for u in units if "start" in u]
    df = pd.DataFrame(rows, columns=["s", "e", "v"]).drop_duplicates(["s", "e"], keep="last")
    df["days"] = (df["e"] - df["s"]).dt.days
    q = df[df.days.between(80, 100)].set_index("e")["v"]
    for _, y in df[df.days.between(350, 380)].iterrows():
        if y["e"] in q.index:
            continue
        inside = q[(q.index > y["s"]) & (q.index < y["e"])]
        if len(inside) == 3:
            q.loc[y["e"]] = y["v"] - inside.sum()
    return q.sort_index()


def _first(facts: dict, tags: list[str]):
    best = None
    for t in tags:
        u = facts.get(t, {}).get("units", {}).get("USD")
        if u and (best is None or u[-1]["end"] > best[-1]["end"]):
            best = u
    return best


def _latest(facts: dict, tag: str):
    u = facts.get(tag, {}).get("units", {}).get("USD")
    if not u:
        return None
    last = max(u, key=lambda x: (x["end"], x.get("filed", "")))
    stale = pd.Timestamp(last["end"]) < pd.Timestamp.now() - pd.DateOffset(months=18)
    return None if stale or not last["val"] else {"value": last["val"], "date": last["end"]}


def seasonality(q: pd.Series, years: int = 8) -> dict:
    """Seasonal index per calendar quarter: revenue relative to its own centred one-year average,
    so steady growth does not masquerade as a strong fourth quarter. 100 = a normal quarter.
    A fiscal quarter is assigned to the calendar quarter that holds its middle month."""
    q = q[q.index >= q.index.max() - pd.DateOffset(years=years)]
    trend = q.rolling(4).mean().rolling(2).mean().shift(-2)      # centred 4-quarter average
    ratio = (q / trend).dropna()
    mid = ratio.index - pd.Timedelta(days=45)
    out = ratio.groupby(mid.quarter).mean()
    out = out / out.mean() * 100
    return {f"Q{k}": round(float(v), 1) for k, v in out.items()}


def sec_company(cid: str, cik: int) -> dict:
    r = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json", headers=UA, timeout=60)
    f = r.json()
    g = f["facts"].get("us-gaap", {})
    out: dict = {"sec_name": f.get("entityName")}
    rev_u, cogs_u = _first(g, REV_TAGS), _first(g, COGS_TAGS)
    if rev_u:
        q = _quarterly(rev_u)
        out["rev_q"] = {str(k.date()): v for k, v in q.tail(52).items()}
        out["seasonality"] = seasonality(q)
        if cogs_u and "InventoryNet" in g:
            c = _quarterly(cogs_u)
            inv = pd.Series({pd.Timestamp(u["end"]): float(u["val"]) for u in g["InventoryNet"]["units"]["USD"]})
            inv = inv[~inv.index.duplicated(keep="last")]
            d = (inv.reindex(c.index) / c * 91).dropna()
            if len(d):
                out["inventory_days"] = {"latest": round(float(d.iloc[-1])), "median_5y": round(float(d.tail(20).median())),
                                         "date": str(d.index[-1].date())}
    for key, tag in [("purchase_obligation", "PurchaseObligation"),
                     ("purchase_obligation_next_12m", "PurchaseObligationDueInNextTwelveMonths"),
                     ("remaining_performance_obligation", "RevenueRemainingPerformanceObligation"),
                     ("customer_prepayments", "ContractWithCustomerLiability")]:
        v = _latest(g, tag)
        if v:
            out[key] = v
    return out


def tier_lead_lag(sec: dict, companies: pd.DataFrame, max_lag: int = 4) -> dict:
    """corr(year-on-year revenue growth of tier A at quarter t, tier B at t+lag). Positive lag = A leads."""
    growth = {}
    for cid, d in sec.items():
        if "rev_q" not in d:
            continue
        q = pd.Series(d["rev_q"]).rename(index=pd.Timestamp).sort_index()
        q.index = q.index.to_period("Q").to_timestamp()        # align fiscal quarter ends to calendar quarters
        growth[cid] = q.groupby(level=0).last().pct_change(4)
    g = pd.DataFrame(growth)
    tiers = {t: g[[c for c in g.columns if companies.loc[c, "tier"] == t]].median(axis=1)
             for t in companies["tier"].unique()}
    tiers = {t: s.dropna() for t, s in tiers.items() if s.notna().sum() >= 12}
    out = {}
    names = list(tiers)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            cc = {lag: tiers[a].corr(tiers[b].shift(-lag)) for lag in range(-max_lag, max_lag + 1)}
            best = max(cc, key=lambda k: cc[k])
            out[f"{a}->{b}"] = {"best_lag_quarters": best, "corr_at_best": round(float(cc[best]), 2),
                                "corr_same_quarter": round(float(cc[0]), 2), "quarters": int(min(len(tiers[a]), len(tiers[b])))}
    return out


def main() -> None:
    companies = G.load_companies()
    out = {"monthly": {}, "sec": {}}
    for cid, c in companies.iterrows():
        if c["ticker"].endswith((".TW", ".TWO")) and c["tier"] != "control":
            s = taiwan_monthly(c["ticker"].split(".")[0])
            if len(s):
                yoy = s.pct_change(12)
                month_share = (s / s.groupby(s.index.year).transform("sum"))[s.groupby(s.index.year).transform("count") == 12]
                out["monthly"][cid] = {
                    "last_month": str(s.index[-1].date())[:7], "last_revenue_twd": float(s.iloc[-1]),
                    "yoy_pct": round(float(yoy.iloc[-1]) * 100, 1),
                    "series": {str(k.date())[:7]: v for k, v in s.tail(36).items()},
                    "month_share_pct": {int(k): round(float(v) * 100, 1) for k, v in month_share.groupby(month_share.index.month).mean().items()}}
                print(cid, "monthly:", len(s), "months, last", out["monthly"][cid]["last_month"], f"{out['monthly'][cid]['yoy_pct']:+}% yoy", flush=True)
            time.sleep(1.2)
    for cid, cik in CIK.items():
        try:
            out["sec"][cid] = sec_company(cid, cik)
            d = out["sec"][cid]
            print(cid, d.get("sec_name"), "| quarters:", len(d.get("rev_q", {})), "| season:", d.get("seasonality"),
                  "| inv days:", d.get("inventory_days", {}).get("latest"), flush=True)
        except Exception as e:  # noqa: BLE001
            print(cid, "failed:", e, flush=True)
        time.sleep(0.25)
    out["tier_lead_lag"] = tier_lead_lag(out["sec"], companies)
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps(out["tier_lead_lag"], indent=1))


if __name__ == "__main__":
    main()
