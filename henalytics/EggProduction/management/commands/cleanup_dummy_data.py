from django.core.management.base import BaseCommand

from EggProduction.models import Flock, ModelVersion, SalesForecast


class Command(BaseCommand):
    help = 'Remove dummy House 99 data and optionally clear old forecast outputs.'

    def add_arguments(self, parser):
        parser.add_argument('--with-forecasts', action='store_true', help='Also delete all sales forecasts and orphan model versions.')

    def handle(self, *args, **options):
        deleted_flocks, _ = Flock.objects.filter(house_no=99).delete()
        self.stdout.write(self.style.SUCCESS(f'Removed dummy House 99 records: {deleted_flocks} object(s).'))

        if options['with_forecasts']:
            deleted_sales_forecasts, _ = SalesForecast.objects.all().delete()
            deleted_models, _ = ModelVersion.objects.filter(
                harvest_forecasts__isnull=True,
                sales_forecasts__isnull=True,
            ).delete()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Removed {deleted_sales_forecasts} sales forecast object(s) and '
                    f'{deleted_models} orphan model object(s).'
                )
            )
