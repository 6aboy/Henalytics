from django.test import TestCase

from .models import Flock, ProductionLog, GradingLog, SalesTransaction, SalesItem, ModelVersion, HarvestForecast, SalesForecast


class MarkdownSchemaFieldTest(TestCase):
    def test_markdown_schema_fields_exist(self):
        self.assertTrue(hasattr(Flock, 'house_no'))
        self.assertTrue(hasattr(ProductionLog, 'production_date'))
        self.assertTrue(hasattr(ProductionLog, 'live_hen_count'))
        self.assertTrue(hasattr(ProductionLog, 'daily_mortality'))
        self.assertTrue(hasattr(ProductionLog, 'daily_culls'))
        self.assertTrue(hasattr(ProductionLog, 'feed_consumed_bags'))
        self.assertTrue(hasattr(ProductionLog, 'eggs_collected'))
        self.assertTrue(hasattr(ProductionLog, 'hen_day_production'))
        self.assertTrue(hasattr(ProductionLog, 'hen_housed_production'))
        self.assertTrue(hasattr(ProductionLog, 'feed_conversion_ratio'))
        self.assertTrue(hasattr(ProductionLog, 'management_remarks'))

        self.assertTrue(hasattr(GradingLog, 'grading_date'))
        self.assertTrue(hasattr(GradingLog, 'grade_jumbo'))
        self.assertTrue(hasattr(GradingLog, 'grade_extra_large'))
        self.assertTrue(hasattr(GradingLog, 'grade_large'))
        self.assertTrue(hasattr(GradingLog, 'grade_medium'))
        self.assertTrue(hasattr(GradingLog, 'grade_small'))
        self.assertTrue(hasattr(GradingLog, 'grade_pullets'))
        self.assertTrue(hasattr(GradingLog, 'grade_peewee'))
        self.assertTrue(hasattr(GradingLog, 'cracked_eggs'))
        self.assertTrue(hasattr(GradingLog, 'source'))

        self.assertTrue(hasattr(SalesTransaction, 'sale_date'))
        self.assertTrue(hasattr(SalesItem, 'quantity_trays'))
        self.assertTrue(hasattr(SalesItem, 'price_per_tray'))
        self.assertTrue(hasattr(SalesItem, 'total_amount'))

        self.assertTrue(hasattr(ModelVersion, 'mae'))
        self.assertTrue(hasattr(HarvestForecast, 'forecast_date'))
        self.assertTrue(hasattr(SalesForecast, 'forecast_date'))
