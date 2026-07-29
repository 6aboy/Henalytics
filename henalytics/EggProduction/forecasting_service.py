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
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from statsmodels.tools.sm_exceptions import ConvergenceWarning
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.statespace.sarimax import SARIMAX

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
    SEASONAL_PERIOD = 7
    SEASONAL_ORDERS = ((1, 0, 1, SEASONAL_PERIOD), (0, 1, 1, SEASONAL_PERIOD))
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
    EGG_FEATURE_FIELDS = (
        'age_weeks',
        'age_days',
        'dead_count',
        'culled_count',
        'hen_count',
        'feed_bags',
        'pct_hen_day',
        'pct_hen_housed',
    )

    @classmethod
    def periods_for_range(cls, range_key, custom_start=None, custom_end=None):
        if range_key == 'custom' and custom_start and custom_end:
            days = (custom_end - custom_start).days + 1
            return max(days, 1)
        return cls.HORIZONS.get(range_key, 30)

    @classmethod
    def generate_egg_forecasts(cls, flock, periods=30, user=None, include_sizes=True):
        series_map = cls._egg_series_map(flock, include_sizes=include_sizes)
        forecast_start_date = cls._latest_production_date(flock)
        if forecast_start_date:
            forecast_start_date += timedelta(days=1)

        return cls._generate_series_forecasts(
            series_map=series_map,
            periods=periods,
            user=user,
            model_kind='egg',
            flock=flock,
            forecast_start_date=forecast_start_date,
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
    def evaluate_egg_forecasts(cls, flock, include_sizes=True):
        series_map = cls._egg_series_map(flock, include_sizes=include_sizes)
        return cls._evaluate_series_map(series_map, allow_seasonal=True, use_exog=True)

    @classmethod
    def evaluate_sales_forecasts(cls, include_sizes=True):
        series_map = {'overall': cls._sales_amount_series()}
        if include_sizes:
            series_map.update(cls._sales_amount_series_by_grade())
        return cls._evaluate_series_map(series_map, allow_seasonal=False, use_exog=False)

    @classmethod
    def _generate_series_forecasts(cls, series_map, periods, user, model_kind, flock=None, forecast_start_date=None):
        created_ids = []
        errors = []
        model_versions = []
        required_rows = cls._min_history_for_periods(periods)

        cls._clear_previous_forecasts(model_kind, flock)

        for grade, series in series_map.items():
            prepared = cls._prepare_daily_dataset(series, use_exog=model_kind == 'egg')
            if prepared is None:
                errors.append(f'{grade}: at least {cls.MIN_POINTS} dated records are required')
                continue
            if len(prepared['series']) < required_rows:
                errors.append(f'{grade}: {required_rows} historical days are required for a {periods}-day forecast')
                continue

            result = cls._forecast_series(
                prepared,
                periods,
                allow_seasonal=model_kind == 'egg',
                forecast_start_date=forecast_start_date,
            )
            if not result['success']:
                errors.append(f'{grade}: {result["error"]}')
                continue

            with transaction.atomic():
                model_version = ModelVersion.objects.create(
                    model_type='arima',
                    triggered_by=user,
                    r2_score=cls._decimal_or_none(result['r_squared'], 4, min_value=-9.9999, max_value=9.9999),
                    rmse=cls._decimal_or_none(result['rmse'], 2),
                    mae=cls._decimal_or_none(result.get('mae'), 2),
                    mape=cls._decimal_or_none(result.get('mape'), 2),
                    baseline_rmse=cls._decimal_or_none(result.get('baseline_rmse'), 2),
                    aic_score=cls._decimal_or_none(result['aic_score'], 2),
                    arima_order=str(result['order']),
                    training_rows=len(prepared['series']),
                    is_active=True,
                )
                model_versions.append(model_version.id)

                start_date = result['start_date']
                for index, raw_value in enumerate(result['forecasted_values'], start=1):
                    forecast_date = start_date + timedelta(days=index - 1)
                    lower_value = result.get('lower_values', [None] * periods)[index - 1]
                    upper_value = result.get('upper_values', [None] * periods)[index - 1]
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
                            lower_qty=cls._int_or_none(lower_value),
                            upper_qty=cls._int_or_none(upper_value),
                        )
                    created_ids.append(forecast.id)

        return {
            'success': bool(created_ids),
            'forecast_ids': created_ids,
            'model_version_ids': model_versions,
            'errors': errors,
            'created_count': len(created_ids),
        }

    @staticmethod
    def _clear_previous_forecasts(model_kind, flock=None):
        if model_kind == 'sales':
            SalesForecast.objects.all().delete()
        elif flock is not None:
            HarvestForecast.objects.filter(flock=flock).delete()

    @classmethod
    def _forecast_series(cls, prepared, periods, allow_seasonal=False, forecast_start_date=None):
        series = prepared['series']
        exog = prepared['exog']
        best = None
        for spec in cls._candidate_model_specs(len(series), allow_seasonal):
            try:
                model = cls._fit_model(series.to_numpy(dtype=float), spec, exog=exog)
                if best is None or model.aic < best['model'].aic:
                    best = {'model': model, 'spec': spec}
            except Exception:
                logger.debug("Time-series model %s failed", spec, exc_info=True)

        if best is None:
            return {'success': False, 'error': 'ARIMA could not fit this series'}

        future_exog = cls._future_exog(exog, periods)
        forecast_values, lower_values, upper_values = cls._forecast_values_with_intervals(
            best['model'],
            periods,
            future_exog=future_exog,
        )
        metrics = cls._score_series(prepared, best['spec'])
        return {
            'success': True,
            'forecasted_values': forecast_values,
            'lower_values': lower_values,
            'upper_values': upper_values,
            'order': cls._format_model_spec(best['spec'], uses_exog=exog is not None),
            'aic_score': float(best['model'].aic),
            'rmse': metrics['rmse'],
            'mae': metrics['mae'],
            'mape': metrics['mape'],
            'baseline_rmse': metrics['baseline_rmse'],
            'r_squared': metrics['r_squared'],
            'start_date': forecast_start_date or series.index.max().date() + timedelta(days=1),
        }

    @classmethod
    def _forecast_values_with_intervals(cls, fitted_model, periods, future_exog=None):
        forecast_result = fitted_model.get_forecast(steps=periods, exog=future_exog)
        forecast_values = np.asarray(forecast_result.predicted_mean, dtype=float)
        try:
            confidence = np.asarray(forecast_result.conf_int(alpha=0.20), dtype=float)
            lower_values = np.maximum(confidence[:, 0], 0)
            upper_values = np.maximum(confidence[:, 1], lower_values)
        except Exception:
            logger.debug("Forecast interval calculation failed", exc_info=True)
            lower_values = np.full(periods, np.nan)
            upper_values = np.full(periods, np.nan)
        return forecast_values, lower_values, upper_values

    @classmethod
    def _fallback_forecast_if_needed(cls, series, forecast_values, periods, model_rmse, forecast_start_date=None):
        if not len(forecast_values):
            return None

        recent = series.tail(min(60, len(series))).to_numpy(dtype=float)
        recent_mean = float(np.mean(recent)) if len(recent) else 0
        trend_fallback = cls._trend_forecast_if_model_is_flat(series, forecast_values, periods, model_rmse, forecast_start_date)
        if trend_fallback is not None:
            return trend_fallback

        if periods < 90:
            return None

        zero_share = float(np.mean(forecast_values <= 0))
        final_value = float(forecast_values[-1])
        collapsed = zero_share > 0.10 or (recent_mean and final_value < recent_mean * 0.35)
        if not collapsed:
            return None

        baseline_values = cls._seasonal_naive_forecast(series, periods)
        baseline_rmse, baseline_r2 = cls._score_seasonal_naive(series)
        if model_rmse is not None and baseline_rmse is not None and baseline_rmse > model_rmse and zero_share <= 0.25:
            return None

        return {
            'success': True,
            'forecasted_values': baseline_values,
            'lower_values': cls._interval_from_rmse(baseline_values, baseline_rmse),
            'upper_values': cls._interval_from_rmse(baseline_values, baseline_rmse, upper=True),
            'order': 'seasonal naive baseline (7-day)',
            'aic_score': None,
            'rmse': baseline_rmse,
            'mae': None,
            'mape': None,
            'baseline_rmse': baseline_rmse,
            'r_squared': baseline_r2,
            'start_date': forecast_start_date or series.index.max().date() + timedelta(days=1),
        }

    @classmethod
    def _trend_forecast_if_model_is_flat(cls, series, forecast_values, periods, model_rmse, forecast_start_date=None):
        values = series.to_numpy(dtype=float)
        if len(values) < cls.MIN_POINTS:
            return None

        window_size = min(30, len(values))
        recent = values[-window_size:]
        recent_mean = float(np.mean(recent)) if len(recent) else 0
        if recent_mean <= 0:
            return None

        x_values = np.arange(window_size, dtype=float)
        slope, intercept = np.polyfit(x_values, recent, 1)
        recent_change_pct = ((recent[-1] - recent[0]) / recent[0] * 100) if recent[0] else 0

        forecast_slope = (
            (float(forecast_values[-1]) - float(forecast_values[0])) / max(len(forecast_values) - 1, 1)
            if len(forecast_values) > 1
            else 0
        )
        forecast_change_pct = (
            (float(forecast_values[-1]) - float(forecast_values[0])) / float(forecast_values[0]) * 100
            if forecast_values[0]
            else 0
        )

        strong_recent_trend = abs(recent_change_pct) >= 12 and abs(slope) >= recent_mean * 0.005
        model_is_flat = abs(forecast_change_pct) < max(3, abs(recent_change_pct) * 0.25)
        model_opposes_trend = slope and forecast_slope and np.sign(slope) != np.sign(forecast_slope)
        if not strong_recent_trend or not (model_is_flat or model_opposes_trend):
            return None

        # Damping keeps the short data trend visible without unrealistically accelerating far into the future.
        damping = np.linspace(0.85, 0.35, periods)
        steps = np.arange(1, periods + 1, dtype=float)
        trend_values = recent[-1] + (slope * steps * damping)
        trend_values = np.maximum(trend_values, 0)
        trend_rmse, trend_r2 = cls._score_trend_baseline(series)

        return {
            'success': True,
            'forecasted_values': trend_values,
            'lower_values': cls._interval_from_rmse(trend_values, trend_rmse if trend_rmse is not None else model_rmse),
            'upper_values': cls._interval_from_rmse(trend_values, trend_rmse if trend_rmse is not None else model_rmse, upper=True),
            'order': 'trend-adjusted ARIMA fallback',
            'aic_score': None,
            'rmse': trend_rmse if trend_rmse is not None else model_rmse,
            'mae': None,
            'mape': None,
            'baseline_rmse': None,
            'r_squared': trend_r2,
            'start_date': forecast_start_date or series.index.max().date() + timedelta(days=1),
        }

    @classmethod
    def _score_trend_baseline(cls, series):
        values = series.to_numpy(dtype=float)
        test_size = max(2, min(int(len(values) * 0.2), len(values) - 2))
        if len(values) < cls.MIN_POINTS or test_size <= 0:
            return None, None

        train = values[:-test_size]
        test = values[-test_size:]
        window_size = min(30, len(train))
        recent = train[-window_size:]
        x_values = np.arange(window_size, dtype=float)
        slope, _intercept = np.polyfit(x_values, recent, 1)
        damping = np.linspace(0.85, 0.35, test_size)
        steps = np.arange(1, test_size + 1, dtype=float)
        predictions = np.maximum(train[-1] + (slope * steps * damping), 0)
        rmse = float(np.sqrt(mean_squared_error(test, predictions)))
        r_squared = float(r2_score(test, predictions)) if test_size > 1 else None
        return rmse, r_squared

    @classmethod
    def _seasonal_naive_forecast(cls, series, periods):
        values = series.to_numpy(dtype=float)
        window = values[-cls.SEASONAL_PERIOD:] if len(values) >= cls.SEASONAL_PERIOD else values[-1:]
        repeated = np.resize(window, periods)
        return repeated.astype(float)

    @classmethod
    def _seasonal_naive_from_train(cls, train_values, periods):
        train_values = np.asarray(train_values, dtype=float)
        window = train_values[-cls.SEASONAL_PERIOD:] if len(train_values) >= cls.SEASONAL_PERIOD else train_values[-1:]
        return np.resize(window, periods).astype(float)

    @staticmethod
    def _interval_from_rmse(values, rmse, upper=False):
        values = np.asarray(values, dtype=float)
        if rmse is None:
            padding = np.maximum(values * 0.12, 1)
        else:
            padding = max(float(rmse) * 1.28, 1)
        if upper:
            return values + padding
        return np.maximum(values - padding, 0)

    @classmethod
    def _score_seasonal_naive(cls, series):
        values = series.to_numpy(dtype=float)
        test_size = max(2, min(int(len(values) * 0.2), len(values) - 2))
        if len(values) <= cls.SEASONAL_PERIOD or test_size <= 0:
            return None, None

        train = values[:-test_size]
        test = values[-test_size:]
        window = train[-cls.SEASONAL_PERIOD:] if len(train) >= cls.SEASONAL_PERIOD else train[-1:]
        predictions = np.resize(window, test_size).astype(float)
        rmse = float(np.sqrt(mean_squared_error(test, predictions)))
        r_squared = float(r2_score(test, predictions)) if test_size > 1 else None
        return rmse, r_squared

    @classmethod
    def _score_series(cls, prepared, spec):
        series = prepared['series']
        exog = prepared['exog']
        values = series.to_numpy(dtype=float)
        test_size = max(2, min(int(len(values) * 0.2), len(values) - 2))
        empty = {
            'rmse': None,
            'mae': None,
            'mape': None,
            'baseline_rmse': None,
            'r_squared': None,
        }
        try:
            train_exog = exog.iloc[:-test_size] if exog is not None else None
            test_exog = exog.iloc[-test_size:] if exog is not None else None
            model = cls._fit_model(values[:-test_size], spec, exog=train_exog)
            predictions = np.asarray(model.forecast(steps=test_size, exog=test_exog), dtype=float)
            actual = values[-test_size:]
            metrics = cls._prediction_metrics(actual, predictions)
            baseline_predictions = cls._seasonal_naive_from_train(values[:-test_size], test_size)
            baseline_metrics = cls._prediction_metrics(actual, baseline_predictions)
            return {
                'rmse': metrics['rmse'],
                'mae': metrics['mae'],
                'mape': metrics['mape'],
                'baseline_rmse': baseline_metrics['rmse'],
                'r_squared': metrics['r2'],
            }
        except Exception:
            logger.debug("ARIMA scoring failed", exc_info=True)
            return empty

    @classmethod
    def _evaluate_series_map(cls, series_map, allow_seasonal=False, use_exog=False):
        results = []
        for category, rows in series_map.items():
            prepared = cls._prepare_daily_dataset(rows, use_exog=use_exog)
            if prepared is None:
                results.append({
                    'category': category,
                    'success': False,
                    'error': f'at least {cls.MIN_POINTS} dated records are required',
                })
                continue

            evaluation = cls._evaluate_series(prepared, allow_seasonal=allow_seasonal)
            evaluation['category'] = category
            results.append(evaluation)
        return results

    @classmethod
    def _evaluate_series(cls, prepared, allow_seasonal=False):
        series = prepared['series']
        exog = prepared['exog']
        values = series.to_numpy(dtype=float)
        test_size = max(2, min(int(len(values) * 0.2), len(values) - 2))
        train = values[:-test_size]
        test = values[-test_size:]
        train_exog = exog.iloc[:-test_size] if exog is not None else None
        test_exog = exog.iloc[-test_size:] if exog is not None else None

        best = None
        for spec in cls._candidate_model_specs(len(train), allow_seasonal):
            try:
                model = cls._fit_model(train, spec, exog=train_exog)
                if best is None or model.aic < best['model'].aic:
                    best = {'model': model, 'spec': spec}
            except Exception:
                logger.debug("Evaluation model %s failed", spec, exc_info=True)

        if best is None:
            return {
                'success': False,
                'error': 'ARIMA could not fit this series',
            }

        arima_predictions = np.asarray(best['model'].forecast(steps=test_size, exog=test_exog), dtype=float)
        baseline_predictions = np.repeat(train[-1], test_size)

        arima_metrics = cls._prediction_metrics(test, arima_predictions)
        baseline_metrics = cls._prediction_metrics(test, baseline_predictions)
        arima_beats_baseline = arima_metrics['rmse'] < baseline_metrics['rmse']

        return {
            'success': True,
            'rows': len(values),
            'test_rows': test_size,
            'model_order': cls._format_model_spec(best['spec'], uses_exog=exog is not None),
            'uses_features': exog is not None,
            'arima': arima_metrics,
            'baseline': baseline_metrics,
            'winner': 'ARIMA' if arima_beats_baseline else 'Baseline',
            'improvement_pct': cls._improvement_percent(
                baseline_metrics['rmse'],
                arima_metrics['rmse'],
            ),
        }

    @staticmethod
    def _prediction_metrics(actual, predicted):
        rmse = float(np.sqrt(mean_squared_error(actual, predicted)))
        mae = float(mean_absolute_error(actual, predicted))
        r_squared = float(r2_score(actual, predicted)) if len(actual) > 1 else None
        nonzero = actual != 0
        mape = (
            float(np.mean(np.abs((actual[nonzero] - predicted[nonzero]) / actual[nonzero])) * 100)
            if nonzero.any()
            else None
        )
        return {
            'rmse': rmse,
            'mae': mae,
            'r2': r_squared,
            'mape': mape,
        }

    @staticmethod
    def _improvement_percent(baseline_rmse, arima_rmse):
        if baseline_rmse == 0:
            return None
        return float((baseline_rmse - arima_rmse) / baseline_rmse * 100)

    @classmethod
    def _min_history_for_periods(cls, periods):
        return min(max(cls.MIN_POINTS, periods), 90)

    @staticmethod
    def _fit_arima(values, order):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            warnings.simplefilter('ignore', ConvergenceWarning)
            return ARIMA(values, order=order).fit()

    @staticmethod
    def _fit_sarima(values, order, seasonal_order, exog=None):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            warnings.simplefilter('ignore', ConvergenceWarning)
            return SARIMAX(
                values,
                exog=exog,
                order=order,
                seasonal_order=seasonal_order,
                enforce_stationarity=False,
                enforce_invertibility=False,
            ).fit(disp=False)

    @classmethod
    def _fit_model(cls, values, spec, exog=None):
        if spec['seasonal_order'] is None and exog is None:
            return cls._fit_arima(values, spec['order'])
        return cls._fit_sarima(
            values,
            spec['order'],
            spec['seasonal_order'] or (0, 0, 0, 0),
            exog=exog,
        )

    @classmethod
    def _candidate_model_specs(cls, series_length, allow_seasonal):
        nonseasonal_specs = [{'order': order, 'seasonal_order': None} for order in cls.DEFAULT_ORDERS]
        if allow_seasonal and series_length >= cls.SEASONAL_PERIOD * 4:
            specs = []
            for order in cls.DEFAULT_ORDERS[:3]:
                for seasonal_order in cls.SEASONAL_ORDERS:
                    specs.append({'order': order, 'seasonal_order': seasonal_order})
            specs.extend(nonseasonal_specs)
            return specs
        return nonseasonal_specs

    @staticmethod
    def _format_model_spec(spec, uses_exog=False):
        order = spec['order']
        seasonal_order = spec['seasonal_order']
        suffix = ' + features' if uses_exog else ''
        if seasonal_order is None:
            return f'{order}{suffix}'
        return f'{order}x{seasonal_order}{suffix}'

    @classmethod
    def _prepare_daily_series(cls, rows):
        prepared = cls._prepare_daily_dataset(rows, use_exog=False)
        return prepared['series'] if prepared else None

    @classmethod
    def _prepare_daily_dataset(cls, rows, use_exog=False):
        if not rows:
            return None

        df = pd.DataFrame(rows)
        if df.empty:
            return None

        df['date'] = pd.to_datetime(df['date'])
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        observed_count = int(df['value'].notna().sum())
        if observed_count < cls.MIN_POINTS:
            return None

        aggregations = {'value': lambda values: values.sum(min_count=1)}
        if use_exog:
            for field_name in cls.EGG_FEATURE_FIELDS:
                if field_name in df.columns:
                    df[field_name] = pd.to_numeric(df[field_name], errors='coerce')
                    aggregations[field_name] = 'mean'

        df = df.groupby('date', as_index=True).agg(aggregations).sort_index()
        df = df.reindex(pd.date_range(df.index.min(), df.index.max(), freq='D'))
        df = df.interpolate(method='time').ffill().bfill()

        if len(df) < cls.MIN_POINTS or df['value'].isna().all():
            return None

        exog = None
        feature_columns = [field for field in cls.EGG_FEATURE_FIELDS if field in df.columns]
        if use_exog and feature_columns:
            exog = df[feature_columns].shift(1).ffill().bfill()

        return {'series': df['value'], 'exog': exog}

    @staticmethod
    def _future_exog(exog, periods):
        if exog is None:
            return None
        last_row = exog.iloc[[-1]]
        return pd.concat([last_row] * periods, ignore_index=True)

    @classmethod
    def _egg_series_map(cls, flock, include_sizes=True):
        series_map = {'overall': cls._production_total_series(flock)}
        if include_sizes:
            series_map.update(cls._grading_size_series(flock))
        return series_map

    @staticmethod
    def _production_total_series(flock):
        return (
            ProductionLog.objects.filter(flock=flock)
            .values(
                'age_weeks',
                'age_days',
                'dead_count',
                'culled_count',
                'hen_count',
                'feed_bags',
                'pct_hen_day',
                'pct_hen_housed',
                date=models.F('log_date'),
            )
            .annotate(value=models.Sum('eggs_total'))
            .order_by('date')
        )

    @staticmethod
    def _latest_production_date(flock):
        return (
            ProductionLog.objects.filter(flock=flock)
            .order_by('-log_date')
            .values_list('log_date', flat=True)
            .first()
        )

    @classmethod
    def _grading_size_series(cls, flock):
        series = {}
        production_features = {
            row['log_date']: row
            for row in ProductionLog.objects.filter(flock=flock).values(
                'log_date',
                'age_weeks',
                'age_days',
                'dead_count',
                'culled_count',
                'hen_count',
                'feed_bags',
                'pct_hen_day',
                'pct_hen_housed',
            )
        }
        for grade, field_name in cls.EGG_GRADE_FIELDS.items():
            rows = (
                GradingLog.objects.filter(flock=flock)
                .values(date=models.F('log_date'))
                .annotate(value=models.Sum(field_name))
                .order_by('date')
            )
            if rows:
                enriched_rows = []
                for row in rows:
                    enriched = dict(row)
                    features = production_features.get(row['date'])
                    if features:
                        for feature_name in cls.EGG_FEATURE_FIELDS:
                            if feature_name in features:
                                enriched[feature_name] = features[feature_name]
                    enriched_rows.append(enriched)
                series[grade] = enriched_rows
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

    @staticmethod
    def _int_or_none(value):
        if value is None:
            return None
        try:
            if np.isnan(value):
                return None
        except TypeError:
            pass
        return max(0, int(round(float(value))))
