import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from ml.predict import PredictionError, forecast, load_model_and_metadata, validate_future_exog
from ml.train import DatasetValidationError, load_clean_dataset


def write_dataset(path: Path, **overrides):
    rows = []
    for day in range(12):
        rows.append({
            "Corrected Date": f"2026-01-{day + 1:02d}",
            "Pieces": 1200 + day,
            "Bird No.": 1800 - day,
            "Dead": "" if day == 0 else 0,
            "Cull": "" if day == 1 else 0,
            "FEED (bags)": 4,
        })
    df = pd.DataFrame(rows)
    for column, value in overrides.items():
        if value == "__drop__":
            df = df.drop(columns=[column])
        else:
            df[column] = value
    df.to_csv(path, index=False)


class MLPipelineTest(unittest.TestCase):
    def test_required_column_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.csv"
            write_dataset(path, Pieces="__drop__")

            with self.assertRaises(DatasetValidationError):
                load_clean_dataset(path)

    def test_invalid_dates_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.csv"
            write_dataset(path, **{"Corrected Date": "bad-date"})

            with self.assertRaises(DatasetValidationError):
                load_clean_dataset(path)

    def test_blank_dead_and_cull_are_zero_filled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.csv"
            write_dataset(path)

            df = load_clean_dataset(path)

            self.assertEqual(df["Dead"].iloc[0], 0)
            self.assertEqual(df["Cull"].iloc[1], 0)

    def test_missing_target_is_not_fabricated(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.csv"
            write_dataset(path)
            df = pd.read_csv(path)
            df.loc[2, "Pieces"] = None
            df.to_csv(path, index=False)

            with self.assertRaises(DatasetValidationError):
                load_clean_dataset(path)

    def test_missing_model_file_fails_clearly(self):
        with self.assertRaises(FileNotFoundError):
            load_model_and_metadata("definitely_missing_model")

    def test_missing_predictors_fail_validation(self):
        future = pd.DataFrame({"Bird No.": [1800], "Dead": [0], "Cull": [0]})

        with self.assertRaises(PredictionError):
            validate_future_exog(future, 1)

    def test_invalid_forecast_horizon_fails(self):
        with self.assertRaises(PredictionError):
            forecast(horizon=0)

    def test_forecast_json_shape_with_stubbed_model(self):
        class StubResult:
            predicted_mean = [1000, 1010]

            def conf_int(self, alpha=0.05):
                return [[900, 1100], [910, 1110]]

        class StubModel:
            def get_forecast(self, steps, exog):
                return StubResult()

        with patch("ml.predict.load_model_and_metadata", return_value=(StubModel(), {"model_version": "test"})):
            future = pd.DataFrame({
                "forecast_date": ["2026-01-01", "2026-01-02"],
                "Bird No.": [1800, 1800],
                "Dead": [0, 0],
                "Cull": [0, 0],
                "FEED (bags)": [4, 4],
            })
            result = forecast(horizon=2, future_exog=future)

        self.assertEqual(result["model_version"], "test")
        self.assertEqual(len(result["forecasts"]), 2)
        self.assertEqual(result["forecasts"][0]["predicted_pieces"], 1000)
        json.dumps(result)


if __name__ == "__main__":
    unittest.main()
