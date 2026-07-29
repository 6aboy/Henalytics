import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Train the experimental cleaned-CSV SARIMAX model.'

    def add_arguments(self, parser):
        parser.add_argument('--model-name', default='sarimax_clean_v1')
        parser.add_argument('--dataset', help='Optional path to a cleaned CSV dataset.')

    def handle(self, *args, **options):
        self._ensure_project_root_on_path()

        try:
            from ml.train import DATA_PATH, train_model
        except ImportError as exc:
            raise CommandError(f'Unable to import ml.train: {exc}') from exc

        dataset_path = Path(options['dataset']) if options.get('dataset') else DATA_PATH

        try:
            result = train_model(dataset_path=dataset_path, model_name=options['model_name'])
        except Exception as exc:
            raise CommandError(f'SARIMAX training failed: {exc}') from exc

        self.stdout.write(self.style.SUCCESS('Experimental SARIMAX model trained.'))
        self.stdout.write(f'Model: {result.model_path}')
        self.stdout.write(f'Metadata: {result.metadata_path}')
        self.stdout.write(f'MAE: {result.metrics["mae"]:.2f}')
        self.stdout.write(f'RMSE: {result.metrics["rmse"]:.2f}')
        if result.metrics.get('mape') is not None:
            self.stdout.write(f'MAPE: {result.metrics["mape"]:.2f}%')

    @staticmethod
    def _ensure_project_root_on_path():
        project_root = Path(settings.BASE_DIR).parent
        project_root_text = str(project_root)
        if project_root_text not in sys.path:
            sys.path.insert(0, project_root_text)
