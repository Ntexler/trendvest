"""Synthetic check: a known news shock with a known price reaction must be recovered."""
import numpy as np
import pandas as pd

from research.news_impact import metrics as M


def make_frame(seed=0):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2024-01-01", periods=400)
    rm = rng.normal(0, 0.01, len(days))
    eps = rng.normal(0, 0.01, len(days))
    articles = rng.poisson(100, len(days)).astype(float)
    shock_days = [200, 300]
    for i in shock_days:
        articles[i] = 1500          # news spike
        eps[i] += 0.08              # +8% abnormal move on day 0
        eps[i + 1] -= 0.01
        eps[i + 2] -= 0.02
        eps[i + 3] -= 0.01          # gives back half within 3 days
    r = 1.2 * rm + eps
    close = pd.Series(100 * np.exp(np.cumsum(r)), index=days)
    mkt = pd.Series(100 * np.exp(np.cumsum(rm)), index=days)
    vol = pd.Series(1e6, index=days)
    news = pd.DataFrame({"articles": articles, "total": 1e5, "tone": 0.0}, index=days)
    return M.build_daily_frame(close, mkt, vol, news), [days[i] for i in shock_days]


def test_events_found_and_reaction_measured():
    df, shocks = make_frame()
    events = M.find_events(df)
    assert set(shocks) <= set(events)
    for d in shocks:
        m = M.event_metrics(df, d)
        assert m["peak_day"] == 0              # market reacts the same day
        assert m["car0_sig"] > 5               # move is many sigmas
        assert 0.3 < m["reversal"] < 0.7       # about half given back
        assert m["settle_day"] <= 5


def test_lead_lag_peaks_at_zero():
    df, _ = make_frame()
    assert M.lead_lag(df).idxmax() == 0
