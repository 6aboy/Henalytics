from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAXResults

try:
    from .train import DATA_PATH, DATE_COLUMN, EXOG_COLUMNS, MODEL_DIR, MODEL_NAME, load_clean_dataset
except ImportError:
    from train import DATA_PATH, DATE_COLUMN, EXOG_COLUMNS, MODEL_DIR, MODEL_NAME, load_clean_dataset


class PredictionError(ValueError):
    pass


def model_paths(model_name: str = MODEL_NAME) -> tuple[Path, Path]:
    return MODEL_DIR / f"{model_name}.pkl", MODEL_DIR / f"{model_name}.metadata.json"


def load_model_and_metadata(model_name: str = MODEL_NAME):
    model_path, metadata_path = model_paths(model_name)
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

    model = SARIMAXResults.load(str(model_path))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    missing = [column for column in EXOG_COLUMNS if column not in metadata.get("exogenous_columns", [])]
    if missing:
        raise PredictionError(f"Metadata is missing expected predictors: {', '.join(missing)}")
    return model, metadata


def default_future_exog(horizon: int, dataset_path: Path = DATA_PATH) -> tuple[pd.DataFrame, dict]:
    if horizon < 1:
        raise PredictionError("Forecast horizon must be at least 1.")

    df = load_clean_dataset(dataset_path)
    latest = df.iloc[-1]
    last_date = latest[DATE_COLUMN].date()
    dates = [last_date + timedelta(days=step) for step in range(1, horizon + 1)]
    assumptions = {
        "Bird No.": float(latest["Bird No."]),
        "Dead": 0,
        "Cull": 0,
        "FEED (bags)": float(latest["FEED (bags)"]),
    }
    future = pd.DataFrame({column: [value] * horizon for column, value in assumptions.items()})
    future.insert(0, "forecast_date", dates)
    return future, assumptions


def validate_future_exog(future_exog: pd.DataFrame, horizon: int) -> pd.DataFrame:
    if len(future_exog) != horizon:
        raise PredictionError("Future predictor row count must match forecast horizon.")
    missing = [column for column in EXOG_COLUMNS if column not in future_exog.columns]
    if missing:
        raise PredictionError(f"Missing future predictors: {', '.join(missing)}")
    cleaned = future_exog.copy()
    for column in EXOG_COLUMNS:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
    if cleaned[EXOG_COLUMNS].isna().any().any():
        raise PredictionError("Future predictors must be numeric.")
    return cleaned


def forecast(horizon: int = 30, future_exog: pd.DataFrame | None = None, model_name: str = MODEL_NAME) -> dict:
    model, metadata = load_model_and_metadata(model_name)
    assumptions = None
    if future_exog is None:
        future_exog, assumptions = default_future_exog(horizon)
    else:
        future_exog = validate_future_exog(future_exog, horizon)

    forecast_result = model.get_forecast(steps=horizon, exog=future_exog[EXOG_COLUMNS].to_numpy(dtype=float))
    raw_predictions = np.asarray(forecast_result.predicted_mean, dtype=float)
    confidence = np.asarray(forecast_result.conf_int(alpha=0.05), dtype=float)

    dates = future_exog["forecast_date"] if "forecast_date" in future_exog.columns else range(1, horizon + 1)
    rows = []
    for forecast_date, raw_value, bounds in zip(dates, raw_predictions, confidence):
        lower = max(float(bounds[0]), 0)
        upper = max(float(bounds[1]), lower)
        rows.append({
            "date": forecast_date.isoformat() if hasattr(forecast_date, "isoformat") else str(forecast_date),
            "predicted_pieces": max(float(raw_value), 0),
            "raw_predicted_pieces": float(raw_value),
            "lower_bound": lower,
            "upper_bound": upper,
            "model_version": metadata.get("model_version", model_name),
        })

    return {
        "model_version": metadata.get("model_version", model_name),
        "horizon": horizon,
        "assumptions": assumptions,
        "forecasts": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Henalytics SARIMAX egg forecasts.")
    parser.add_argument("--horizon", type=int, default=30)
    parser.add_argument("--model-name", default=MODEL_NAME)
    args = parser.parse_args()
    print(json.dumps(forecast(horizon=args.horizon, model_name=args.model_name), indent=2))


if __name__ == "__main__":
    main()
