from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from EggProduction.forecasting_service import ForecastingService
from EggProduction.models import Flock, ProductionLog, SalesItem


class Command(BaseCommand):
    help = 'Generate forecasts for active flocks from production, grading, or sales records.'

    def add_arguments(self, parser):
        parser.add_argument('--flock-id', type=int, help='Database ID of a specific flock to forecast.')
        parser.add_argument('--periods', type=int, default=30, help='Number of future days to forecast.')
        parser.add_argument(
            '--data-type',
            type=str,
            default='egg',
            choices=['egg', 'sales'],
            help='Operational data to forecast.',
        )
        parser.add_argument('--overall-only', action='store_true', help='Deprecated: egg forecasts are always overall-only.')

    def handle(self, *args, **options):
        admin_user = User.objects.filter(is_staff=True).first()

        total_forecasts = 0
        total_errors = 0

        if options['data_type'] == 'sales':
            result = ForecastingService.generate_sales_forecasts(
                periods=options['periods'],
                user=admin_user,
                include_sizes=not options['overall_only'],
            )
            self._write_result('Sales revenue', result)
            return

        flocks = Flock.objects.filter(status='active')

        if options['flock_id']:
            flocks = flocks.filter(id=options['flock_id'])

        if not flocks.exists():
            self.stdout.write(self.style.WARNING('No active flocks found to forecast.'))
            return

        for flock in flocks:
            if not self._has_source_data(flock, options['data_type']):
                self.stdout.write(self.style.WARNING(f'No production records for House {flock.house_no}.'))
                continue

            result = ForecastingService.generate_egg_forecasts(
                flock=flock,
                periods=options['periods'],
                user=admin_user,
            )

            if result['success']:
                total_forecasts += result['created_count']
                self.stdout.write(
                    self.style.SUCCESS(
                        f'House {flock.house_no}: generated {result["created_count"]} ARIMA forecast rows.'
                    )
                )
            else:
                total_errors += 1
                error_text = '; '.join(result.get('errors', [])) or 'No forecasts generated.'
                self.stdout.write(
                    self.style.ERROR(
                        f'House {flock.house_no}: {error_text}'
                    )
                )

        self.stdout.write(self.style.SUCCESS(f'Generated {total_forecasts} forecast rows.'))
        if total_errors:
            self.stdout.write(self.style.WARNING(f'{total_errors} flock forecast(s) failed.'))

    def _write_result(self, label, result):
        if result['success']:
            self.stdout.write(self.style.SUCCESS(f'{label}: generated {result["created_count"]} ARIMA forecast rows.'))
        else:
            self.stdout.write(self.style.ERROR(f'{label}: {"; ".join(result["errors"]) or "No forecasts generated."}'))

    @staticmethod
    def _has_source_data(flock, data_type):
        if data_type == 'sales':
            return SalesItem.objects.exists()
        return ProductionLog.objects.filter(flock=flock).exists()
