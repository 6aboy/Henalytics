from django.core.management.base import BaseCommand

from EggProduction.forecasting_service import ForecastingService
from EggProduction.models import Flock


class Command(BaseCommand):
    help = 'Compare ARIMA forecasts against a simple last-value baseline.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--data-type',
            choices=['egg', 'sales'],
            default='egg',
            help='Operational data to evaluate.',
        )
        parser.add_argument('--flock-id', type=int, help='Database ID of the flock to evaluate for egg forecasts.')
        parser.add_argument('--overall-only', action='store_true', help='Skip per-size/category series.')

    def handle(self, *args, **options):
        include_sizes = not options['overall_only']

        if options['data_type'] == 'sales':
            results = ForecastingService.evaluate_sales_forecasts(include_sizes=include_sizes)
            self._write_results('Sales Revenue Forecast Evaluation', results)
            return

        flock = self._get_flock(options['flock_id'])
        if flock is None:
            return

        results = ForecastingService.evaluate_egg_forecasts(flock, include_sizes=include_sizes)
        self._write_results(f'Egg Forecast Evaluation - House {flock.house_no}', results)

    def _get_flock(self, flock_id):
        flocks = Flock.objects.filter(status='active')
        if flock_id:
            flocks = flocks.filter(id=flock_id)

        flock = flocks.order_by('-date_started').first()
        if flock is None:
            self.stdout.write(self.style.ERROR('No matching active flock found.'))
            return None
        return flock

    def _write_results(self, title, results):
        self.stdout.write(self.style.MIGRATE_HEADING(title))
        self.stdout.write(
            'category | rows | test | model_order | arima_rmse | baseline_rmse | '
            'winner | improvement | arima_r2 | arima_mape'
        )

        for result in results:
            if not result['success']:
                self.stdout.write(f'{result["category"]} | {result["error"]}')
                continue

            arima = result['arima']
            baseline = result['baseline']
            self.stdout.write(
                f'{result["category"]} | '
                f'{result["rows"]} | '
                f'{result["test_rows"]} | '
                f'{result["model_order"]} | '
                f'{self._format_number(arima["rmse"])} | '
                f'{self._format_number(baseline["rmse"])} | '
                f'{result["winner"]} | '
                f'{self._format_percent(result["improvement_pct"])} | '
                f'{self._format_number(arima["r2"], 4)} | '
                f'{self._format_percent(arima["mape"])}'
            )

    @staticmethod
    def _format_number(value, places=2):
        if value is None:
            return 'N/A'
        return f'{value:.{places}f}'

    @staticmethod
    def _format_percent(value):
        if value is None:
            return 'N/A'
        return f'{value:.2f}%'
