"""How hot is each company right now, compared with the rest of its market.

Two parts, each a percentile within the market (0 = coolest, 100 = hottest), shown separately on the page:
  sales  revenue growth over the last year
  price  price change over the last 26 weeks, against the market's own index
Heat = their average (price alone when sales growth is unknown, and the page says so).
Levels: 0-20 frozen, 20-40 cool, 40-60 mild, 60-80 hot, 80-100 boiling.

Hot is not a buy signal. The bottom line says so with our own base rate (fast growth usually slows), and points to
a company that is hot AND cheap for its stage, to show that the price is the thing to check.

    MARKET=chips python -m research.supply_chain.heat     -> results/<market>/heat.json
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import graph as G

LEVELS = [(80, "boiling", "רותחת"), (60, "hot", "חמה"), (40, "mild", "פושרת"), (20, "cool", "קרירה"), (0, "frozen", "קפואה")]
WEEKS = 26


def level(h: float) -> tuple[str, str]:
    return next((k, he) for lo, k, he in LEVELS if h >= lo)


def compute() -> dict:
    companies = G.load_companies()
    chain = companies[companies["tier"] != "control"]
    w = json.loads((G.DATA / "prices_weekly.json").read_text())
    px = pd.DataFrame(w["series"], index=pd.to_datetime(w["dates"])).astype(float)
    rel = (px.iloc[-1] / px.iloc[-1 - WEEKS]) / (px["_MARKET"].iloc[-1] / px["_MARKET"].iloc[-1 - WEEKS]) - 1
    prof = json.loads((G.DATA / "profiles.json").read_text())
    growth = pd.Series({c: (prof.get(c, {}).get("info") or {}).get("revenueGrowth") for c in chain.index}, dtype=float) * 100
    price = rel.reindex(chain.index) * 100
    ok = price.dropna().index
    r_price, r_sales = price[ok].rank(pct=True) * 100, growth[ok].dropna().rank(pct=True) * 100
    heat = pd.concat([r_price, r_sales.reindex(ok)], axis=1).mean(axis=1, skipna=True)
    stages = json.loads((G.DATA / "stages.json").read_text())["stages"]
    screen_p = G.RESULTS / "screen.json"
    screen = json.loads(screen_p.read_text()) if screen_p.exists() else {}
    rates_p = G.BASE / "results" / "base_rates.json"
    rates = json.loads(rates_p.read_text()) if rates_p.exists() else None

    cos = {}
    for c in ok:
        k, he = level(heat[c])
        cos[c] = {"heat": int(round(heat[c])), "level": k, "level_he": he,
                  "price_pct": round(float(price[c]), 1), "price_rank": int(round(r_price[c])),
                  "sales_pct": None if pd.isna(growth.get(c)) else round(float(growth[c]), 1),
                  "sales_rank": None if c not in r_sales else int(round(r_sales[c])),
                  "cap": (prof.get(c, {}).get("info") or {}).get("marketCapUSD"),
                  "tier": chain.loc[c, "tier"], "cheap_rank": (screen.get(c) or {}).get("rank_in_stage")}

    n = len(cos)
    hot = [c for c, v in cos.items() if v["level"] in ("hot", "boiling")]
    by_stage = {}
    for c, v in cos.items():
        by_stage.setdefault(v["tier"], []).append(v["heat"])
    stage_heat = {t: int(round(np.median(h))) for t, h in by_stage.items()}
    hottest = max(stage_heat, key=stage_heat.get)
    coolest = min(stage_heat, key=stage_heat.get)
    cheap_hot = sorted((c for c in hot if cos[c]["cheap_rank"] is not None and cos[c]["cheap_rank"] <= 40),
                       key=lambda c: -cos[c]["heat"])
    slowed = None
    if rates:
        b = next((x for x in rates["growth"]["buckets"] if x["lo"] == 25), None)
        slowed = round(b["slowed_pct"] / 10) if b else None
    name = lambda c: chain.loc[c, "name"]  # noqa: E731
    bottom = {
        "count": f"{len(hot)} מתוך {n} חברות חמות או רותחות.",
        "not_buy": "חם זה לא סימן לקנות. חם אומר שהרבה קורה עכשיו: המכירות רצות, או שהמחיר עלה יותר מהמדד."
                   + (f" בעבר, {slowed} מכל 10 חברות שהמכירות שלהן גדלו ביותר מרבע בשנה גדלו לאט יותר שנה אחר כך." if slowed else ""),
        "where": f"הכי חם בשלב \"{stages.get(hottest, {}).get('title', hottest)}\". הכי קר בשלב \"{stages.get(coolest, {}).get('title', coolest)}\".",
        "check": (f"מה כן לבדוק: אם המחיר כבר כולל את החום. למשל, {name(cheap_hot[0])} חמה, ועדיין זולה יחסית לחברות דומות."
                  if cheap_hot else "מה כן לבדוק: אם המחיר כבר כולל את החום. כרגע אין חברה חמה שגם זולה יחסית לשלב שלה.")
                 + " וגם מניה קרה לא בהכרח זולה: לפעמים יש לזה סיבה.",
    }
    out = {"as_of": w["dates"][-1], "weeks": WEEKS, "companies": cos, "stage_heat": stage_heat, "bottom": bottom,
           "method": "חום = כמה המכירות גדלו בשנה, וכמה המחיר עלה בחצי השנה האחרונה מעבר למדד, לעומת שאר החברות באותו שוק. 100 = הכי חמה."}
    G.RESULTS.mkdir(parents=True, exist_ok=True)
    (G.RESULTS / "heat.json").write_text(json.dumps(out, ensure_ascii=False))
    print(f"{G.MARKET}: {n} companies, {len(hot)} hot; hottest stage {hottest}, coolest {coolest}; hot and cheap: {cheap_hot[:3]}")
    return out


if __name__ == "__main__":
    compute()
