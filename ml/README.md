# Henalytics ML Draft

This folder contains the standalone machine-learning draft for egg production forecasting.

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
