"""Step 1 — demand forecasting.

Aggregate tickets into a daily demand series, run a three-model bake-off
(seasonal-naive vs Holt-Winters vs gradient boosting) with a first-half /
second-half backtest, and report accuracy against the Poisson noise floor.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from statsmodels.tsa.holtwinters import ExponentialSmoothing

CHOSEN_MODEL = "GBM(calendar)"


def _score(name: str, pred: np.ndarray, actual: np.ndarray) -> dict:
    pred = np.asarray(pred, dtype=float)
    mae = float(np.mean(np.abs(pred - actual)))
    rmse = float(np.sqrt(np.mean((pred - actual) ** 2)))
    mask = actual > 5
    mape = float(np.mean(np.abs((pred - actual)[mask] / actual[mask])) * 100)
    return {"model": name, "mae": round(mae, 2), "rmse": round(rmse, 2), "mape": round(mape, 1)}


def _calendar_features(index: pd.DatetimeIndex) -> pd.DataFrame:
    day_of_year = index.dayofyear
    return pd.DataFrame({
        "dow": index.dayofweek,
        "month": index.month,
        "weekend": (index.dayofweek >= 5).astype(int),
        "sin": np.sin(2 * np.pi * day_of_year / 365),
        "cos": np.cos(2 * np.pi * day_of_year / 365),
    })


def run(demand: pd.Series) -> dict:
    n = len(demand)
    split = n // 2
    train, test = demand.iloc[:split], demand.iloc[split:]
    actual = test.values

    weekday_avg = demand.groupby(demand.index.dayofweek).mean()

    models = []
    weekday_mean = train.groupby(train.index.dayofweek).mean()
    naive = test.index.dayofweek.map(weekday_mean).values
    models.append(_score("seasonal-naive", naive, actual))

    holt = ExponentialSmoothing(train, trend="add", seasonal="add", seasonal_periods=7).fit()
    models.append(_score("Holt-Winters(m=7)", holt.forecast(len(test)).values, actual))

    gbm = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_depth=4)
    gbm.fit(_calendar_features(train.index), train.values)
    gbm_pred = gbm.predict(_calendar_features(test.index))
    models.append(_score(CHOSEN_MODEL, gbm_pred, actual))

    return {
        "days": n,
        "start": str(demand.index.min().date()),
        "end": str(demand.index.max().date()),
        "mean_per_day": round(float(demand.mean()), 2),
        "noise_floor_mae": round(float(np.sqrt(test.mean())), 2),
        "split_index": split,
        "chosen_model": CHOSEN_MODEL,
        "models": models,
        "weekday_profile": [round(float(v), 2) for v in weekday_avg.values],
        "series": [
            {"date": str(d.date()), "count": round(float(v), 1)}
            for d, v in demand.items()
        ],
        "backtest": [
            {"date": str(d.date()), "actual": round(float(a), 1), "forecast": round(float(f), 2)}
            for d, a, f in zip(test.index, actual, gbm_pred)
        ],
    }
