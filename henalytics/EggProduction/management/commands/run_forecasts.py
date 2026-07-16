from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from EggProduction.forecasting_service import ForecastingService
from EggProduction.models import Flock, GradingLog, ProductionLog, SalesItem


class Command(BaseCommand):
    help = 'Generate forecasts for active flocks from production, grading, or sales records.'

    def add_arguments(self, parser):
        parser.add_argument('--flock-id', type=int, help='Database ID of a specific flock to forecast.')
        parser.add_argument(
            '--model',
            type=str,
            default='hybrid',
            choices=['arima', 'mlr', 'hybrid'],
            help='Forecasting model to use.',
        )
        parser.add_argument('--periods', type=int, default=30, help='Number of future days to forecast.')
        parser.add_argument(
            '--data-type',
            type=str,
            default='egg_production',
            choices=['egg_production', 'grading', 'sales_volume', 'hen_performance'],
            help='Operational data to forecast.',
        )

    def handle(self, *args, **options):
        admin_user = User.objects.filter(is_staff=True).first()
        flocks = Flock.objects.filter(status='active')

        if options['flock_id']:
            flocks = flocks.filter(id=options['flock_id'])

        if not flocks.exists():
            self.stdout.write(self.style.WARNING('No active flocks found to forecast.'))
            return

        total_forecasts = 0
        total_errors = 0

        for flock in flocks:
            if not self._has_source_data(flock, options['data_type']):
                self.stdout.write(
                    self.style.WARNING(
                        f'No {options["data_type"]} records for House {flock.house_no} (flock #{flock.id}).'
                    )
                )
                continue

            service = ForecastingService(flock, options['data_type'])
            result = service.generate_forecast(options['model'], options['periods'], admin_user)

            if result['success']:
                total_forecasts += len(result['forecast_ids'])
                self.stdout.write(
                    self.style.SUCCESS(
                        f'House {flock.house_no}: generated {len(result["forecast_ids"])} '
                        f'{result["model_type"]} forecast rows.'
                    )
                )
            else:
                total_errors += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'House {flock.house_no}: {result.get("error", "Unknown forecasting error")}'
                    )
                )

        self.stdout.write(self.style.SUCCESS(f'Generated {total_forecasts} forecast rows.'))
        if total_errors:
            self.stdout.write(self.style.WARNING(f'{total_errors} flock forecast(s) failed.'))

    @staticmethod
    def _has_source_data(flock, data_type):
        if data_type == 'sales_volume':
            return SalesItem.objects.filter(transaction__flock=flock).exists()
        if data_type == 'grading':
            return GradingLog.objects.filter(flock=flock).exists()
        return ProductionLog.objects.filter(flock=flock).exists()
