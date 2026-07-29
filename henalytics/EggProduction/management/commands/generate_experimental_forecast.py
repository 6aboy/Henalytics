import json
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from EggProduction.forecasting_service import ForecastingService


class Command(BaseCommand):
    help = 'Generate JSON output from the experimental cleaned-CSV SARIMAX model.'

    def add_arguments(self, parser):
        parser.add_argument('--horizon', type=int, default=30)
        parser.add_argument(
            '--range',
            choices=['week', 'three_weeks', 'month', 'three_months'],
            help='Named forecast horizon. Overrides --horizon when provided.',
        )
        parser.add_argument('--model-name', default='sarimax_clean_v1')

    def handle(self, *args, **options):
        self._ensure_project_root_on_path()

        try:
            from ml.predict import forecast
        except ImportError as exc:
            raise CommandError(f'Unable to import ml.predict: {exc}') from exc

        horizon = options['horizon']
        if options.get('range'):
            horizon = ForecastingService.periods_for_range(options['range'])

        try:
            result = forecast(horizon=horizon, model_name=options['model_name'])
        except Exception as exc:
            raise CommandError(f'Experimental forecast failed: {exc}') from exc

        self.stdout.write(json.dumps(result, indent=2))

    @staticmethod
    def _ensure_project_root_on_path():
        project_root = Path(settings.BASE_DIR).parent
        project_root_text = str(project_root)
        if project_root_text not in sys.path:
            sys.path.insert(0, project_root_text)
