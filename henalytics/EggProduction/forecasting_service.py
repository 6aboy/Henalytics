"""
Forecasting helpers for Henalytics.

The service reads the app's current operational tables and writes to the current
forecast tables. It intentionally avoids the older TimeSeriesData/Forecast schema.
"""
import logging
from datetime import timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
from django.db import models, transaction
from django.utils import timezone
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from statsmodels.tsa.arima.model import ARIMA

from .models import (
    GradingLog,
    HarvestForecast,
    ModelVersion,
    ProductionLog,
    SalesForecast,
    SalesItem,
)

logger = logging.getLogger(__name__)


class ForecastingService:
    """Generate simple ARIMA, MLR, or hybrid forecasts from stored farm records."""

    SALES_TYPES = {'sales', 'sales_volume', 'sales_price'}

    def __init__(self, flock, data_type='egg_production', forecast_type=None):
        self.flock = flock
        self.data_type = data_type
        self.forecast_type = forecast_type or data_type
        self.series = None
        self.values = None

    def prepare_data(self, lookback_days=365):
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=lookback_days)

        if self.data_type in self.SALES_TYPES:
            rows = (
                SalesItem.objects.filter(
                    transaction__flock=self.flock,
                    transaction__sale_date__range=(start_date, end_date),
                )
                .values(date=models.F('transaction__sale_date'))
                .annotate(value=models.Sum('quantity_trays'))
                .order_by('date')
            )
        elif self.data_type == 'grading':
            rows = (
                GradingLog.objects.filter(flock=self.flock, log_date__range=(start_date, end_date))
                .values(date=models.F('log_date'))
                .annotate(value=models.Sum('eggs_total'))
                .order_by('date')
            )
        elif self.data_type == 'hen_performance':
            rows = (
                ProductionLog.objects.filter(flock=self.flock, log_date__range=(start_date, end_date))
                .values(date=models.F('log_date'))
                .annotate(value=models.Avg('pct_hen_day'))
                .order_by('date')
            )
        else:
            rows = (
                ProductionLog.objects.filter(flock=self.flock, log_date__range=(start_date, end_date))
                .values(date=models.F('log_date'))
                .annotate(value=models.Sum('eggs_total'))
                .order_by('date')
            )

        if not rows:
            return False

        df = pd.DataFrame(rows)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').set_index('date')
        df = df.reindex(pd.date_range(df.index.min(), df.index.max(), freq='D'))
        df['value'] = df['value'].astype(float).interpolate(method='linear').ffill().bfill()

        self.series = df['value']
        self.values = self.series.to_numpy()
        return len(self.values) >= 10

    def forecast_arima(self, periods=30, order=(1, 1, 1)):
        if self.values is None and not self.prepare_data():
            return {'success': False, 'error': 'Insufficient data for forecasting'}

        try:
            model = ARIMA(self.values, order=order).fit()
            forecast_values = np.asarray(model.forecast(steps=periods), dtype=float)
            rmse, r_squared = self._score_arima(order)
            return {
                'success': True,
                'model_type': 'arima',
                'forecasted_values': forecast_values,
                'rmse': rmse,
                'r_squared': r_squared,
                'aic_score': float(model.aic),
                'arima_order': str(order),
            }
        except Exception as exc:
            logger.exception("ARIMA forecast failed")
            return {'success': False, 'error': str(exc)}

    def forecast_mlr(self, periods=30):
        if self.values is None and not self.prepare_data():
            return {'success': False, 'error': 'Insufficient data for forecasting'}

        try:
            n = len(self.values)
            x = np.arange(n).reshape(-1, 1)
            y = self.values
            model = LinearRegression().fit(x, y)
            future_x = np.arange(n, n + periods).reshape(-1, 1)
            forecast_values = model.predict(future_x)

            test_size = max(2, min(int(n * 0.2), n - 2))
            train_model = LinearRegression().fit(x[:-test_size], y[:-test_size])
            predictions = train_model.predict(x[-test_size:])
            rmse = float(np.sqrt(mean_squared_error(y[-test_size:], predictions)))
            r_squared = float(r2_score(y[-test_size:], predictions)) if test_size > 1 else None

            return {
                'success': True,
                'model_type': 'mlr',
                'forecasted_values': forecast_values,
                'rmse': rmse,
                'r_squared': r_squared,
                'aic_score': None,
                'arima_order': '',
            }
        except Exception as exc:
            logger.exception("MLR forecast failed")
            return {'success': False, 'error': str(exc)}

    def forecast_hybrid(self, periods=30):
        arima = self.forecast_arima(periods)
        mlr = self.forecast_mlr(periods)
        if not arima['success']:
            return mlr
        if not mlr['success']:
            return arima

        return {
            'success': True,
            'model_type': 'hybrid',
            'forecasted_values': (arima['forecasted_values'] + mlr['forecasted_values']) / 2,
            'rmse': (arima['rmse'] + mlr['rmse']) / 2,
            'r_squared': self._average_optional(arima['r_squared'], mlr['r_squared']),
            'aic_score': arima['aic_score'],
            'arima_order': arima['arima_order'],
        }

    def generate_forecast(self, model_type='hybrid', periods=30, user=None):
        if not self.prepare_data():
            return {'success': False, 'error': 'Insufficient data for forecasting'}

        if model_type == 'arima':
            result = self.forecast_arima(periods)
        elif model_type == 'mlr':
            result = self.forecast_mlr(periods)
        else:
            result = self.forecast_hybrid(periods)

        if not result['success']:
            return result

        with transaction.atomic():
            model_version = ModelVersion.objects.create(
                model_type=result['model_type'],
                triggered_by=user,
                r2_score=self._decimal_or_none(result['r_squared'], places=4),
                rmse=self._decimal_or_none(result['rmse'], places=2),
                aic_score=self._decimal_or_none(result['aic_score'], places=2),
                arima_order=result.get('arima_order', ''),
                training_rows=len(self.values),
                is_active=True,
            )

            forecast_ids = []
            start_date = timezone.now().date()
            for index, raw_value in enumerate(result['forecasted_values'], start=1):
                forecast_date = start_date + timedelta(days=index)
                value = max(0, int(round(float(raw_value))))

                if self.data_type in self.SALES_TYPES:
                    forecast = SalesForecast.objects.create(
                        model_version=model_version,
                        forecast_date=forecast_date,
                        grade='A',
                        predicted_trays=value,
                    )
                else:
                    forecast = HarvestForecast.objects.create(
                        flock=self.flock,
                        model_version=model_version,
                        forecast_date=forecast_date,
                        grade='A',
                        predicted_qty=value,
                    )
                forecast_ids.append(forecast.id)

        return {
            'success': True,
            'forecast_ids': forecast_ids,
            'model_type': result['model_type'],
            'rmse': result['rmse'],
            'r_squared': result['r_squared'],
        }

    def _score_arima(self, order):
        n = len(self.values)
        test_size = max(2, min(int(n * 0.2), n - 2))
        train_values = self.values[:-test_size]
        test_values = self.values[-test_size:]
        model = ARIMA(train_values, order=order).fit()
        predictions = np.asarray(model.forecast(steps=test_size), dtype=float)
        rmse = float(np.sqrt(mean_squared_error(test_values, predictions)))
        r_squared = float(r2_score(test_values, predictions)) if test_size > 1 else None
        return rmse, r_squared

    @staticmethod
    def _average_optional(first, second):
        values = [value for value in (first, second) if value is not None]
        return sum(values) / len(values) if values else None

    @staticmethod
    def _decimal_or_none(value, places):
        if value is None or np.isnan(value):
            return None
        quantizer = Decimal('1') if places == 0 else Decimal(f'0.{"0" * (places - 1)}1')
        return Decimal(str(value)).quantize(quantizer)
