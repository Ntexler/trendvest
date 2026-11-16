"""The economic calendar: central-bank decisions and consumer-price releases, with how the home market moved.

Sources (all free, official):
  Fed decisions and rates   federalreserve.gov calendar pages and each decision's statement (cached in data/fed_decisions.csv)
  Bank of Israel rate       edge.boi.gov.il series database (series MNT_RIB_BOI_D); past decisions = days the rate changed
  ECB deposit rate          data-api.ecb.europa.eu (FM, DFR)
  Bank of Japan decisions   boj.or.jp statement links (data/boj_decisions.txt keeps the history)
  Israel CPI                api.cbs.gov.il (series 120010), published on the 15th at 18:30 Israel time
  US CPI                    api.bls.gov (CUUR0000SA0); release dates kept by hand in data/us_cpi_release.txt (bls.gov blocks us)
  Upcoming dates that no readable page gives (Bank of Israel, ECB, BoJ): data/schedule_upcoming.txt, kept by hand.
Market reaction: the home index's close-to-close move on the first session that could react (decision times in Israel time).
"Noisy day": on past days of that kind the home index moved, on average, at least 15% more than on an ordinary day.

    python -m research.macro.collect     -> supply_chain/map/site/data/macro.json
"""
from __future__ import annotations

import csv
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd
import requests

D = Path(__file__).parent / "data"
OUT = Path(__file__).parents[1] / "supply_chain" / "map" / "site" / "data" / "macro.json"
UA = {"User-Agent": "Mozilla/5.0 (research script)"}
INDEX = {"us": "^GSPC", "il": "^TA125.TA", "jp": "^N225", "eu": "^STOXX50E", "asia": "^HSI"}
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September",
                                      "October", "November", "December"], 1)}
# kind -> (time in Israel, home market, which markets react the same day; the others react the next session)
KIND = {"fed": ("21:00", "us", {"us"}), "uscpi": ("15:30", "us", {"us", "il", "eu"}), "boi": ("16:00", "il", {"il", "us"}),
        "ilcpi": ("18:30", "il", set()), "ecb": ("15:15", "eu", {"eu", "il", "us"}), "boj": ("05:00", "jp", {"jp", "asia", "il", "eu", "us"})}
TITLE = {"fed": "הפד · החלטת ריבית", "uscpi": "ארה״ב · מדד המחירים", "boi": "בנק ישראל · החלטת ריבית",
         "ilcpi": "ישראל · מדד המחירים", "ecb": "הבנק המרכזי האירופי · ריבית", "boj": "בנק יפן · ריבית"}


def get(url, **kw):
    for k in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=60, **kw)
            if r.status_code == 200:
                return r
        except requests.RequestException:
            pass
        time.sleep(2 * (k + 1))
    raise RuntimeError(f"failed: {url}")


def frac(s: str) -> float:
    s = s.strip()
    if "-" in s and "/" in s:
        a, b = s.split("-")
        return float(a) + float(Fraction(b))
    return float(Fraction(s))


# ---------- the Fed ----------
def fed() -> tuple[list[dict], list[str]]:
    cache = D / "fed_decisions.csv"
    have = {r["date"]: r for r in csv.DictReader(cache.open())} if cache.exists() else {}
    html = get("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm").text
    pages = [html]
    if not have:
        pages += [get(f"https://www.federalreserve.gov/monetarypolicy/fomchistorical{y}.htm").text for y in range(2016, 2021)]
    stmts = sorted({m for p in pages for m in re.findall(r"monetary(20\d{6})a\d*\.htm", p)})
    for s in stmts:
        d = f"{s[:4]}-{s[4:6]}-{s[6:]}"
        if d in have or d < "2016-01-01":
            continue
        t = get(f"https://www.federalreserve.gov/newsevents/pressreleases/monetary{s}a.htm").content.decode("utf-8", "ignore")
        t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)).replace("\u2011", "-").replace("\u2010", "-").replace("\u2013", "-")
        m = re.search(r"target range for the federal funds rate (?:by [^.]*? )?(?:at|to) ([\d\-/]+) to ([\d\-/]+) percent", t)
        if m:
            have[d] = {"date": d, "low": f"{frac(m.group(1)):.2f}", "high": f"{frac(m.group(2)):.2f}"}
        time.sleep(1)
    with cache.open("w", newline="") as f:
        w = csv.DictWriter(f, ["date", "low", "high"])
        w.writeheader()
        w.writerows(sorted(have.values(), key=lambda r: r["date"]))
    rows = sorted(have.values(), key=lambda r: r["date"])
    # upcoming decision days from the calendar page: the last day of each meeting
    up = []
    for year, body in zip(*[iter(re.split(r"(\d{4}) FOMC Meetings", html)[1:])] * 2):
        for mon, days in re.findall(r"fomc-meeting__month[^>]*><strong>([^<]+)</strong>.*?fomc-meeting__date[^>]*>([^<]+)<", body, re.S):
            last_mon = mon.split("/")[-1].strip()
            day = re.findall(r"\d+", days)
            if last_mon in MONTHS and day:
                up.append(f"{year}-{MONTHS[last_mon]:02d}-{int(day[-1]):02d}")
    return rows, sorted(set(up))


# ---------- Bank of Israel, ECB, BoJ ----------
def boi() -> pd.Series:
    url = ("https://edge.boi.gov.il/FusionEdgeServer/sdmx/v2/data/dataflow/BOI.STATISTICS/BR/1.0/"
           "?startperiod=2015-06-01&format=csv")
    df = pd.read_csv(pd.io.common.StringIO(get(url).text))
    s = df[df.SERIES_CODE == "MNT_RIB_BOI_D"].set_index("TIME_PERIOD").OBS_VALUE.astype(float)
    s.index = pd.to_datetime(s.index)
    return s.sort_index()


def ecb() -> pd.Series:
    url = "https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.DFR.LEV?startPeriod=2015-06-01&format=csvdata"
    df = pd.read_csv(pd.io.common.StringIO(get(url).text))
    s = df.set_index("TIME_PERIOD").OBS_VALUE.astype(float)
    s.index = pd.to_datetime(s.index)
    return s.sort_index()


def boj() -> list[str]:
    f = D / "boj_decisions.txt"
    have = set(f.read_text().split()) if f.exists() else set()
    try:
        for u in ("https://www.boj.or.jp/en/mopo/mpmsche_minu/index.htm", "https://www.boj.or.jp/en/mopo/mpmsche_minu/past.htm"):
            have |= {"20" + m for m in re.findall(r"k(\d{6})[ab]\.(?:pdf|htm)", get(u).text)}
    except RuntimeError:
        pass
    have = sorted(have)
    f.write_text("\n".join(have) + "\n")
    return [f"{x[:4]}-{x[4:6]}-{x[6:]}" for x in have]


def changes(s: pd.Series) -> list[tuple[pd.Timestamp, float, float]]:
    d = s.diff()
    return [(t, float(s.loc[t]), float(d.loc[t])) for t in d[d.abs() > 1e-9].index]


# ---------- prices ----------
def il_cpi() -> list[dict]:
    url = "https://api.cbs.gov.il/index/data/price?id=120010&format=json&download=false&PageSize=500&startPeriod=01-2015&endPeriod=12-2030"
    rows = sorted(get(url).json()["month"][0]["date"], key=lambda r: (r["year"], r["month"]))
    return [{"m": f"{r['year']}-{r['month']:02d}", "mom": r["percent"], "yoy": r["percentYear"]} for r in rows]


def us_cpi() -> list[dict]:
    """US CPI, 12-month change. The BLS API without a key allows few requests per day from a shared address, so the
    series is cached in data/us_cpi.csv (seeded 2026-11-16 from data.bls.gov) and only extended when the API answers."""
    cache = D / "us_cpi.csv"
    have = {r["m"]: r for r in csv.DictReader(cache.open())} if cache.exists() else {}
    y = date.today().year
    try:
        r = requests.post("https://api.bls.gov/publicAPI/v2/timeseries/data/", timeout=60,
                          json={"seriesid": ["CUUR0000SA0"], "startyear": str(y - 2), "endyear": str(y)}).json()
        pts = {f"{p['year']}-{p['period'][1:]}": float(p["value"]) for p in r["Results"]["series"][0]["data"] if p["period"].startswith("M")}
        for m in sorted(pts):
            prev, pm = f"{int(m[:4]) - 1}{m[4:]}", (pd.Period(m, "M") - 1).strftime("%Y-%m")
            if prev in pts:
                have[m] = {"m": m, "yoy": f"{(pts[m] / pts[prev] - 1) * 100:.1f}", "mom": f"{(pts[m] / pts[pm] - 1) * 100:.1f}" if pm in pts else ""}
    except Exception as e:  # noqa: BLE001
        print("BLS API unavailable, using the cached series:", e)
    with cache.open("w", newline="") as f:
        w = csv.DictWriter(f, ["m", "yoy", "mom"])
        w.writeheader()
        w.writerows(sorted(have.values(), key=lambda r: r["m"]))
    return [{"m": r["m"], "yoy": float(r["yoy"]), "mom": float(r["mom"]) if r["mom"] else None} for r in sorted(have.values(), key=lambda r: r["m"])]


def il_cpi_release(month: str) -> str:
    """Israel's CBS publishes month M on the 15th of M+1; on a Friday or Saturday it moves to Thursday."""
    p = pd.Period(month, "M") + 1
    d = date(p.year, p.month, 15)
    while d.weekday() in (4, 5):
        d -= timedelta(days=1)
    return d.isoformat()


def main() -> None:
    import yfinance as yf
    today = pd.Timestamp(date.today())
    raw = yf.download(list(INDEX.values()), start="2015-12-01", auto_adjust=True, progress=False)["Close"]
    idx = {k: raw[v].dropna() for k, v in INDEX.items()}
    if datetime.now(timezone.utc).hour < 22:                    # today's sessions may still be open: not a close yet
        idx = {k: s[s.index < today] for k, s in idx.items()}
    ret = {k: s.pct_change() for k, s in idx.items()}

    def react(kind, d):
        """market -> (session date, index move %) for the first session that could react to an event on day d."""
        same = KIND[kind][2]
        out = {}
        for mk, s in idx.items():
            start = pd.Timestamp(d) + (pd.Timedelta(0) if mk in same else pd.Timedelta(days=1))
            j = s.index.searchsorted(start)
            if j < len(s) and s.index[j] <= today:
                out[mk] = [s.index[j].strftime("%Y-%m-%d"), round(float(ret[mk].iloc[j]) * 100, 2)]
        return out

    fed_rows, fed_up = fed()
    boi_s, ecb_s = boi(), ecb()
    boj_days = boj()
    ilc, usc = il_cpi(), us_cpi()
    us_rel = [x for x in (D / "us_cpi_release.txt").read_text().split() if re.match(r"\d{4}-\d\d-\d\d$", x)]
    sched = {}
    for line in (D / "schedule_upcoming.txt").read_text().splitlines():
        if line and not line.startswith("#"):
            k, d = line.split(",")
            sched.setdefault(k, []).append(d)

    ev = []
    prev = None
    for r in fed_rows:
        lo, hi = float(r["low"]), float(r["high"])
        ch = None if prev is None else hi - prev
        prev = hi
        lab = f"הפד: {'ללא שינוי' if not ch else ('▲ העלה' if ch > 0 else '▼ הוריד') + f' ב־{abs(ch):.2f}'} · {lo:.2f}%–{hi:.2f}%"
        ev.append({"kind": "fed", "date": r["date"], "label": lab, "change": ch})
    # Bank of Israel: only the days its rate took effect are known here (2-3 days after the decision), so its past
    # decisions are not placed on the calendar - a wrong day would explain the wrong market move.
    for d in boj_days:
        if d >= "2016-01-01":
            ev.append({"kind": "boj", "date": d, "label": "בנק יפן: החלטת ריבית"})
    for c in ilc:
        d = il_cpi_release(c["m"])
        if "2016-01-01" <= d <= today.strftime("%Y-%m-%d"):
            ev.append({"kind": "ilcpi", "date": d, "label": f"מדד המחירים בישראל: {c['mom']:+.1f}% בחודש, {c['yoy']:.1f}% בשנה"})
    usm = {c["m"]: c for c in usc}
    for d in us_rel:
        if d <= today.strftime("%Y-%m-%d"):
            m = (pd.Period(d[:7], "M") - 1).strftime("%Y-%m")
            c = usm.get(m)
            ev.append({"kind": "uscpi", "date": d, "label": "מדד המחירים בארה״ב" + (f": {c['yoy']:.1f}% בשנה" if c else "")})
    for e in ev:
        e["time"] = KIND[e["kind"]][0]
        e["react"] = react(e["kind"], e["date"])
    ev.sort(key=lambda e: e["date"])

    # how noisy each kind of day is for its home market
    noise = {}
    for kind, (_, home, _) in KIND.items():
        days = [e["react"][home][0] for e in ev if e["kind"] == kind and home in e["react"]]
        r = ret[home][ret[home].index >= "2016-01-01"].dropna()
        on = r[r.index.isin(pd.to_datetime(days))].abs()
        if len(on) >= 15:
            noise[kind] = {"n": int(len(on)), "event_avg": round(float(on.mean()) * 100, 2), "all_avg": round(float(r.abs().mean()) * 100, 2),
                           "ratio": round(float(on.mean() / r.abs().mean()), 2)}

    horizon = (today + pd.Timedelta(days=45)).strftime("%Y-%m-%d")
    t0 = today.strftime("%Y-%m-%d")
    up = [("fed", d) for d in fed_up] + [("uscpi", d) for d in us_rel] + [(k, d) for k, ds in sched.items() for d in ds]
    up.append(("ilcpi", il_cpi_release(ilc[-1]["m"]) if il_cpi_release(ilc[-1]["m"]) >= t0 else il_cpi_release((pd.Period(ilc[-1]["m"], "M") + 1).strftime("%Y-%m"))))
    upcoming = []
    for k, d in sorted(set(up), key=lambda x: x[1]):
        if t0 <= d <= horizon:
            z = noise.get(k)
            upcoming.append({"kind": k, "date": d, "time": KIND[k][0], "title": TITLE[k], "loud": bool(z and z["ratio"] >= 1.15),
                             "ratio": z["ratio"] if z else None})

    def last_change(s):
        c = changes(s[s.index >= "2016-01-01"])
        return {"date": c[-1][0].strftime("%Y-%m-%d"), "delta": round(c[-1][2], 2)} if c else None
    fl = [e for e in ev if e["kind"] == "fed" and e.get("change")]
    rates = {
        "boi": {"rate": float(boi_s.iloc[-1]), "last_change": last_change(boi_s), "note": "תאריך = כניסה לתוקף, כמה ימים אחרי ההחלטה",
                "next": next((d for d in sched.get("boi", []) if d >= t0), None),
                "next_note": "ייתכן שיש החלטה מוקדמת יותר שלא מצאנו"},
        "fed": {"rate": f"{float(fed_rows[-1]['low']):.2f}–{float(fed_rows[-1]['high']):.2f}", "last_change": {"date": fl[-1]["date"], "delta": round(fl[-1]["change"], 2)} if fl else None,
                "next": next((d for d in fed_up if d >= t0), None)},
        "ecb": {"rate": float(ecb_s.iloc[-1]), "last_change": last_change(ecb_s), "note": "ריבית הפיקדון; תאריך = כניסה לתוקף",
                "next": next((d for d in sched.get("ecb", []) if d >= t0), None)},
        "boj": {"rate": None, "last_change": None, "next": next((d for d in sched.get("boj", []) if d >= t0), None)},
    }
    res = {"updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "rates": rates,
           "cpi": {"il": {"months": ilc[-13:], "released": il_cpi_release(ilc[-1]["m"]), "target": [1, 3]},
                   "us": {"months": usc[-13:], "target": 2}},
           "upcoming": upcoming, "noise": noise, "events": ev,
           "missing": ["מועדי ההחלטות של בנק ישראל עד סוף 2026 ותאריכי ההחלטות שעברו לא זמינים מהשרת (האתר חוסם), לכן החלטות בנק ישראל שעברו לא מסומנות",
                       "ריבית בנק יפן לא זמינה מהשרת"]}
    OUT.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")))
    print(len(ev), "events;", "upcoming", [(u["kind"], u["date"]) for u in upcoming], "; noise", noise, "; rates", rates)


if __name__ == "__main__":
    main()
