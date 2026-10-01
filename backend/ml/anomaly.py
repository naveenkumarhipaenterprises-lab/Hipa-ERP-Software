"""
Unusual sales days: robust z-score (median / MAD) of daily sales over the history window.
Only recent days are reported. Needs enough history to know what "normal" looks like.
"""
import numpy as np

from .data import InsufficientData, continuous_daily, daily_sales

MIN_DAYS = 30
THRESHOLD = 3.5
RECENT_DAYS = 14


def sales_anomalies(history_days=120):
    df = daily_sales(history_days)
    series = continuous_daily(df, "amount")
    if len(series) < MIN_DAYS:
        return InsufficientData(f"Needs at least {MIN_DAYS} days of sales history (has {len(series)}).")
    values = series.values
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    if mad == 0:
        return {"anomalies": [], "median_daily_sales": round(median, 2)}
    scores = 0.6745 * (values - median) / mad
    found = []
    for day, value, score in zip(series.index[-RECENT_DAYS:], values[-RECENT_DAYS:], scores[-RECENT_DAYS:]):
        if abs(score) >= THRESHOLD:
            found.append({"date": day.date().isoformat(), "sales": round(float(value), 2),
                          "direction": "high" if score > 0 else "low", "score": round(float(score), 1)})
    return {"anomalies": found, "median_daily_sales": round(median, 2)}
