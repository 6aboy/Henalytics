"""
Database-backed ARIMA forecasting helpers for Henalytics.

This first draft keeps the pipeline deliberately small: build daily time series
from saved production/sales records, fit ARIMA, and save forecast rows.
"""
import logging
import warnings
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

import numpy as np
import pandas as pd
from django.db import models, transaction
from django.utils import timezone
from sklearn.metrics import mean_squared_error, r2_score
from statsmodels.tools.sm_exceptions import ConvergenceWarning
from statsmodels.tsa.arima.model import ARIMA

from .models import (
    Flock,
    GradingLog,
    HarvestForecast,
    ModelVersion,
    ProductionLog,
    SalesForecast,
    SalesItem,
)

logger = logging.getLogger(__name__)


class ForecastingService:
    """Generate ARIMA forecasts from current database records."""

    MIN_POINTS = 10
    DEFAULT_ORDERS = ((1, 1, 1), (1, 0, 0), (0, 1, 1), (0, 0, 0))
    HORIZONS = {
        'week': 7,
        'month': 30,
        'three_months': 90,
        'six_months': 180,
        'year': 365,
    }
    EGG_GRADE_FIELDS = {
        'xl': 'eggs_aa',
        'large': 'eggs_a',
        'medium': 'eggs_b',
        'small': 'eggs_small',
        'broken': 'eggs_broken',
        'pewee': 'eggs_decode',
    }

    @classmethod
    def periods_for_range(cls, range_key, custom_start=None, custom_end=None):
        if range_key == 'custom' and custom_start and custom_end:
            days = (custom_end - custom_start).days + 1
            return max(days, 1)
        return cls.HORIZONS.get(range_key, 30)

    @classmethod
    def generate_egg_forecasts(cls, flock, periods=30, user=None, include_sizes=True):
        series_map = {'overall': cls._production_total_series(flock)}
        if include_sizes:
            series_map.update(cls._grading_size_series(flock))

        return cls._generate_series_forecasts(
            series_map=series_map,
            periods=periods,
            user=user,
            model_kind='egg',
            flock=flock,
        )

    @classmethod
    def generate_sales_forecasts(cls, periods=30, user=None, include_sizes=True):
        series_map = {'overall': cls._sales_amount_series()}
        if include_sizes:
            series_map.update(cls._sales_amount_series_by_grade())

        return cls._generate_series_forecasts(
            series_map=series_map,
            periods=periods,
            user=user,
            model_kind='sales',
        )

    @classmethod
    def generate_for_active_flocks(cls, data_type='egg', periods=30, user=None, include_sizes=True):
        if data_type == 'sales':
            return [cls.generate_sales_forecasts(periods=periods, user=user, include_sizes=include_sizes)]

        results = []
        for flock in Flock.objects.filter(status='active'):
            results.append(
                cls.generate_egg_forecasts(
                    flock=flock,
                    periods=periods,
                    user=user,
                    include_sizes=include_sizes,
                )
            )
        return results

    @classmethod
    def _generate_series_forecasts(cls, series_map, periods, user, model_kind, flock=None):
        created_ids = []
        errors = []
        model_versions = []

        for grade, series in series_map.items():
            prepared = cls._prepare_daily_series(series)
            if prepared is None:
                errors.append(f'{grade}: at least {cls.MIN_POINTS} dated records are required')
                continue

            result = cls._forecast_series(prepared, periods)
            if not result['success']:
                errors.append(f'{grade}: {result["error"]}')
                continue

            with transaction.atomic():
                model_version = ModelVersion.objects.create(
                    model_type='arima',
                    triggered_by=user,
                    r2_score=cls._decimal_or_none(result['r_squared'], 4, min_value=-9.9999, max_value=9.9999),
                    rmse=cls._decimal_or_none(result['rmse'], 2),
                    aic_score=cls._decimal_or_none(result['aic_score'], 2),
                    arima_order=str(result['order']),
                    training_rows=len(prepared),
                    is_active=True,
                )
                model_versions.append(model_version.id)

                start_date = timezone.now().date()
                for index, raw_value in enumerate(result['forecasted_values'], start=1):
                    forecast_date = start_date + timedelta(days=index)
                    if model_kind == 'sales':
                        amount = cls._decimal_money(max(float(raw_value), 0))
                        forecast = SalesForecast.objects.create(
                            model_version=model_version,
                            forecast_date=forecast_date,
                            grade=grade,
                            predicted_trays=0,
                            predicted_amount=amount,
                        )
                    else:
                        forecast = HarvestForecast.objects.create(
                            flock=flock,
                            model_version=model_version,
                            forecast_date=forecast_date,
                            grade=grade,
                            predicted_qty=max(0, int(round(float(raw_value)))),
                        )
                    created_ids.append(forecast.id)

        return {
            'success': bool(created_ids),
            'forecast_ids': created_ids,
            'model_version_ids': model_versions,
            'errors': errors,
            'created_count': len(created_ids),
        }

    @classmethod
    def _forecast_series(cls, series, periods):
        best = None
        for order in cls.DEFAULT_ORDERS:
            try:
                model = cls._fit_arima(series.to_numpy(dtype=float), order)
                if best is None or model.aic < best['model'].aic:
                    best = {'model': model, 'order': order}
            except Exception:
                logger.debug("ARIMA order %s failed", order, exc_info=True)

        if best is None:
            return {'success': False, 'error': 'ARIMA could not fit this series'}

        forecast_values = np.asarray(best['model'].forecast(steps=periods), dtype=float)
        rmse, r_squared = cls._score_series(series, best['order'])
        return {
            'success': True,
            'forecasted_values': forecast_values,
            'order': best['order'],
            'aic_score': float(best['model'].aic),
            'rmse': rmse,
            'r_squared': r_squared,
        }

    @classmethod
    def _score_series(cls, series, order):
        values = series.to_numpy(dtype=float)
        test_size = max(2, min(int(len(values) * 0.2), len(values) - 2))
        try:
            model = cls._fit_arima(values[:-test_size], order)
            predictions = np.asarray(model.forecast(steps=test_size), dtype=float)
            rmse = float(np.sqrt(mean_squared_error(values[-test_size:], predictions)))
            r_squared = float(r2_score(values[-test_size:], predictions)) if test_size > 1 else None
            return rmse, r_squared
        except Exception:
            logger.debug("ARIMA scoring failed", exc_info=True)
            return None, None

    @staticmethod
    def _fit_arima(values, order):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            warnings.simplefilter('ignore', ConvergenceWarning)
            return ARIMA(values, order=order).fit()

    @classmethod
    def _prepare_daily_series(cls, rows):
        if not rows:
            return None

        df = pd.DataFrame(rows)
        if df.empty:
            return None

        df['date'] = pd.to_datetime(df['date'])
        df['value'] = df['value'].fillna(0).astype(float)
        df = df.groupby('date', as_index=True)['value'].sum().sort_index().to_frame()
        df = df.reindex(pd.date_range(df.index.min(), df.index.max(), freq='D'), fill_value=0)

        if len(df) < cls.MIN_POINTS:
            return None

        return df['value']

    @staticmethod
    def _production_total_series(flock):
        return (
            ProductionLog.objects.filter(flock=flock)
            .values(date=models.F('log_date'))
            .annotate(value=models.Sum('eggs_total'))
            .order_by('date')
        )

    @classmethod
    def _grading_size_series(cls, flock):
        series = {}
        for grade, field_name in cls.EGG_GRADE_FIELDS.items():
            rows = (
                GradingLog.objects.filter(flock=flock)
                .values(date=models.F('log_date'))
                .annotate(value=models.Sum(field_name))
                .order_by('date')
            )
            if rows:
                series[grade] = rows
        return series

    @staticmethod
    def _sales_amount_series():
        return (
            SalesItem.objects.values(date=models.F('transaction__sale_date'))
            .annotate(value=models.Sum('amount'))
            .order_by('date')
        )

    @staticmethod
    def _sales_amount_series_by_grade():
        series = {}
        grades = (
            SalesItem.objects.values_list('grade', flat=True)
            .order_by('grade')
            .distinct()
        )
        for grade in grades:
            series[grade] = (
                SalesItem.objects.filter(grade=grade)
                .values(date=models.F('transaction__sale_date'))
                .annotate(value=models.Sum('amount'))
                .order_by('date')
            )
        return series

    @staticmethod
    def _decimal_money(value):
        return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def _decimal_or_none(value, places, min_value=None, max_value=None):
        if value is None:
            return None
        try:
            if np.isnan(value):
                return None
        except TypeError:
            pass
        if min_value is not None and value < min_value:
            return None
        if max_value is not None and value > max_value:
            return None
        quantizer = Decimal('1') if places == 0 else Decimal(f'0.{"0" * (places - 1)}1')
        return Decimal(str(value)).quantize(quantizer, rounding=ROUND_HALF_UP)
