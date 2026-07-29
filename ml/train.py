from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels
from sklearn.metrics import mean_absolute_error, mean_squared_error
from statsmodels.tsa.statespace.sarimax import SARIMAX


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "Egg_Production_Final_Cleaned.csv"
MODEL_DIR = BASE_DIR / "models"
MODEL_NAME = "sarimax_clean_v1"
DATE_COLUMN = "Corrected Date"
TARGET_COLUMN = "Pieces"
EXOG_COLUMNS = ["Bird No.", "Dead", "Cull", "FEED (bags)"]
REQUIRED_COLUMNS = [DATE_COLUMN, TARGET_COLUMN, *EXOG_COLUMNS]
ORDER = (1, 1, 1)
SEASONAL_ORDER = (1, 0, 1, 7)


class DatasetValidationError(ValueError):
    pass


@dataclass(frozen=True)
class TrainingResult:
    model_path: Path
    metadata_path: Path
    metrics: dict


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_clean_dataset(path: Path = DATA_PATH) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    df = pd.read_csv(path)
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise DatasetValidationError(f"Missing required columns: {', '.join(missing)}")

    df = df[REQUIRED_COLUMNS].copy()
    df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN], errors="coerce")
    if df[DATE_COLUMN].isna().any():
        bad_rows = df.index[df[DATE_COLUMN].isna()].tolist()[:5]
        raise DatasetValidationError(f"Invalid dates found near row(s): {bad_rows}")

    for column in [TARGET_COLUMN, *EXOG_COLUMNS]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df["Dead"] = df["Dead"].fillna(0)
    df["Cull"] = df["Cull"].fillna(0)

    if df[TARGET_COLUMN].isna().any():
        raise DatasetValidationError("Pieces contains blank or non-numeric values. Missing target values are not fabricated.")

    if df[["Bird No.", "FEED (bags)"]].isna().any().any():
        df[["Bird No.", "FEED (bags)"]] = df[["Bird No.", "FEED (bags)"]].ffill().bfill()

    if df[EXOG_COLUMNS].isna().any().any():
        raise DatasetValidationError("Exogenous predictors still contain missing values after cleaning.")

    df = df.sort_values(DATE_COLUMN)
    duplicate_dates = df[df.duplicated(DATE_COLUMN, keep=False)][DATE_COLUMN].dt.date.unique()
    if len(duplicate_dates):
        duplicated = ", ".join(str(item) for item in duplicate_dates[:5])
        raise DatasetValidationError(f"Duplicate dates detected: {duplicated}")

    return longest_continuous_segment(df)


def longest_continuous_segment(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(DATE_COLUMN).reset_index(drop=True)
    gaps = df[DATE_COLUMN].diff().dt.days.fillna(1)
    group_ids = gaps.ne(1).cumsum()
    groups = [group.copy() for _, group in df.groupby(group_ids)]
    longest = max(groups, key=len)
    if len(longest) < 10:
        raise DatasetValidationError("At least 10 continuous daily records are required.")
    return longest.reset_index(drop=True)


def split_train_test(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    test_size = max(2, int(round(len(df) * 0.2)))
    if len(df) - test_size < 8:
        raise DatasetValidationError("Not enough records for chronological train-test split.")
    return df.iloc[:-test_size].copy(), df.iloc[-test_size:].copy()


def calculate_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict:
    nonzero = actual != 0
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
        "mape": float(np.mean(np.abs((actual[nonzero] - predicted[nonzero]) / actual[nonzero])) * 100) if nonzero.any() else None,
    }


def train_model(dataset_path: Path = DATA_PATH, model_name: str = MODEL_NAME) -> TrainingResult:
    df = load_clean_dataset(dataset_path)
    train_df, test_df = split_train_test(df)

    model = SARIMAX(
        train_df[TARGET_COLUMN].to_numpy(dtype=float),
        exog=train_df[EXOG_COLUMNS].to_numpy(dtype=float),
        order=ORDER,
        seasonal_order=SEASONAL_ORDER,
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    fitted = model.fit(disp=False)
    predictions = np.asarray(
        fitted.forecast(steps=len(test_df), exog=test_df[EXOG_COLUMNS].to_numpy(dtype=float)),
        dtype=float,
    )
    metrics = calculate_metrics(test_df[TARGET_COLUMN].to_numpy(dtype=float), predictions)

    final_model = SARIMAX(
        df[TARGET_COLUMN].to_numpy(dtype=float),
        exog=df[EXOG_COLUMNS].to_numpy(dtype=float),
        order=ORDER,
        seasonal_order=SEASONAL_ORDER,
        enforce_stationarity=False,
        enforce_invertibility=False,
    ).fit(disp=False)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / f"{model_name}.pkl"
    metadata_path = MODEL_DIR / f"{model_name}.metadata.json"
    final_model.save(model_path)

    metadata = {
        "model_name": model_name,
        "model_version": model_name,
        "dataset_filename": dataset_path.name,
        "dataset_hash": file_hash(dataset_path),
        "target_column": TARGET_COLUMN,
        "exogenous_columns": EXOG_COLUMNS,
        "training_date_range": {
            "start": df[DATE_COLUMN].min().date().isoformat(),
            "end": df[DATE_COLUMN].max().date().isoformat(),
        },
        "observation_count": int(len(df)),
        "order": ORDER,
        "seasonal_order": SEASONAL_ORDER,
        "mae": metrics["mae"],
        "rmse": metrics["rmse"],
        "mape": metrics["mape"],
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "statsmodels_version": statsmodels.__version__,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return TrainingResult(model_path=model_path, metadata_path=metadata_path, metrics=metrics)


def main() -> None:
    result = train_model()
    print(json.dumps({
        "model_path": str(result.model_path),
        "metadata_path": str(result.metadata_path),
        "metrics": result.metrics,
    }, indent=2))


if __name__ == "__main__":
    main()
