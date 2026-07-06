"""
Forecasting Service Module
Handles ARIMA, MLR, and Hybrid forecasting models for Henalytics system
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_percentage_error, r2_score
from statsmodels.tsa.arima.model import ARIMA
from scipy import stats

from .models import TimeSeriesData, Forecast, SystemLog
from django.contrib.auth.models import User
from django.utils import timezone

logger = logging.getLogger(__name__)


class ForecastingService:
    """Service for generating forecasts using ARIMA, MLR, and Hybrid models"""
    
    def __init__(self, flock, data_type, forecast_type='price'):
        """
        Initialize forecasting service
        
        Args:
            flock: Flock instance
            data_type: Type of data (egg_production, sales_volume, sales_price, hen_performance)
            forecast_type: Type of forecast (price, quantity, performance)
        """
        self.flock = flock
        self.data_type = data_type
        self.forecast_type = forecast_type
        self.model_data = None
        self.dates = None
        self.values = None
    
    def prepare_data(self, lookback_days=90):
        """Prepare time series data for forecasting"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=lookback_days)
        
        # Fetch historical data
        data = TimeSeriesData.objects.filter(
            flock=self.flock,
            data_type=self.data_type,
            record_date__range=[start_date, end_date]
        ).order_by('record_date').values('record_date', 'value')
        
        if not data.exists():
            logger.warning(f"No data found for flock {self.flock.id}, data_type {self.data_type}")
            return False
        
        df = pd.DataFrame(data)
        df['record_date'] = pd.to_datetime(df['record_date'])
        df = df.sort_values('record_date')
        
        # Fill missing dates with interpolation
        date_range = pd.date_range(start=df['record_date'].min(), end=df['record_date'].max(), freq='D')
        df = df.set_index('record_date').reindex(date_range)
        df['value'] = df['value'].interpolate(method='linear')
        
        self.dates = df.index
        self.values = df['value'].values
        self.model_data = df
        
        return len(self.values) > 10  # Need at least 10 data points
    
    def forecast_arima(self, periods=7, order=(1, 1, 1)):
        """
        ARIMA Forecasting Model
        
        Args:
            periods: Number of periods to forecast
            order: ARIMA(p, d, q) parameters
        
        Returns:
            dict with forecasted values and confidence intervals
        """
        try:
            if self.values is None:
                self.prepare_data()
            
            # Fit ARIMA model
            model = ARIMA(self.values, order=order)
            fitted_model = model.fit()
            
            # Generate forecast
            forecast_result = fitted_model.get_forecast(steps=periods)
            forecast_values = forecast_result.predicted_mean
            conf_int = forecast_result.conf_int(alpha=0.05)  # 95% confidence
            
            # Calculate performance metrics on last 30% of data (test set)
            test_size = max(int(len(self.values) * 0.3), 7)
            train_values = self.values[:-test_size]
            test_values = self.values[-test_size:]
            
            train_model = ARIMA(train_values, order=order).fit()
            predictions = train_model.get_forecast(steps=test_size).predicted_mean.values
            
            mape = mean_absolute_percentage_error(test_values, predictions)
            r_squared = r2_score(test_values, predictions)
            
            return {
                'model_type': 'arima',
                'forecasted_values': forecast_values.values,
                'lower_bounds': conf_int[0].values,
                'upper_bounds': conf_int[1].values,
                'mape': float(mape),
                'r_squared': float(r_squared),
                'parameters': {'order': order},
                'success': True
            }
        
        except Exception as e:
            logger.error(f"ARIMA forecast failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def forecast_mlr(self, periods=7):
        """
        Multiple Linear Regression Forecasting Model
        
        Args:
            periods: Number of periods to forecast
        
        Returns:
            dict with forecasted values and confidence intervals
        """
        try:
            if self.values is None:
                self.prepare_data()
            
            # Create features (time index and lagged values)
            n = len(self.values)
            X = np.arange(n).reshape(-1, 1)
            y = self.values
            
            # Fit MLR model
            model = LinearRegression()
            model.fit(X, y)
            
            # Generate forecast
            future_X = np.arange(n, n + periods).reshape(-1, 1)
            forecast_values = model.predict(future_X)
            
            # Calculate performance metrics on test set
            test_size = max(int(n * 0.3), 7)
            train_X = X[:-test_size]
            train_y = y[:-test_size]
            test_X = X[-test_size:]
            test_y = y[-test_size:]
            
            train_model = LinearRegression()
            train_model.fit(train_X, train_y)
            predictions = train_model.predict(test_X)
            
            mape = mean_absolute_percentage_error(test_y, predictions)
            r_squared = r2_score(test_y, predictions)
            
            # Calculate confidence intervals using residual standard error
            residuals = y - model.predict(X)
            residual_std = np.std(residuals)
            
            # 95% confidence interval (approximate)
            confidence_factor = 1.96  # 95% CI for normal distribution
            ci_width = confidence_factor * residual_std
            
            upper_bounds = forecast_values + ci_width
            lower_bounds = forecast_values - ci_width
            
            return {
                'model_type': 'mlr',
                'forecasted_values': forecast_values,
                'lower_bounds': lower_bounds,
                'upper_bounds': upper_bounds,
                'mape': float(mape),
                'r_squared': float(r_squared),
                'parameters': {'slope': float(model.coef_[0]), 'intercept': float(model.intercept_)},
                'success': True
            }
        
        except Exception as e:
            logger.error(f"MLR forecast failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def forecast_hybrid(self, periods=7):
        """
        Hybrid Forecasting Model combining ARIMA and MLR
        Uses weighted average of both models
        
        Args:
            periods: Number of periods to forecast
        
        Returns:
            dict with forecasted values and confidence intervals
        """
        try:
            arima_forecast = self.forecast_arima(periods)
            mlr_forecast = self.forecast_mlr(periods)
            
            if not (arima_forecast['success'] and mlr_forecast['success']):
                return {'success': False, 'error': 'Failed to generate both forecasts'}
            
            # Weight by R² (model with better fit gets higher weight)
            total_r2 = arima_forecast['r_squared'] + mlr_forecast['r_squared']
            arima_weight = arima_forecast['r_squared'] / total_r2 if total_r2 > 0 else 0.5
            mlr_weight = mlr_forecast['r_squared'] / total_r2 if total_r2 > 0 else 0.5
            
            # Combine forecasts
            hybrid_values = (
                arima_weight * arima_forecast['forecasted_values'] +
                mlr_weight * mlr_forecast['forecasted_values']
            )
            
            # Combine confidence intervals (take average)
            hybrid_lower = (
                arima_weight * arima_forecast['lower_bounds'] +
                mlr_weight * mlr_forecast['lower_bounds']
            )
            hybrid_upper = (
                arima_weight * arima_forecast['upper_bounds'] +
                mlr_weight * mlr_forecast['upper_bounds']
            )
            
            # Average metrics
            hybrid_mape = (arima_forecast['mape'] + mlr_forecast['mape']) / 2
            hybrid_r2 = (arima_forecast['r_squared'] + mlr_forecast['r_squared']) / 2
            
            return {
                'model_type': 'hybrid',
                'forecasted_values': hybrid_values,
                'lower_bounds': hybrid_lower,
                'upper_bounds': hybrid_upper,
                'mape': hybrid_mape,
                'r_squared': hybrid_r2,
                'parameters': {
                    'arima_weight': arima_weight,
                    'mlr_weight': mlr_weight,
                    'arima_r2': arima_forecast['r_squared'],
                    'mlr_r2': mlr_forecast['r_squared']
                },
                'success': True
            }
        
        except Exception as e:
            logger.error(f"Hybrid forecast failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def generate_forecast(self, model_type='hybrid', periods=7, user=None):
        """
        Generate and save forecast to database
        
        Args:
            model_type: Type of model (arima, mlr, hybrid)
            periods: Number of periods to forecast
            user: User instance for logging
        
        Returns:
            dict with status and forecast IDs
        """
        try:
            # Prepare data
            if not self.prepare_data():
                return {'success': False, 'error': 'Insufficient data for forecasting'}
            
            # Generate forecast based on model type
            if model_type == 'arima':
                result = self.forecast_arima(periods)
            elif model_type == 'mlr':
                result = self.forecast_mlr(periods)
            else:  # hybrid
                result = self.forecast_hybrid(periods)
            
            if not result['success']:
                return {'success': False, 'error': result.get('error', 'Unknown error')}
            
            # Save forecasts to database
            forecast_ids = []
            start_date = timezone.now().date()
            
            for i, (forecast_value, lower, upper) in enumerate(zip(
                result['forecasted_values'],
                result['lower_bounds'],
                result['upper_bounds']
            )):
                forecast_date = start_date + timedelta(days=i+1)
                
                forecast = Forecast.objects.create(
                    flock=self.flock,
                    forecast_type=self.forecast_type,
                    model_type=model_type,
                    forecast_date=forecast_date,
                    forecasted_value=Decimal(str(forecast_value)),
                    upper_bound=Decimal(str(upper)),
                    lower_bound=Decimal(str(lower)),
                    mean_absolute_percentage_error=Decimal(str(result['mape'])),
                    r_squared=Decimal(str(result['r_squared'])),
                    model_parameters=result['parameters'],
                    is_active=True
                )
                forecast_ids.append(forecast.id)
            
            # Log system activity
            SystemLog.objects.create(
                log_type='forecast_run',
                message=f'{model_type.upper()} forecast generated for {self.flock.flock_id} ({self.data_type}). MAPE: {result["mape"]:.2f}%, R²: {result["r_squared"]:.4f}',
                user=user,
                status='info'
            )
            
            return {
                'success': True,
                'forecast_ids': forecast_ids,
                'model_type': model_type,
                'mape': result['mape'],
                'r_squared': result['r_squared']
            }
        
        except Exception as e:
            logger.error(f"Forecast generation failed: {str(e)}")
            if user:
                SystemLog.objects.create(
                    log_type='forecast_run',
                    message=f'Forecast generation failed: {str(e)}',
                    user=user,
                    status='error'
                )
            return {'success': False, 'error': str(e)}
