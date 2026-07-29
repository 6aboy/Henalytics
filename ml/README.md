# Henalytics ML

This folder contains the standalone machine-learning workflow for experimental egg production forecasting.

## Structure

- `data/Egg_Production_Final_Cleaned.csv` - cleaned research dataset.
- `notebooks/Henalytics_SARIMAX_Trend_TimeSeries.ipynb` - notebook reference only.
- `models/` - saved SARIMAX model artifacts and metadata.
- `train.py` - trains and evaluates the SARIMAX model from the cleaned CSV.
- `predict.py` - loads a saved model and creates future forecasts.

## Dataset Contract

Target column:

- `Pieces`

Date column:

- `Corrected Date`

Exogenous predictor columns:

- `Bird No.`
- `Dead`
- `Cull`
- `FEED (bags)`

`%HD` and `%HH` are excluded because they are derived from egg output and may leak the answer into the model.

## Windows Commands

```powershell
python -m venv ml/.venv
ml\.venv\Scripts\activate
python -m pip install -r ml/requirements.txt
python ml/train.py
python ml/predict.py --horizon 30
```

## Notes

The notebook is for research and validation. Django should not execute the notebook, and model training should not happen during an HTTP request.

## Django Integration

Training command:

```powershell
python henalytics/manage.py train_sarimax
```

Forecast command:

```powershell
python henalytics/manage.py generate_experimental_forecast --range week
python henalytics/manage.py generate_experimental_forecast --range three_weeks
python henalytics/manage.py generate_experimental_forecast --range month
python henalytics/manage.py generate_experimental_forecast --range three_months
```

Experimental web page:

```text
/forecasting/
```

The page loads the saved model artifact and displays future forecast output by chart and table. It does not train the model during an HTTP request.

## Model Artifacts

Saved model:

```text
ml/models/sarimax_clean_v1.pkl
```

Saved metadata:

```text
ml/models/sarimax_clean_v1.metadata.json
```

The metadata records the dataset hash, train date range, observation count, selected SARIMAX orders, MAE, RMSE, MAPE, Python version, and statsmodels version.

## Future Predictor Assumptions

When future exogenous values are not manually supplied, `predict.py` assumes:

- latest `Bird No.`
- `Dead = 0`
- `Cull = 0`
- latest `FEED (bags)`

These values are shown on the Forecasting page so the output is transparent.

## Rollback

To roll back the experimental ML feature, remove the `ml/` package, remove the `/forecasting/` route and sidebar link, and continue using the existing database-backed Analytics pages.

## Limitations

- Forecast quality depends on the cleaned CSV.
- The model forecasts future daily `Pieces`, not exact guaranteed production.
- Future values for bird count, dead birds, culls, and feed are assumptions unless supplied by the user.
- Shorter horizons are preferred for defense because uncertainty grows over time.
