"""Revenue forecasting.

Method: ordinary least squares on the monthly revenue series, with an
optional seasonal adjustment from month-of-year averages.

Why not Prophet/ARIMA by default? On the short series a single uploaded
file usually provides (often 12-36 months), a linear trend plus seasonal
index is both more stable and easier to defend than a heavier model that
will happily overfit. The interface below is deliberately model-agnostic
so ARIMA or Prophet can be swapped in when longer history exists.
"""
from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session

from app.analytics.kpis import monthly_sales

MIN_POINTS = 4


def forecast_revenue(db: Session, periods: int = 6) -> dict:
    """Project revenue `periods` months ahead."""
    history = monthly_sales(db)
    if len(history) < MIN_POINTS:
        return {
            "status": "insufficient_data",
            "message": f"Need at least {MIN_POINTS} months of history to forecast; "
                       f"found {len(history)}.",
            "history": history, "forecast": [],
        }

    y = np.array([float(m["revenue"] or 0) for m in history], dtype=float)
    x = np.arange(len(y), dtype=float)

    # --- trend ---
    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept

    # --- seasonality: average residual by calendar month ---
    resid = y - fitted
    seasonal: dict[int, float] = {}
    for m, r in zip((h["month"] for h in history), resid):
        seasonal.setdefault(int(m), []).append(float(r))
    seasonal_index = {m: float(np.mean(v)) for m, v in seasonal.items()}

    # --- goodness of fit ---
    ss_res = float(np.sum((y - fitted) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    rmse = float(np.sqrt(ss_res / len(y)))

    last_year = int(history[-1]["year"])
    last_month = int(history[-1]["month"])

    out = []
    for step in range(1, periods + 1):
        idx = len(y) - 1 + step
        month = (last_month + step - 1) % 12 + 1
        year = last_year + (last_month + step - 1) // 12
        point = slope * idx + intercept + seasonal_index.get(month, 0.0)
        point = max(point, 0.0)                       # revenue cannot be negative
        band = 1.96 * rmse                            # ~95% interval from in-sample error
        out.append({
            "year": year, "month": month,
            "label": f"{year}-{month:02d}",
            "predicted_revenue": round(point, 2),
            "lower_bound": round(max(point - band, 0.0), 2),
            "upper_bound": round(point + band, 2),
        })

    return {
        "status": "ok",
        "model": "linear trend + monthly seasonal index",
        "metrics": {"r2": round(r2, 3), "rmse": round(rmse, 2),
                    "trend_per_month": round(float(slope), 2),
                    "history_points": len(y)},
        "history": history,
        "forecast": out,
    }
