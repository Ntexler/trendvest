"""News Impact metrics: how fast a stock reacts to a news-attention shock,
how far it moves, and how fast it settles back.

Method (classic event study + lead/lag analysis)
------------------------------------------------
1. Abnormal return   AR_t = r_t - beta_t * r_mkt,t
   beta_t is estimated on the previous 120 trading days (no look-ahead).
2. Attention shock   z_t = (x_t - mean(x[t-60:t-1])) / std(x[t-60:t-1])
   where x_t = log(1 + articles per 10k articles that GDELT saw that day).
3. Event             a day with z_t >= Z_EVENT, at least COOLDOWN days after the previous event.
4. Per event, over days k = -5..+10:
   CAR_k            cumulative abnormal return from day 0 to k
   AV_k = |AR_k| / sigma_pre    abnormal volatility, in units of normal daily noise
   peak_day         day k (0..10) where |CAR_k| is largest  -> reaction speed
   settle_day       first day after the peak with AV < 1 for two days in a row -> recovery
   reversal         share of the peak move that was given back by day 10
   pre_move         |CAR| over days -5..-1, in sigma units -> did prices move *before* the news?
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BETA_WINDOW = 120
Z_WINDOW = 60
Z_EVENT = 2.5
COOLDOWN = 5
PRE, POST = 5, 10


def align_news_to_trading_days(news: pd.DataFrame, trading_days: pd.DatetimeIndex) -> pd.DataFrame:
    """Weekend/holiday news counts toward the next trading day."""
    news = news.copy()
    pos = trading_days.searchsorted(news.index)
    news = news[pos < len(trading_days)]
    news["tday"] = trading_days[pos[pos < len(trading_days)]]
    news["tone_x_n"] = news["tone"].fillna(0) * news["articles"].fillna(0)
    g = news.groupby("tday").agg(
        articles=("articles", "sum"), total=("total", "sum"), tone_x_n=("tone_x_n", "sum")
    )
    g["tone"] = g["tone_x_n"] / g["articles"].replace(0, np.nan)
    g["share"] = g["articles"] / g["total"].replace(0, np.nan) * 1e4
    return g.drop(columns="tone_x_n").reindex(trading_days)


def build_daily_frame(close: pd.Series, market: pd.Series, volume: pd.Series,
                      news: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame({"close": close, "mkt": market, "volume": volume}).dropna(subset=["close", "mkt"])
    df["r"] = np.log(df["close"]).diff()
    df["rm"] = np.log(df["mkt"]).diff()
    cov = df["r"].rolling(BETA_WINDOW, min_periods=60).cov(df["rm"])
    var = df["rm"].rolling(BETA_WINDOW, min_periods=60).var()
    df["beta"] = (cov / var).shift(1)
    df["ar"] = df["r"] - df["beta"] * df["rm"]
    df["sigma"] = df["ar"].rolling(Z_WINDOW, min_periods=30).std().shift(6)  # quiet window, ends 6 days before
    df["av"] = df["ar"].abs() / df["sigma"]
    df["vol_ratio"] = df["volume"] / df["volume"].rolling(Z_WINDOW, min_periods=30).median().shift(1)

    n = align_news_to_trading_days(news, df.index)
    df = df.join(n[["articles", "share", "tone"]])
    x = np.log1p(df["share"].fillna(0))
    mu = x.rolling(Z_WINDOW, min_periods=30).mean().shift(1)
    sd = x.rolling(Z_WINDOW, min_periods=30).std().shift(1)
    df["news_z"] = (x - mu) / sd.replace(0, np.nan)
    tmu = df["tone"].rolling(30, min_periods=10).mean().shift(1)
    df["tone_shock"] = df["tone"] - tmu
    return df.dropna(subset=["ar", "sigma", "news_z"])


def find_events(df: pd.DataFrame, z: float = Z_EVENT) -> list[pd.Timestamp]:
    events, last = [], None
    idx = list(df.index)
    for i, (d, v) in enumerate(df["news_z"].items()):
        if v >= z and (last is None or i - last > COOLDOWN) and PRE <= i < len(idx) - POST:
            events.append(d)
            last = i
    return events


def event_metrics(df: pd.DataFrame, day0: pd.Timestamp) -> dict:
    i = df.index.get_loc(day0)
    w = df.iloc[i - PRE: i + POST + 1]
    sigma = df["sigma"].iloc[i]
    post = w.iloc[PRE:]
    car = post["ar"].cumsum().to_numpy()
    av = (post["ar"].abs() / sigma).to_numpy()
    peak = int(np.argmax(np.abs(car)))
    settle = None
    for k in range(max(peak, 1), len(av) - 1):
        if av[k] < 1 and av[k + 1] < 1:
            settle = k
            break
    peak_car = car[peak]
    reversal = (1 - car[-1] / peak_car) if abs(peak_car) > 1e-9 else np.nan
    return {
        "date": day0,
        "news_z": df["news_z"].iloc[i],
        "tone_shock": df["tone_shock"].iloc[i],
        "car0_sig": car[0] / sigma,
        "car1_sig": car[1] / sigma,
        "car10_sig": car[-1] / sigma,
        "peak_car_sig": peak_car / sigma,
        "peak_day": peak,
        "settle_day": settle if settle is not None else np.nan,
        "reversal": float(np.clip(reversal, -2, 2)),
        "av0": av[0],
        "vol_ratio0": df["vol_ratio"].iloc[i],
        "pre_move_sig": w["ar"].iloc[:PRE].sum() / sigma,
        "speed_share": abs(car[1]) / abs(peak_car) if abs(peak_car) > 1e-9 else np.nan,
    }


def lead_lag(df: pd.DataFrame, max_lag: int = 5) -> pd.Series:
    """corr(news_z_t, AV_{t+lag}). Positive lag = news leads the price shock."""
    out = {}
    for lag in range(-max_lag, max_lag + 1):
        out[lag] = df["news_z"].corr(df["av"].shift(-lag))
    return pd.Series(out, name="corr")


def granger_p(df: pd.DataFrame, maxlag: int = 3) -> tuple[float, float]:
    """(p news->volatility, p volatility->news), min over lags 1..maxlag."""
    from statsmodels.tsa.stattools import grangercausalitytests
    d = df[["av", "news_z"]].dropna()
    d = d.clip(lower=d.quantile(0.005), upper=d.quantile(0.995), axis=1)

    def p(cols):
        res = grangercausalitytests(d[cols], maxlag=maxlag, verbose=False)
        return min(r[0]["ssr_ftest"][1] for r in res.values())

    return p(["av", "news_z"]), p(["news_z", "av"])


def profile(ticker: str, df: pd.DataFrame) -> tuple[dict, pd.DataFrame, pd.Series]:
    """Summary row (the 'News Impact Profile'), per-event table, lead/lag curve."""
    events = [event_metrics(df, d) for d in find_events(df)]
    ev = pd.DataFrame(events)
    ll = lead_lag(df)
    g_news, g_rev = granger_p(df)
    calm = df.loc[df["news_z"] < 1, "av"].mean()
    row = {"ticker": ticker, "days": len(df), "events": len(ev)}
    if len(ev):
        hit = ev.dropna(subset=["tone_shock"])
        hit = hit[(hit["tone_shock"].abs() > 0.3) & (hit["car1_sig"].abs() > 0.5)]
        row.update({
            "impact_x": ev["av0"].mean() / calm,                 # event-day volatility vs a calm day
            "abs_car1_sig": ev["car1_sig"].abs().median(),
            "peak_day_med": ev["peak_day"].median(),
            "settle_day_med": ev["settle_day"].median(),
            "reversal_med": ev["reversal"].median(),
            "pre_move_abs_sig": ev["pre_move_sig"].abs().median(),
            "vol_ratio_med": ev["vol_ratio0"].median(),
            "tone_hit_rate": (np.sign(hit["tone_shock"]) == np.sign(hit["car1_sig"])).mean() if len(hit) else np.nan,
            "tone_n": len(hit),
        })
    row.update({
        "best_lag": int(ll.idxmax()),
        "corr_lag0": ll.loc[0],
        "corr_lag1": ll.loc[1],
        "corr_lag_minus1": ll.loc[-1],
        "granger_news_to_vol_p": g_news,
        "granger_vol_to_news_p": g_rev,
    })
    if len(ev):
        ev.insert(0, "ticker", ticker)
    return row, ev, ll


def prediction_test(frames: dict[str, pd.DataFrame], train_share: float = 0.7) -> dict:
    """Can today's news predict a big move TOMORROW (|AR| > 2 sigma)?

    Chronological split per ticker, pooled logistic regression.
    Compares a baseline (today's own volatility + volume) against baseline + news features.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score

    base_cols = ["av", "vol_ratio"]
    news_cols = ["news_z", "news_z_lag1", "tone_shock"]
    tr, te = [], []
    for t, df in frames.items():
        d = df.copy()
        d["news_z_lag1"] = d["news_z"].shift(1)
        d["y"] = (d["av"].shift(-1) > 2).astype(float)
        d["y_dir"] = (d["ar"].shift(-1) > 0).astype(float)
        d = d.dropna(subset=base_cols + news_cols + ["y"]).iloc[:-1]
        cut = int(len(d) * train_share)
        tr.append(d.iloc[:cut])
        te.append(d.iloc[cut:])
    tr, te = pd.concat(tr), pd.concat(te)
    for d in (tr, te):
        d[base_cols + news_cols] = d[base_cols + news_cols].clip(-10, 10)

    def fit_auc(cols, target="y"):
        m = LogisticRegression(max_iter=1000).fit(tr[cols], tr[target])
        return roc_auc_score(te[target], m.predict_proba(te[cols])[:, 1]), m

    auc_base, _ = fit_auc(base_cols)
    auc_full, m_full = fit_auc(base_cols + news_cols)
    auc_news_only, _ = fit_auc(news_cols)
    auc_dir, _ = fit_auc(["tone_shock", "news_z"], "y_dir")
    return {
        "train_rows": len(tr), "test_rows": len(te),
        "big_move_rate_test": te["y"].mean(),
        "auc_baseline_volatility": auc_base,
        "auc_news_only": auc_news_only,
        "auc_baseline_plus_news": auc_full,
        "auc_direction_from_tone": auc_dir,
        "coefs": dict(zip(base_cols + news_cols, np.round(m_full.coef_[0], 3))),
    }
