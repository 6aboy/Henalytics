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
    EGG_USE_SEASONALITY = False
    SALES_USE_SEASONALITY = True
    OUTLIER_WINDOW_DAYS = 14
    OUTLIER_MIN_HISTORY_DAYS = 7
    OUTLIER_RELATIVE_BAND = 0.35
    EGG_RATE_LOOKBACK_DAYS = 21
    EGG_RATE_SIMILAR_ROWS = 10
    EGG_RATE_MIN_PERCENT = 5
    EGG_RATE_MAX_PERCENT = 92
    EGG_RATE_MAX_DAILY_CHANGE = 2.0
    EGG_RATE_SHOCK_THRESHOLD = 0.55
    HORIZONS = {
        'week': 7,
        'three_weeks': 21,
        'month': 30,
        'three_months': 90,
    }
    EGG_SOURCE_FEATURE_FIELDS = (
        # Poultry performance predictors used by the SARIMAX egg forecast.
        'age_weeks',
        'age_days',
        'hen_count',
        'dead_count',
        'culled_count',
        'feed_bags',
    )
    EGG_DERIVED_FEATURE_FIELDS = (
        # These are useful diagnostics, but are calculated from production and are tested separately.
        'pct_hen_day',
        'pct_hen_housed',
        'fcr',
    )
    EGG_TIME_FEATURE_FIELDS = (
        # Trend-only egg predictor. Weekly seasonality is intentionally tested separately, not forced.
        'trend_day',
    )
    EGG_FEATURE_FIELDS = EGG_SOURCE_FEATURE_FIELDS + EGG_DERIVED_FEATURE_FIELDS + EGG_TIME_FEATURE_FIELDS
    EGG_SAFE_FEATURE_FIELDS = EGG_SOURCE_FEATURE_FIELDS + EGG_TIME_FEATURE_FIELDS
    EGG_DIAGNOSTIC_FEATURE_FIELDS = EGG_FEATURE_FIELDS
    EGG_DATABASE_FEATURE_FIELDS = EGG_SOURCE_FEATURE_FIELDS + EGG_DERIVED_FEATURE_FIELDS
    SALES_SOURCE_FEATURE_FIELDS = (
        # Lagged sales predictors: known historical behavior carried into the forecast.
        'quantity_pieces',
        'avg_unit_price',
        'transaction_count',
    )
    SALES_TIME_FEATURE_FIELDS = (
        # Calendar/trend predictors help revenue models see weekday and monthly rhythm.
        'trend_day',
        'weekday_sin',
        'weekday_cos',
        'month_sin',
        'month_cos',
    )
    SALES_FEATURE_FIELDS = SALES_SOURCE_FEATURE_FIELDS + SALES_TIME_FEATURE_FIELDS
    SALES_SAFE_FEATURE_FIELDS = SALES_FEATURE_FIELDS
    SALES_DATABASE_FEATURE_FIELDS = SALES_SOURCE_FEATURE_FIELDS

    @classmethod
    def periods_for_range(cls, range_key, custom_start=None, custom_end=None):
        if range_key == 'custom' and custom_start and custom_end:
            days = (custom_end - custom_start).days + 1
            return max(days, 1)
        return cls.HORIZONS.get(range_key, 30)

    @classmethod
    def generate_egg_forecasts(cls, flock, periods=30, user=None, include_sizes=False):
        series_map = cls._egg_series_map(flock)
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
        forecast_start_date = cls._latest_sales_date()
        if forecast_start_date:
            forecast_start_date += timedelta(days=1)

        return cls._generate_series_forecasts(
            series_map=series_map,
            periods=periods,
            user=user,
            model_kind='sales',
            forecast_start_date=forecast_start_date,
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
    def evaluate_egg_forecasts(cls, flock, include_sizes=False):
        series_map = cls._egg_series_map(flock)
        return cls._evaluate_series_map(series_map, allow_seasonal=cls.EGG_USE_SEASONALITY, use_exog=True)

    @classmethod
    def evaluate_sales_forecasts(cls, include_sizes=True):
        series_map = {'overall': cls._sales_amount_series()}
        if include_sizes:
            series_map.update(cls._sales_amount_series_by_grade())
        return cls._evaluate_series_map(series_map, allow_seasonal=True, use_exog=True, dataset_kind='sales')

    @classmethod
    def _generate_series_forecasts(cls, series_map, periods, user, model_kind, flock=None, forecast_start_date=None):
        created_ids = []
        errors = []
        model_versions = []
        required_rows = cls._min_history_for_periods(periods)

        cls._clear_previous_forecasts(model_kind, flock)

        for grade, series in series_map.items():
            prepared = cls._prepare_daily_dataset(series, use_exog=model_kind in ('egg', 'sales'), dataset_kind=model_kind)
            if prepared is None:
                errors.append(f'{grade}: at least {cls.MIN_POINTS} dated records are required')
                continue
            if len(prepared['series']) < required_rows:
                errors.append(f'{grade}: {required_rows} historical days are required for a {periods}-day forecast')
                continue

            result = cls._forecast_series(
                prepared,
                periods,
                allow_seasonal=cls._uses_seasonality(model_kind),
                compare_models=model_kind in ('egg', 'sales'),
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
                    feature_set=result.get('feature_set', ''),
                    selection_metric=result.get('selection_metric', 'rolling_mae_mape'),
                    comparison_summary=result.get('comparison_summary') or {},
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
    def _forecast_series(cls, prepared, periods, allow_seasonal=False, compare_models=False, forecast_start_date=None):
        series = prepared['series']
        selection = cls._select_forecast_candidate(prepared, allow_seasonal=allow_seasonal, compare_models=compare_models)
        best = selection['candidate'] if selection else None

        if best is None:
            return {'success': False, 'error': 'ARIMA could not fit this series'}

        exog = cls._exog_for_candidate(prepared, best)
        future_exog = cls._future_exog(exog, periods)
        forecast_values, lower_values, upper_values = cls._forecast_values_with_intervals(
            best['model'],
            periods,
            future_exog=future_exog,
        )
        metrics = best.get('metrics') or cls._score_series(prepared, best['spec'], feature_set=best.get('feature_set', 'all'))
        rate_limits = cls._egg_rate_capacity_limits(prepared, periods)
        fallback = cls._fallback_forecast_if_needed(
            series,
            forecast_values,
            periods,
            metrics,
            forecast_start_date=forecast_start_date,
            exog=exog,
            allow_seasonal=allow_seasonal,
            rate_limits=rate_limits,
        )
        if fallback is not None and (prepared.get('dataset_kind') == 'egg' or not compare_models):
            fallback.setdefault('feature_set', best.get('feature_set', ''))
            fallback.setdefault('selection_metric', 'rolling_mae_mape' if compare_models else 'aic')
            fallback.setdefault('comparison_summary', selection.get('comparison_summary') if selection else {})
            return fallback

        if prepared.get('dataset_kind') == 'egg':
            forecast_values, lower_values, upper_values = cls._apply_egg_rate_limits(
                forecast_values,
                lower_values,
                upper_values,
                rate_limits,
            )

        return {
            'success': True,
            'forecasted_values': forecast_values,
            'lower_values': lower_values,
            'upper_values': upper_values,
            'order': cls._format_candidate_label(best),
            'aic_score': float(best['model'].aic),
            'rmse': metrics['rmse'],
            'mae': metrics['mae'],
            'mape': metrics['mape'],
            'baseline_rmse': metrics['baseline_rmse'],
            'r_squared': metrics['r_squared'],
            'feature_set': best.get('feature_set', ''),
            'selection_metric': 'rolling_mae_mape' if compare_models else 'aic',
            'comparison_summary': selection.get('comparison_summary') if selection else {},
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
    def _select_forecast_candidate(cls, prepared, allow_seasonal=False, compare_models=False):
        series = prepared['series']
        values = series.to_numpy(dtype=float)
        if not compare_models:
            return cls._select_lowest_aic_candidate(prepared, allow_seasonal)

        candidates = cls._web_forecast_candidates(len(series), allow_seasonal, prepared.get('dataset_kind', 'egg'))
        comparison_candidates = []
        forecast_candidates = []
        for candidate in candidates:
            metrics = cls._rolling_backtest(prepared, candidate)
            if metrics.get('mae') is None:
                continue
            comparison_candidates.append({**candidate, 'metrics': metrics})
            if candidate['kind'] == 'baseline' or candidate.get('feature_set') == 'diagnostic':
                continue
            if prepared.get('dataset_kind') == 'egg' and candidate.get('feature_set') != 'safe':
                continue
            try:
                exog = cls._exog_for_candidate(prepared, candidate)
                model = cls._fit_model(values, candidate['spec'], exog=exog)
                candidate = {**candidate, 'model': model, 'metrics': metrics}
                forecast_candidates.append(candidate)
            except Exception:
                logger.debug("Final model fit failed for %s", candidate, exc_info=True)

        if not forecast_candidates:
            return cls._select_lowest_aic_candidate(prepared, allow_seasonal)

        best = min(
            forecast_candidates,
            key=lambda item: (
                item['metrics']['mae'],
                item['metrics']['mape'] if item['metrics'].get('mape') is not None else float('inf'),
                item['metrics']['rmse'],
            ),
        )
        return {
            'candidate': best,
            'comparison_summary': cls._comparison_summary(comparison_candidates, best),
        }

    @classmethod
    def _web_forecast_candidates(cls, series_length, allow_seasonal, dataset_kind='egg'):
        candidates = [
            {'name': 'Seasonal Baseline', 'kind': 'baseline', 'spec': None, 'feature_set': 'none', 'dataset_kind': dataset_kind},
        ]
        if allow_seasonal and series_length >= cls.SEASONAL_PERIOD * 4:
            specs = [
                {'order': (0, 1, 1), 'seasonal_order': (1, 0, 1, cls.SEASONAL_PERIOD)},
                {'order': (1, 0, 0), 'seasonal_order': (0, 1, 1, cls.SEASONAL_PERIOD)},
                {'order': (1, 0, 0), 'seasonal_order': None},
            ]
        else:
            specs = [{'order': (1, 0, 0), 'seasonal_order': None}]

        for spec in specs:
            candidates.append({'name': 'SARIMA', 'kind': 'sarima', 'spec': spec, 'feature_set': 'none', 'dataset_kind': dataset_kind})
            candidates.append({'name': 'SARIMAX', 'kind': 'sarimax', 'spec': spec, 'feature_set': 'safe', 'dataset_kind': dataset_kind})
        return candidates

    @classmethod
    def _select_lowest_aic_candidate(cls, prepared, allow_seasonal):
        series = prepared['series']
        values = series.to_numpy(dtype=float)
        best = None
        for candidate in cls._model_candidates(len(series), allow_seasonal, prepared.get('dataset_kind', 'egg')):
            if candidate['kind'] == 'baseline':
                continue
            try:
                exog = cls._exog_for_candidate(prepared, candidate)
                model = cls._fit_model(values, candidate['spec'], exog=exog)
                if best is None or model.aic < best['model'].aic:
                    best = {**candidate, 'model': model}
            except Exception:
                logger.debug("Time-series model %s failed", candidate, exc_info=True)
        if best is None:
            return None
        best['metrics'] = cls._score_series(prepared, best['spec'], feature_set=best.get('feature_set', 'all'))
        return {'candidate': best, 'comparison_summary': cls._comparison_summary([best], best)}

    @classmethod
    def _model_candidates(cls, series_length, allow_seasonal, dataset_kind='egg'):
        candidates = [
            {'name': 'Seasonal Baseline', 'kind': 'baseline', 'spec': None, 'feature_set': 'none', 'dataset_kind': dataset_kind},
        ]
        feature_profiles = ['safe', 'diagnostic'] if dataset_kind == 'egg' else ['safe']
        for spec in cls._candidate_model_specs(series_length, allow_seasonal):
            candidates.append({'name': 'SARIMA', 'kind': 'sarima', 'spec': spec, 'feature_set': 'none', 'dataset_kind': dataset_kind})
            if 'safe' in feature_profiles:
                candidates.append({'name': 'SARIMAX', 'kind': 'sarimax', 'spec': spec, 'feature_set': 'safe', 'dataset_kind': dataset_kind})
            if 'diagnostic' in feature_profiles:
                candidates.append({'name': 'SARIMAX Diagnostic', 'kind': 'sarimax', 'spec': spec, 'feature_set': 'diagnostic', 'dataset_kind': dataset_kind})
        return candidates

    @classmethod
    def _uses_seasonality(cls, model_kind):
        if model_kind == 'egg':
            return cls.EGG_USE_SEASONALITY
        if model_kind == 'sales':
            return cls.SALES_USE_SEASONALITY
        return False

    @classmethod
    def _exog_for_candidate(cls, prepared, candidate):
        feature_set = candidate.get('feature_set')
        exog = prepared.get('exog')
        if feature_set in (None, '', 'none') or exog is None:
            return None
        if feature_set == 'safe':
            if prepared.get('dataset_kind') == 'sales':
                return cls._slice_exog(exog, cls.SALES_SAFE_FEATURE_FIELDS)
            return cls._slice_exog(exog, cls.EGG_SAFE_FEATURE_FIELDS)
        if feature_set == 'diagnostic':
            return cls._slice_exog(exog, cls.EGG_DIAGNOSTIC_FEATURE_FIELDS)
        return exog

    @staticmethod
    def _slice_exog(exog, columns):
        selected_columns = [column for column in columns if column in exog.columns]
        if not selected_columns:
            return None
        sliced = exog[selected_columns].copy()
        sliced.attrs.update(exog.attrs)
        if sliced.attrs.get('latest_source_values') is not None:
            latest_values = sliced.attrs['latest_source_values']
            sliced.attrs['latest_source_values'] = latest_values[[column for column in latest_values.index if column in selected_columns]]
        return sliced

    @classmethod
    def _rolling_backtest(cls, prepared, candidate):
        series = prepared['series']
        values = series.to_numpy(dtype=float)
        if candidate['kind'] == 'baseline':
            return cls._seasonal_naive_metrics(series, actual_series=prepared.get('raw_series'))
        if len(values) < cls.MIN_POINTS + 7:
            return cls._score_series(prepared, candidate['spec'], feature_set=candidate.get('feature_set', 'none'))
        raw_values = prepared.get('raw_series', series).to_numpy(dtype=float)

        horizon = min(14, max(3, len(values) // 12))
        min_train_size = max(cls.MIN_POINTS, min(90, len(values) // 2))
        max_windows = 2
        available_windows = max((len(values) - min_train_size) // horizon, 1)
        window_count = min(max_windows, available_windows)
        starts = [
            len(values) - (window_count - index) * horizon
            for index in range(window_count)
        ]
        actual_values = []
        predicted_values = []
        for test_start in starts:
            train_values = values[:test_start]
            test_values = values[test_start:test_start + horizon]
            if len(test_values) < 2 or len(train_values) < cls.MIN_POINTS:
                continue
            try:
                prediction = cls._candidate_backtest_prediction(prepared, candidate, train_values, test_start, len(test_values))
                prediction = cls._apply_backtest_rate_limits(prepared, prediction, test_start, len(test_values))
            except Exception:
                logger.debug("Rolling backtest failed for %s", candidate, exc_info=True)
                continue
            actual_values.extend(raw_values[test_start:test_start + len(test_values)].tolist())
            predicted_values.extend(prediction.tolist())

        if not actual_values:
            return {
                'rmse': None,
                'mae': None,
                'mape': None,
                'baseline_rmse': None,
                'r_squared': None,
            }

        metrics = cls._prediction_metrics(np.asarray(actual_values), np.asarray(predicted_values))
        baseline_predictions = cls._rolling_baseline_predictions(values, starts, horizon)
        baseline_metrics = cls._prediction_metrics(
            np.asarray(actual_values),
            np.asarray(baseline_predictions[:len(actual_values)]),
        ) if baseline_predictions else {'rmse': None}
        return {
            'rmse': metrics['rmse'],
            'mae': metrics['mae'],
            'mape': metrics['mape'],
            'baseline_rmse': baseline_metrics['rmse'],
            'r_squared': metrics['r2'],
            'windows': len(starts),
        }

    @classmethod
    def _candidate_backtest_prediction(cls, prepared, candidate, train_values, test_start, test_size):
        if candidate['kind'] == 'baseline':
            return cls._seasonal_naive_from_train(train_values, test_size)

        exog = cls._exog_for_candidate(prepared, candidate)
        train_exog = exog.iloc[:test_start] if exog is not None else None
        test_exog = exog.iloc[test_start:test_start + test_size] if exog is not None else None
        model = cls._fit_model(train_values, candidate['spec'], exog=train_exog)
        return np.asarray(model.forecast(steps=test_size, exog=test_exog), dtype=float)

    @classmethod
    def _rolling_baseline_predictions(cls, values, starts, horizon):
        predictions = []
        for test_start in starts:
            train_values = values[:test_start]
            test_size = min(horizon, len(values) - test_start)
            if len(train_values) >= cls.MIN_POINTS and test_size > 0:
                predictions.extend(cls._seasonal_naive_from_train(train_values, test_size).tolist())
        return predictions

    @classmethod
    def _comparison_summary(cls, candidates, best):
        summary = []
        for candidate in sorted(
            candidates,
            key=lambda item: (
                item.get('metrics', {}).get('mae') if item.get('metrics', {}).get('mae') is not None else float('inf'),
                item.get('metrics', {}).get('mape') if item.get('metrics', {}).get('mape') is not None else float('inf'),
            ),
        )[:6]:
            metrics = candidate.get('metrics') or {}
            summary.append({
                'name': candidate.get('name'),
                'feature_set': candidate.get('feature_set', 'none'),
                'order': cls._format_candidate_label(candidate),
                'mae': cls._round_metric(metrics.get('mae')),
                'mape': cls._round_metric(metrics.get('mape')),
                'rmse': cls._round_metric(metrics.get('rmse')),
                'winner': cls._same_candidate(candidate, best),
            })
        return {
            'selected': cls._format_candidate_label(best),
            'selected_name': best.get('name'),
            'selected_feature_set': best.get('feature_set', 'none'),
            'selection_metric': 'rolling MAE then MAPE',
            'items': summary,
            'cards': cls._comparison_cards(candidates, best),
            'assumptions': cls._future_exog_assumptions(best),
        }

    @classmethod
    def _comparison_cards(cls, candidates, best):
        grouped = {}
        for candidate in candidates:
            key = cls._comparison_group(candidate)
            metrics = candidate.get('metrics') or {}
            if metrics.get('mae') is None:
                continue
            current = grouped.get(key)
            if current is None or (
                metrics.get('mae'),
                metrics.get('mape') if metrics.get('mape') is not None else float('inf'),
            ) < (
                current.get('metrics', {}).get('mae'),
                current.get('metrics', {}).get('mape') if current.get('metrics', {}).get('mape') is not None else float('inf'),
            ):
                grouped[key] = candidate

        labels = [
            ('baseline', 'Weekly Baseline', 'Simple repeat of recent weekly pattern'),
            ('sarima', 'SARIMA', 'Uses historical values and selected time-series order'),
            ('safe_sarimax', 'SARIMAX', 'Uses lagged operational predictors plus trend direction'),
            ('diagnostic_sarimax', 'Diagnostic SARIMAX', 'Tests lagged derived performance indicators separately'),
        ]
        cards = []
        for key, label, description in labels:
            candidate = grouped.get(key)
            metrics = candidate.get('metrics') if candidate else {}
            cards.append({
                'key': key,
                'label': label,
                'description': description,
                'order': cls._format_candidate_label(candidate) if candidate else 'Not enough data',
                'mae': cls._round_metric(metrics.get('mae')) if metrics else None,
                'mape': cls._round_metric(metrics.get('mape')) if metrics else None,
                'rmse': cls._round_metric(metrics.get('rmse')) if metrics else None,
                'winner': cls._same_candidate(candidate, best) if candidate else False,
            })
        return cards

    @staticmethod
    def _comparison_group(candidate):
        if candidate.get('kind') == 'baseline':
            return 'baseline'
        if candidate.get('kind') == 'sarima':
            return 'sarima'
        if candidate.get('feature_set') == 'diagnostic':
            return 'diagnostic_sarimax'
        if candidate.get('feature_set') == 'safe':
            return 'safe_sarimax'
        return candidate.get('kind', 'other')

    @classmethod
    def _format_candidate_label(cls, candidate):
        if candidate.get('kind') == 'baseline':
            return 'Seasonal naive baseline'
        return cls._format_model_spec(candidate['spec'], uses_exog=candidate.get('feature_set') not in ('none', None, ''))

    @staticmethod
    def _round_metric(value):
        return round(float(value), 2) if value is not None else None

    @staticmethod
    def _same_candidate(left, right):
        return (
            left.get('name') == right.get('name')
            and left.get('feature_set') == right.get('feature_set')
            and left.get('spec') == right.get('spec')
        )

    @classmethod
    def _future_exog_assumptions(cls, candidate):
        if candidate.get('dataset_kind') == 'sales' and candidate.get('feature_set') == 'safe':
            return [
                'Sales quantity, average unit price, and transaction count use the latest known historical behavior.',
                'Weekday, month cycle, and trend features continue naturally into future dates.',
                'Same-day sales quantity is not used directly, reducing target leakage.',
            ]
        if candidate.get('dataset_kind') == 'sales':
            return [
                'Forecast uses historical sales revenue and weekly seasonality only.',
                'No future sales-volume assumptions are required.',
            ]
        if candidate.get('feature_set') == 'safe':
            return [
                'Age and trend features continue naturally into future dates.',
                'Live hen count, dead/cull count, and feed bags use the latest recorded conditions.',
                'Derived production rates are not used for model selection to reduce target leakage.',
            ]
        if candidate.get('feature_set') == 'diagnostic':
            return [
                'Age and trend features continue naturally into future dates.',
                'Latest flock condition and lagged derived indicators are carried forward.',
                'Hen-day, hen-housed, and FCR are diagnostic features and may be close to the target.',
            ]
        if candidate.get('dataset_kind') == 'egg':
            return [
                'Forecast uses historical egg totals without a forced weekly seasonal cycle.',
                'No future flock-condition assumptions are required.',
            ]
        return [
            'Forecast uses historical egg totals and weekly seasonality only.',
            'No future flock-condition assumptions are required.',
        ]

    @classmethod
    def _fallback_forecast_if_needed(
        cls,
        series,
        forecast_values,
        periods,
        model_metrics,
        forecast_start_date=None,
        exog=None,
        allow_seasonal=False,
        rate_limits=None,
    ):
        if not len(forecast_values):
            return None

        model_rmse = model_metrics.get('rmse') if model_metrics else None
        recent = series.tail(min(60, len(series))).to_numpy(dtype=float)
        recent_mean = float(np.mean(recent)) if len(recent) else 0
        unreasonable = cls._forecast_is_unreasonable(recent, forecast_values, exog)
        if unreasonable:
            return cls._bounded_trend_guard(
                series,
                periods,
                model_metrics,
                forecast_start_date,
                allow_seasonal=allow_seasonal,
                exog=exog,
                rate_limits=rate_limits,
            )

        trend_fallback = cls._trend_forecast_if_model_is_flat(
            series,
            forecast_values,
            periods,
            model_metrics,
            forecast_start_date,
            exog=exog,
            rate_limits=rate_limits,
        )
        if trend_fallback is not None:
            return trend_fallback

        zero_share = float(np.mean(forecast_values <= 0))
        final_value = float(forecast_values[-1])
        collapsed = zero_share > 0.10 or (recent_mean and final_value < recent_mean * 0.35)
        if not collapsed:
            return None

        if periods < 90:
            return cls._bounded_trend_guard(
                series,
                periods,
                model_metrics,
                forecast_start_date,
                allow_seasonal=allow_seasonal,
                exog=exog,
                rate_limits=rate_limits,
            )

        baseline_values = cls._seasonal_naive_forecast(series, periods)
        baseline_rmse, baseline_r2 = cls._score_seasonal_naive(series)
        if model_rmse is not None and baseline_rmse is not None and baseline_rmse > model_rmse and zero_share <= 0.25:
            return None

        baseline_values, lower_values, upper_values = cls._apply_egg_rate_limits(
            baseline_values,
            cls._interval_from_rmse(baseline_values, baseline_rmse),
            cls._interval_from_rmse(baseline_values, baseline_rmse, upper=True),
            rate_limits,
        )

        return {
            'success': True,
            'forecasted_values': baseline_values,
            'lower_values': lower_values,
            'upper_values': upper_values,
            'order': 'seasonal naive baseline (7-day)',
            'aic_score': None,
            'rmse': baseline_rmse,
            'mae': model_metrics.get('mae') if model_metrics else None,
            'mape': model_metrics.get('mape') if model_metrics else None,
            'baseline_rmse': model_metrics.get('baseline_rmse') if model_metrics else baseline_rmse,
            'r_squared': baseline_r2,
            'start_date': forecast_start_date or series.index.max().date() + timedelta(days=1),
        }

    @classmethod
    def _forecast_is_unreasonable(cls, recent, forecast_values, exog=None):
        if not len(recent) or not len(forecast_values):
            return False

        recent_max = float(np.max(recent))
        recent_mean = float(np.mean(recent))
        forecast_max = float(np.max(forecast_values))
        forecast_min = float(np.min(forecast_values))
        if recent_mean > 0 and forecast_min < 0:
            return True
        if recent_mean > 0 and forecast_min < recent_mean * 0.25:
            return True

        recent_limit = max(recent_max * 1.25, recent_mean * 1.35)
        if forecast_max > recent_limit:
            return True

        if exog is not None and 'hen_count' in exog.columns:
            live_hens = cls._latest_live_hen_limit(exog)
            if live_hens is not None and live_hens > 0 and forecast_max > live_hens * 1.02:
                return True

        return False

    @classmethod
    def _bounded_trend_guard(cls, series, periods, model_metrics, forecast_start_date=None, allow_seasonal=False, exog=None, rate_limits=None):
        model_rmse = model_metrics.get('rmse') if model_metrics else None
        values = series.to_numpy(dtype=float)
        window_size = min(45, len(values))
        recent = values[-window_size:]
        x_values = np.arange(window_size, dtype=float)
        slope, _intercept = np.polyfit(x_values, recent, 1)
        steps = np.arange(1, periods + 1, dtype=float)
        damping = np.linspace(0.80, 0.35, periods)
        trend_values = recent[-1] + (slope * steps * damping)

        guarded_values = trend_values
        if allow_seasonal and len(values) >= cls.SEASONAL_PERIOD:
            seasonal = values[-cls.SEASONAL_PERIOD:]
            seasonal_offsets = seasonal - np.mean(seasonal)
            guarded_values = trend_values + np.resize(seasonal_offsets, periods)
        recent_floor = max(float(np.min(recent)) * 0.80, 0)
        recent_ceiling = float(np.max(recent)) * 1.10
        guarded_values = np.clip(guarded_values, recent_floor, recent_ceiling)
        live_hens = cls._latest_live_hen_limit(exog)
        guarded_values = cls._cap_values_by_live_hens(guarded_values, live_hens)
        guarded_values = cls._cap_values_by_rate_limits(guarded_values, rate_limits)

        baseline_rmse, baseline_r2 = cls._score_seasonal_naive(series)
        interval_rmse = baseline_rmse if baseline_rmse is not None else model_rmse
        lower_values, upper_values = cls._interval_bounds(
            guarded_values,
            interval_rmse,
            live_hens=live_hens,
            rate_limits=rate_limits,
        )
        return {
            'success': True,
            'forecasted_values': guarded_values,
            'lower_values': lower_values,
            'upper_values': upper_values,
            'order': 'bounded trend guard',
            'aic_score': None,
            'rmse': interval_rmse,
            'mae': model_metrics.get('mae') if model_metrics else None,
            'mape': model_metrics.get('mape') if model_metrics else None,
            'baseline_rmse': model_metrics.get('baseline_rmse') if model_metrics else baseline_rmse,
            'r_squared': baseline_r2,
            'start_date': forecast_start_date or series.index.max().date() + timedelta(days=1),
        }

    @classmethod
    def _trend_forecast_if_model_is_flat(cls, series, forecast_values, periods, model_metrics, forecast_start_date=None, exog=None, rate_limits=None):
        model_rmse = model_metrics.get('rmse') if model_metrics else None
        values = series.to_numpy(dtype=float)
        if len(values) < cls.MIN_POINTS:
            return None

        window_size = min(60 if periods >= 30 else 30, len(values))
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

        strong_recent_trend = (
            abs(recent_change_pct) >= 8
            or (abs(recent_change_pct) >= 5 and abs(slope) >= recent_mean * 0.001)
        )
        model_is_flat = abs(forecast_change_pct) < max(2, abs(recent_change_pct) * 0.10)
        model_opposes_trend = slope and forecast_slope and np.sign(slope) != np.sign(forecast_slope)
        if not strong_recent_trend or not (model_is_flat or model_opposes_trend):
            return None

        # Damping keeps the short data trend visible without unrealistically accelerating far into the future.
        damping = np.linspace(0.85, 0.35, periods)
        steps = np.arange(1, periods + 1, dtype=float)
        trend_values = recent[-1] + (slope * steps * damping)
        trend_values = np.maximum(trend_values, 0)
        live_hens = cls._latest_live_hen_limit(exog)
        trend_values = cls._cap_values_by_live_hens(trend_values, live_hens)
        trend_values = cls._cap_values_by_rate_limits(trend_values, rate_limits)
        trend_rmse, trend_r2 = cls._score_trend_baseline(series)
        lower_values, upper_values = cls._interval_bounds(
            trend_values,
            trend_rmse if trend_rmse is not None else model_rmse,
            live_hens=live_hens,
            rate_limits=rate_limits,
        )

        return {
            'success': True,
            'forecasted_values': trend_values,
            'lower_values': lower_values,
            'upper_values': upper_values,
            'order': 'trend-adjusted ARIMA fallback',
            'aic_score': None,
            'rmse': trend_rmse if trend_rmse is not None else model_rmse,
            'mae': model_metrics.get('mae') if model_metrics else None,
            'mape': model_metrics.get('mape') if model_metrics else None,
            'baseline_rmse': model_metrics.get('baseline_rmse') if model_metrics else None,
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
    def _interval_bounds(cls, values, rmse, live_hens=None, rate_limits=None):
        lower_values = cls._interval_from_rmse(values, rmse)
        upper_values = cls._interval_from_rmse(values, rmse, upper=True)
        if live_hens is not None:
            lower_values = cls._cap_values_by_live_hens(lower_values, live_hens)
            upper_values = cls._cap_values_by_live_hens(upper_values, live_hens)
            lower_values = np.minimum(lower_values, upper_values)
        if rate_limits is not None:
            lower_values = cls._cap_values_by_rate_limits(lower_values, rate_limits)
            upper_values = cls._cap_values_by_rate_limits(upper_values, rate_limits)
            lower_values = np.minimum(lower_values, upper_values)
        return lower_values, upper_values

    @staticmethod
    def _latest_live_hen_limit(exog):
        if exog is None or 'hen_count' not in exog.columns:
            return None

        latest_source_values = exog.attrs.get('latest_source_values')
        if latest_source_values is not None and 'hen_count' in latest_source_values.index:
            value = latest_source_values['hen_count']
        else:
            value = exog['hen_count'].iloc[-1]

        try:
            if pd.isna(value):
                return None
        except TypeError:
            return None
        return max(float(value), 0)

    @staticmethod
    def _cap_values_by_live_hens(values, live_hens):
        values = np.maximum(np.asarray(values, dtype=float), 0)
        if live_hens is None:
            return values
        return np.minimum(values, float(live_hens))

    @classmethod
    def _apply_egg_rate_limits(cls, forecast_values, lower_values, upper_values, rate_limits):
        if rate_limits is None:
            return forecast_values, lower_values, upper_values

        forecast_values = cls._cap_values_by_rate_limits(forecast_values, rate_limits)
        lower_values = cls._cap_values_by_rate_limits(lower_values, rate_limits)
        upper_values = cls._cap_values_by_rate_limits(upper_values, rate_limits)
        lower_values = np.minimum(lower_values, forecast_values)
        upper_values = np.maximum(forecast_values, upper_values)
        upper_values = cls._cap_values_by_rate_limits(upper_values, rate_limits)
        return forecast_values, lower_values, upper_values

    @staticmethod
    def _cap_values_by_rate_limits(values, rate_limits):
        values = np.maximum(np.asarray(values, dtype=float), 0)
        if rate_limits is None:
            return values
        limits = np.asarray(rate_limits, dtype=float)
        if len(limits) != len(values):
            limits = np.resize(limits, len(values))
        return np.minimum(values, limits)

    @classmethod
    def _egg_rate_capacity_limits(cls, prepared, periods):
        if prepared.get('dataset_kind') != 'egg':
            return None

        frame = prepared.get('raw_feature_frame')
        return cls._egg_rate_capacity_limits_from_frame(frame, periods)

    @classmethod
    def _egg_rate_capacity_limits_from_frame(cls, frame, periods, future_frame=None):
        if frame is None or frame.empty or 'hen_count' not in frame.columns:
            return None

        live_hens = cls._future_live_hen_values(frame, periods, future_frame=future_frame)
        if live_hens is None or not np.any(live_hens > 0):
            return None

        hen_day_rates = cls._expected_rate_path_from_history(frame, 'pct_hen_day', periods)
        hen_housed_rates = cls._expected_rate_path_from_history(frame, 'pct_hen_housed', periods)
        capacities = [live_hens * (hen_day_rates / 100)]

        initial_hens = cls._estimate_initial_hens(frame)
        if initial_hens is not None and hen_housed_rates is not None:
            capacities.append(initial_hens * (hen_housed_rates / 100))

        capacities.append(live_hens * (cls.EGG_RATE_MAX_PERCENT / 100))
        capacity = np.minimum.reduce([values for values in capacities if values is not None])
        return np.maximum(capacity, 0)

    @classmethod
    def _apply_backtest_rate_limits(cls, prepared, prediction, test_start, test_size):
        if prepared.get('dataset_kind') != 'egg':
            return prediction

        frame = prepared.get('raw_feature_frame')
        if frame is None or frame.empty:
            return prediction

        training_frame = frame.iloc[:test_start]
        future_frame = frame.iloc[test_start:test_start + test_size]
        rate_limits = cls._egg_rate_capacity_limits_from_frame(
            training_frame,
            test_size,
            future_frame=future_frame,
        )
        return cls._cap_values_by_rate_limits(prediction, rate_limits)

    @classmethod
    def _future_live_hen_values(cls, frame, periods, future_frame=None):
        if future_frame is not None and 'hen_count' in future_frame.columns and not future_frame.empty:
            values = pd.to_numeric(future_frame['hen_count'], errors='coerce').ffill().bfill().to_numpy(dtype=float)
            if len(values):
                if len(values) < periods:
                    values = np.pad(values, (0, periods - len(values)), mode='edge')
                return np.maximum(values[:periods], 0)

        latest_live_hens = cls._series_last_number(frame['hen_count'])
        if latest_live_hens is None or latest_live_hens <= 0:
            return None
        return np.full(periods, latest_live_hens, dtype=float)

    @classmethod
    def _expected_rate_path_from_history(cls, frame, rate_column, periods):
        base_rate = cls._expected_rate_from_history(frame, rate_column)
        if base_rate is None:
            return np.full(periods, cls.EGG_RATE_MAX_PERCENT, dtype=float)

        trend_source = cls._valid_rate_series(frame, rate_column).tail(cls.EGG_RATE_LOOKBACK_DAYS)
        slope = 0.0
        if len(trend_source) >= cls.OUTLIER_MIN_HISTORY_DAYS:
            x_values = np.arange(len(trend_source), dtype=float)
            slope, _intercept = np.polyfit(x_values, trend_source.to_numpy(dtype=float), 1)
            slope = float(np.clip(slope, -cls.EGG_RATE_MAX_DAILY_CHANGE, cls.EGG_RATE_MAX_DAILY_CHANGE))

        steps = np.arange(1, periods + 1, dtype=float)
        damping = np.linspace(0.85, 0.35, periods)
        rate_path = base_rate + (slope * steps * damping)
        latest_rate = cls._series_last_number(frame[rate_column])
        if latest_rate is not None and 0 < latest_rate < base_rate * cls.EGG_RATE_SHOCK_THRESHOLD:
            latest_rate = min(max(float(latest_rate), 0), 100)
            shock_weight = np.linspace(0.25, 0.55, periods)
            shock_path = base_rate - ((base_rate - latest_rate) * shock_weight)
            rate_path = np.minimum(rate_path, shock_path)
        return np.clip(rate_path, cls.EGG_RATE_MIN_PERCENT, cls.EGG_RATE_MAX_PERCENT)

    @classmethod
    def _expected_rate_from_history(cls, frame, rate_column):
        if rate_column not in frame.columns:
            return None

        working = frame.copy()
        working[rate_column] = pd.to_numeric(working[rate_column], errors='coerce')
        working['hen_count'] = pd.to_numeric(working.get('hen_count'), errors='coerce')
        working = working[
            working[rate_column].between(cls.EGG_RATE_MIN_PERCENT, 100)
            & working['hen_count'].gt(0)
        ]
        if working.empty:
            return None

        recent = working.tail(cls.EGG_RATE_LOOKBACK_DAYS)
        recent_rate = cls._robust_rate_median(recent[rate_column])
        latest_live_hens = cls._series_last_number(frame['hen_count'])
        if latest_live_hens is None:
            return recent_rate

        median_hens = float(working['hen_count'].median()) if not working['hen_count'].dropna().empty else latest_live_hens
        scale_hens = max(latest_live_hens, median_hens, 1)
        distance = (working['hen_count'] - latest_live_hens).abs() / scale_hens
        if recent_rate is not None:
            distance = distance + ((working[rate_column] - recent_rate).abs() / max(recent_rate, 1))
        if 'age_days' in working.columns:
            working['age_days'] = pd.to_numeric(working['age_days'], errors='coerce')
            latest_age = cls._series_last_number(frame['age_days'])
            if latest_age is not None and working['age_days'].notna().any():
                distance = distance + ((working['age_days'] - latest_age).abs() / 365).fillna(0)

        similar = working.assign(_distance=distance).nsmallest(cls.EGG_RATE_SIMILAR_ROWS, '_distance')
        similar_rate = cls._robust_rate_median(similar[rate_column])
        if recent_rate is None:
            return similar_rate
        if similar_rate is None:
            return recent_rate
        return (recent_rate * 0.65) + (similar_rate * 0.35)

    @classmethod
    def _robust_rate_median(cls, series):
        rates = cls._valid_rate_series(pd.DataFrame({'rate': series}), 'rate')
        if rates.empty:
            return None
        lower = rates.quantile(0.10)
        upper = rates.quantile(0.90)
        trimmed = rates[rates.between(lower, upper)]
        return float((trimmed if not trimmed.empty else rates).median())

    @classmethod
    def _valid_rate_series(cls, frame, rate_column):
        if rate_column not in frame:
            return pd.Series(dtype=float)
        rates = pd.to_numeric(frame[rate_column], errors='coerce').dropna()
        return rates[rates.between(cls.EGG_RATE_MIN_PERCENT, 100)]

    @classmethod
    def _bounded_rate(cls, rate):
        if rate is None or not np.isfinite(rate):
            return cls.EGG_RATE_MAX_PERCENT
        return min(max(float(rate), cls.EGG_RATE_MIN_PERCENT), cls.EGG_RATE_MAX_PERCENT)

    @staticmethod
    def _estimate_initial_hens(frame):
        if 'pct_hen_housed' not in frame.columns or 'value' not in frame.columns:
            return None
        values = pd.to_numeric(frame['value'], errors='coerce')
        rates = pd.to_numeric(frame['pct_hen_housed'], errors='coerce')
        valid = values.gt(0) & rates.gt(0)
        if not valid.any():
            return None
        estimates = values[valid] / (rates[valid] / 100)
        estimates = estimates.replace([np.inf, -np.inf], np.nan).dropna()
        if estimates.empty:
            return None
        return float(estimates.median())

    @staticmethod
    def _series_last_number(series):
        values = pd.to_numeric(series, errors='coerce').dropna()
        if values.empty:
            return None
        return float(values.iloc[-1])

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
    def _seasonal_naive_metrics(cls, series, actual_series=None):
        values = series.to_numpy(dtype=float)
        actual_values = (actual_series if actual_series is not None else series).to_numpy(dtype=float)
        test_size = max(2, min(int(len(values) * 0.2), len(values) - 2))
        if len(values) <= cls.SEASONAL_PERIOD or test_size <= 0:
            return {
                'rmse': None,
                'mae': None,
                'mape': None,
                'baseline_rmse': None,
                'r_squared': None,
            }

        train = values[:-test_size]
        test = actual_values[-test_size:]
        predictions = cls._seasonal_naive_from_train(train, test_size)
        metrics = cls._prediction_metrics(test, predictions)
        return {
            'rmse': metrics['rmse'],
            'mae': metrics['mae'],
            'mape': metrics['mape'],
            'baseline_rmse': metrics['rmse'],
            'r_squared': metrics['r2'],
        }

    @classmethod
    def _score_series(cls, prepared, spec, feature_set='all'):
        series = prepared['series']
        exog = cls._exog_for_candidate(prepared, {'spec': spec, 'feature_set': feature_set})
        values = series.to_numpy(dtype=float)
        actual_values = prepared.get('raw_series', series).to_numpy(dtype=float)
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
            actual = actual_values[-test_size:]
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
    def _evaluate_series_map(cls, series_map, allow_seasonal=False, use_exog=False, dataset_kind='egg'):
        results = []
        for category, rows in series_map.items():
            prepared = cls._prepare_daily_dataset(rows, use_exog=use_exog, dataset_kind=dataset_kind)
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
        values = series.to_numpy(dtype=float)
        actual_values = prepared.get('raw_series', series).to_numpy(dtype=float)
        test_size = max(2, min(int(len(values) * 0.2), len(values) - 2))
        train = values[:-test_size]
        test = actual_values[-test_size:]

        best = None
        for candidate in cls._model_candidates(len(train), allow_seasonal, prepared.get('dataset_kind', 'egg')):
            try:
                metrics = cls._rolling_backtest(prepared, candidate)
                if metrics.get('mae') is None:
                    continue
                if best is None or (metrics['mae'], metrics.get('mape') or float('inf')) < (
                    best['metrics']['mae'],
                    best['metrics'].get('mape') or float('inf'),
                ):
                    best = {**candidate, 'metrics': metrics}
            except Exception:
                logger.debug("Evaluation model %s failed", candidate, exc_info=True)

        if best is None:
            return {
                'success': False,
                'error': 'ARIMA could not fit this series',
            }

        arima_metrics = best['metrics']
        baseline_predictions = cls._seasonal_naive_from_train(train, test_size)
        baseline_metrics = cls._prediction_metrics(test, baseline_predictions)
        arima_beats_baseline = arima_metrics['rmse'] < baseline_metrics['rmse']

        return {
            'success': True,
            'rows': len(values),
            'test_rows': test_size,
            'model_order': cls._format_candidate_label(best),
            'uses_features': best.get('feature_set') not in ('none', None, ''),
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
    def _prepare_daily_dataset(cls, rows, use_exog=False, dataset_kind='egg'):
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

        database_fields = cls.EGG_DATABASE_FEATURE_FIELDS if dataset_kind == 'egg' else cls.SALES_DATABASE_FEATURE_FIELDS
        time_fields = cls.EGG_TIME_FEATURE_FIELDS if dataset_kind == 'egg' else cls.SALES_TIME_FEATURE_FIELDS
        feature_fields = cls.EGG_FEATURE_FIELDS if dataset_kind == 'egg' else cls.SALES_FEATURE_FIELDS
        aggregations = {'value': lambda values: values.sum(min_count=1)}
        if use_exog:
            for field_name in database_fields:
                if field_name in df.columns:
                    df[field_name] = pd.to_numeric(df[field_name], errors='coerce')
                    aggregations[field_name] = 'mean'

        df = df.groupby('date', as_index=True).agg(aggregations).sort_index()
        df = df.reindex(pd.date_range(df.index.min(), df.index.max(), freq='D'))
        df = df.interpolate(method='time').ffill().bfill()
        raw_series = df['value'].copy()
        raw_feature_frame = df.copy()
        if dataset_kind == 'egg':
            live_hens = df['hen_count'] if 'hen_count' in df.columns else None
            df['value'] = cls._smooth_egg_training_outliers(df['value'], live_hens=live_hens)
        if use_exog:
            cls._add_time_features(df)

        if len(df) < cls.MIN_POINTS or df['value'].isna().all():
            return None

        exog = None
        feature_columns = [field for field in feature_fields if field in df.columns]
        if use_exog and feature_columns:
            source_columns = [field for field in database_fields if field in df.columns]
            time_columns = [field for field in time_fields if field in df.columns]
            lagged_sources = df[source_columns].shift(1).ffill().bfill()
            exog = pd.concat([lagged_sources, df[time_columns]], axis=1)[feature_columns]
            exog.attrs['last_date'] = df.index.max()
            exog.attrs['latest_source_values'] = df[source_columns].iloc[-1].copy() if source_columns else None
            exog.attrs['dataset_kind'] = dataset_kind

        return {
            'series': df['value'],
            'raw_series': raw_series,
            'raw_feature_frame': raw_feature_frame,
            'exog': exog,
            'dataset_kind': dataset_kind,
        }

    @classmethod
    def _smooth_egg_training_outliers(cls, series, live_hens=None):
        values = pd.to_numeric(series, errors='coerce').astype(float).copy()
        if len(values) < cls.OUTLIER_MIN_HISTORY_DAYS + 1:
            return values

        smoothed = values.copy()
        consecutive_outliers = 0
        for index in range(len(values)):
            if index < cls.OUTLIER_MIN_HISTORY_DAYS or pd.isna(values.iloc[index]):
                continue

            start = max(0, index - cls.OUTLIER_WINDOW_DAYS)
            history = smoothed.iloc[start:index].dropna()
            if len(history) < cls.OUTLIER_MIN_HISTORY_DAYS:
                continue

            median = float(history.median())
            if median <= 0:
                continue

            mad = float(np.median(np.abs(history.to_numpy(dtype=float) - median)))
            robust_width = max(median * cls.OUTLIER_RELATIVE_BAND, mad * 4.5, 1)
            lower_bound = max(0, median - robust_width)
            upper_bound = median + robust_width
            current = float(values.iloc[index])
            is_outlier = current < lower_bound or current > upper_bound

            if is_outlier:
                consecutive_outliers += 1
                if consecutive_outliers < 3:
                    smoothed.iloc[index] = min(max(current, lower_bound), upper_bound)
                continue

            consecutive_outliers = 0

        if live_hens is not None:
            hen_limits = pd.to_numeric(live_hens, errors='coerce').astype(float).reindex(smoothed.index)
            if not hen_limits.isna().all():
                hen_limits = hen_limits.ffill().bfill()
                smoothed = pd.Series(
                    np.minimum(smoothed.to_numpy(dtype=float), hen_limits.to_numpy(dtype=float)),
                    index=smoothed.index,
                )

        return smoothed

    @staticmethod
    def _add_time_features(df):
        trend = np.arange(len(df), dtype=float)
        weekdays = df.index.dayofweek.to_numpy(dtype=float)
        months = df.index.month.to_numpy(dtype=float)
        df['trend_day'] = trend
        df['weekday_sin'] = np.sin(2 * np.pi * weekdays / 7)
        df['weekday_cos'] = np.cos(2 * np.pi * weekdays / 7)
        df['month_sin'] = np.sin(2 * np.pi * months / 12)
        df['month_cos'] = np.cos(2 * np.pi * months / 12)

    @classmethod
    def _future_exog(cls, exog, periods):
        if exog is None:
            return None
        last_values = exog.iloc[-1].copy()
        latest_source_values = exog.attrs.get('latest_source_values')
        last_date = exog.attrs.get('last_date')
        future_rows = []
        for step in range(1, periods + 1):
            row = last_values.copy()
            if latest_source_values is not None:
                for field_name, value in latest_source_values.items():
                    if field_name in row:
                        row[field_name] = value
            if 'trend_day' in row:
                row['trend_day'] = float(last_values['trend_day']) + step
            if 'age_days' in row:
                row['age_days'] = float(last_values['age_days']) + step
            if 'age_weeks' in row and 'age_days' in row:
                row['age_weeks'] = int(row['age_days'] // 7)
            if last_date is not None:
                forecast_date = last_date + pd.Timedelta(days=step)
                weekday = float(forecast_date.dayofweek)
                month = float(forecast_date.month)
                if 'weekday_sin' in row:
                    row['weekday_sin'] = np.sin(2 * np.pi * weekday / cls.SEASONAL_PERIOD)
                if 'weekday_cos' in row:
                    row['weekday_cos'] = np.cos(2 * np.pi * weekday / cls.SEASONAL_PERIOD)
                if 'month_sin' in row:
                    row['month_sin'] = np.sin(2 * np.pi * month / 12)
                if 'month_cos' in row:
                    row['month_cos'] = np.cos(2 * np.pi * month / 12)
            future_rows.append(row)
        return pd.DataFrame(future_rows, columns=exog.columns)

    @classmethod
    def _egg_series_map(cls, flock):
        return {'overall': cls._production_total_series(flock)}

    @staticmethod
    def _production_total_series(flock):
        return (
            ProductionLog.objects.filter(flock=flock)
            .values(
                'age_weeks',
                'age_days',
                'hen_count',
                'dead_count',
                'culled_count',
                'feed_bags',
                'pct_hen_day',
                'pct_hen_housed',
                'fcr',
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

    @staticmethod
    def _sales_amount_series():
        return (
            SalesItem.objects.values(date=models.F('transaction__sale_date'))
            .annotate(
                value=models.Sum('amount'),
                quantity_pieces=models.Sum('quantity_pieces'),
                avg_unit_price=models.Avg('unit_price'),
                transaction_count=models.Count('transaction', distinct=True),
            )
            .order_by('date')
        )

    @staticmethod
    def _latest_sales_date():
        return (
            SalesItem.objects
            .order_by('-transaction__sale_date')
            .values_list('transaction__sale_date', flat=True)
            .first()
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
                .annotate(
                    value=models.Sum('amount'),
                    quantity_pieces=models.Sum('quantity_pieces'),
                    avg_unit_price=models.Avg('unit_price'),
                    transaction_count=models.Count('transaction', distinct=True),
                )
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
