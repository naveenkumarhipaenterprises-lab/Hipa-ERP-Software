"""
Demand forecasting per product from its own sales history.

Method: weekly sales totals -> linear trend (scikit-learn LinearRegression) when at least
MIN_WEEKS of history exist; the forecast is the fitted trend projected over the horizon,
never below zero. Safety stock = Z * std(daily demand) * sqrt(LEAD_TIME_DAYS).
"""
import math

import numpy as np
from sklearn.linear_model import LinearRegression

from .data import InsufficientData, continuous_daily, daily_sales

MIN_WEEKS = 4           # at least 4 full weeks of history
MIN_SALE_DAYS = 6       # and sales on at least 6 different days
SERVICE_LEVEL_Z = 1.65  # ~95% service level
LEAD_TIME_DAYS = 7


def forecast_product(product_id, horizon_days, history_days=182):
    df = daily_sales(history_days, product_id)
    if df.empty:
        return InsufficientData("No sales recorded for this product yet.")
    series = continuous_daily(df)
    sale_days = int((series > 0).sum())
    full_weeks = len(series) // 7
    if full_weeks < MIN_WEEKS or sale_days < MIN_SALE_DAYS:
        return InsufficientData(
            f"Needs at least {MIN_WEEKS} weeks of sales history on {MIN_SALE_DAYS}+ days "
            f"(has {full_weeks} weeks, {sale_days} days with sales)."
        )

    # Weekly totals ending today (drop the incomplete oldest week)
    values = series.values[-full_weeks * 7:]
    weekly = values.reshape(full_weeks, 7).sum(axis=1)
    x = np.arange(full_weeks).reshape(-1, 1)
    model = LinearRegression().fit(x, weekly)

    weeks_ahead = horizon_days / 7
    future_x = np.arange(full_weeks, full_weeks + math.ceil(weeks_ahead)).reshape(-1, 1)
    predicted = np.clip(model.predict(future_x), 0, None)
    # Partial last week counts proportionally
    fraction = weeks_ahead - math.floor(weeks_ahead)
    if fraction:
        predicted[-1] *= fraction
    forecast = float(predicted.sum())

    daily_std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    return {
        "forecast_kg": round(forecast, 1),
        "daily_avg_kg": round(float(values.mean()), 2),
        "safety_stock_kg": round(SERVICE_LEVEL_Z * daily_std * math.sqrt(LEAD_TIME_DAYS), 1),
        "weeks_used": full_weeks,
        "trend_kg_per_week": round(float(model.coef_[0]), 2),
    }
