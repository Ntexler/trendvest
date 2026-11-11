"""Cross-exchange plumbing: which exchange a Yahoo ticker trades on, when it closes,
which local index to compare it with, and how to line an event up with each market.

The key problem: a Taiwan earthquake at 08:00 Taipei time hits the Taipei close the same
day, but hits the New York close of the *previous calendar date*. So "day 0" must be
computed per ticker as the first session that CLOSES after the event's UTC timestamp.
"""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

# Yahoo suffix -> (time zone, local close time, local benchmark index)
EXCHANGES = {
    "TW": ("Asia/Taipei", time(13, 30), "^TWII"),
    "TWO": ("Asia/Taipei", time(13, 30), "^TWII"),
    "T": ("Asia/Tokyo", time(15, 0), "^N225"),       # 15:30 since 2024-11-05, handled below
    "KS": ("Asia/Seoul", time(15, 30), "^KS11"),
    "KQ": ("Asia/Seoul", time(15, 30), "^KS11"),
    "HK": ("Asia/Hong_Kong", time(16, 0), "^HSI"),
    "SS": ("Asia/Shanghai", time(15, 0), "000001.SS"),
    "AS": ("Europe/Amsterdam", time(17, 30), "^AEX"),
    "PA": ("Europe/Paris", time(17, 30), "^FCHI"),
    "DE": ("Europe/Berlin", time(17, 30), "^GDAXI"),
    "SW": ("Europe/Zurich", time(17, 30), "^SSMI"),
    "ST": ("Europe/Stockholm", time(17, 30), "^OMX"),
    "TA": ("Asia/Jerusalem", time(17, 25), "^TA125.TA"),
    "": ("America/New_York", time(16, 0), "^GSPC"),
}
TOKYO_LATE_CLOSE_FROM = pd.Timestamp("2024-11-05")


def suffix(ticker: str) -> str:
    return ticker.rsplit(".", 1)[1] if "." in ticker and not ticker.startswith("^") else ""


def benchmark(ticker: str) -> str:
    return EXCHANGES[suffix(ticker)][2]


def close_utc(ticker: str, dates: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """UTC timestamp of the closing auction for each trading date of this ticker."""
    tz, close, _ = EXCHANGES[suffix(ticker)]
    out = []
    for d in dates:
        c = close
        if suffix(ticker) == "T" and d >= TOKYO_LATE_CLOSE_FROM:
            c = time(15, 30)
        local = datetime.combine(d.date(), c, tzinfo=ZoneInfo(tz))
        out.append(pd.Timestamp(local).tz_convert("UTC"))
    return pd.DatetimeIndex(out)


def day0_position(ticker: str, dates: pd.DatetimeIndex, event_utc: pd.Timestamp) -> int | None:
    """Index of the first session that closes after the event became known."""
    closes = close_utc(ticker, dates)
    pos = int(closes.searchsorted(event_utc, side="right"))  # unit-safe (pandas 3 stores non-ns units)
    return pos if pos < len(dates) else None


def abnormal_returns(close: pd.Series, bench: pd.Series, i0: int,
                     est=(250, 11), pre=5, post=10) -> dict | None:
    """Market-model abnormal returns around position ``i0`` of ``close``.

    alpha/beta are fitted on days [-est[0], -est[1]] so the event cannot leak into them.
    Returns AR for days -pre..+post and the residual sigma, or None if history is too short.
    """
    df = pd.DataFrame({"p": close, "m": bench}).dropna()
    if close.index[i0] not in df.index:
        return None
    j = df.index.get_loc(close.index[i0])
    r = np.log(df["p"]).diff()
    rm = np.log(df["m"]).diff()
    lo, hi = j - est[0], j - est[1]
    if lo < 1 or j + post >= len(df):
        return None
    x, y = rm.iloc[lo:hi].to_numpy(), r.iloc[lo:hi].to_numpy()
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 120:
        return None
    beta, alpha = np.polyfit(x[ok], y[ok], 1)
    resid = y[ok] - (alpha + beta * x[ok])
    sigma = resid.std(ddof=2)
    w = slice(j - pre, j + post + 1)
    ar = (r.iloc[w] - (alpha + beta * rm.iloc[w])).to_numpy()
    return {"ar": ar, "sigma": sigma, "beta": beta, "day0": df.index[j]}
