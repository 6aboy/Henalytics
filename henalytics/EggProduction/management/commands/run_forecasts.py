"""
Django management command to run forecasts for all flocks
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from EggProduction.models import Flock, TimeSeriesData
from EggProduction.forecasting_service import ForecastingService


class Command(BaseCommand):
    help = 'Generate forecasts for all active flocks using configured models'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--flock-id',
            type=str,
            help='Specific flock ID to forecast',
        )
        parser.add_argument(
            '--model',
            type=str,
            default='hybrid',
            choices=['arima', 'mlr', 'hybrid'],
            help='Forecasting model to use',
        )
        parser.add_argument(
            '--periods',
            type=int,
            default=7,
            help='Number of periods to forecast',
        )
        parser.add_argument(
            '--data-type',
            type=str,
            help='Data type to forecast (egg_production, sales_volume, sales_price, hen_performance)',
        )
    
    def handle(self, *args, **options):
        flock_id = options.get('flock_id')
        model_type = options.get('model', 'hybrid')
        periods = options.get('periods', 7)
        data_type = options.get('data_type')
        
        # Get system admin user for logging
        admin_user = User.objects.filter(is_staff=True).first()
        if not admin_user:
            self.stdout.write(self.style.ERROR('No admin user found'))
            return
        
        # Get flocks to forecast
        if flock_id:
            flocks = Flock.objects.filter(flock_id=flock_id)
        else:
            flocks = Flock.objects.filter(status='active')
        
        if not flocks.exists():
            self.stdout.write(self.style.WARNING('No flocks found to forecast'))
            return
        
        # Get data types to forecast
        if data_type:
            data_types = [data_type]
        else:
            data_types = ['egg_production', 'sales_volume', 'sales_price', 'hen_performance']
        
        # Generate forecasts
        total_forecasts = 0
        total_errors = 0
        
        for flock in flocks:
            for dt in data_types:
                # Check if data exists for this flock/data_type
                if not TimeSeriesData.objects.filter(flock=flock, data_type=dt).exists():
                    self.stdout.write(
                        self.style.WARNING(
                            f'No data for {flock.flock_id} - {dt}'
                        )
                    )
                    continue
                
                try:
                    service = ForecastingService(flock, dt, forecast_type=dt.replace('_', ' ').title())
                    result = service.generate_forecast(model_type, periods, admin_user)
                    
                    if result['success']:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✓ {flock.flock_id} - {dt} (MAPE: {result["mape"]:.2f}%, R²: {result["r_squared"]:.4f})'
                            )
                        )
                        total_forecasts += len(result['forecast_ids'])
                    else:
                        self.stdout.write(
                            self.style.ERROR(
                                f'✗ {flock.flock_id} - {dt}: {result.get("error", "Unknown error")}'
                            )
                        )
                        total_errors += 1
                
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'✗ {flock.flock_id} - {dt}: {str(e)}'
                        )
                    )
                    total_errors += 1
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully generated {total_forecasts} forecasts'))
        if total_errors > 0:
            self.stdout.write(self.style.WARNING(f'⚠ {total_errors} forecasts failed'))
