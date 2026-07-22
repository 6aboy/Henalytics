from django.test import TestCase

from .models import Flock, ProductionLog, GradingLog, SalesTransaction, SalesItem, ModelVersion, HarvestForecast, SalesForecast


class MarkdownSchemaFieldTest(TestCase):
    def test_markdown_schema_fields_exist(self):
        self.assertTrue(hasattr(Flock, 'house_no'))
        self.assertTrue(hasattr(ProductionLog, 'log_date'))
        self.assertTrue(hasattr(ProductionLog, 'hen_count'))
        self.assertTrue(hasattr(ProductionLog, 'dead_count'))
        self.assertTrue(hasattr(ProductionLog, 'culled_count'))
        self.assertTrue(hasattr(ProductionLog, 'feed_bags'))
        self.assertTrue(hasattr(ProductionLog, 'eggs_total'))
        self.assertTrue(hasattr(ProductionLog, 'pct_hen_day'))
        self.assertTrue(hasattr(ProductionLog, 'pct_hen_housed'))
        self.assertTrue(hasattr(ProductionLog, 'fcr'))
        self.assertTrue(hasattr(ProductionLog, 'remarks'))

        self.assertTrue(hasattr(GradingLog, 'log_date'))
        self.assertTrue(hasattr(GradingLog, 'eggs_total'))
        self.assertTrue(hasattr(GradingLog, 'eggs_aa'))
        self.assertTrue(hasattr(GradingLog, 'eggs_a'))
        self.assertTrue(hasattr(GradingLog, 'eggs_b'))
        self.assertTrue(hasattr(GradingLog, 'eggs_small'))
        self.assertTrue(hasattr(GradingLog, 'eggs_broken'))
        self.assertTrue(hasattr(GradingLog, 'eggs_decode'))
        self.assertTrue(hasattr(GradingLog, 'eggs_source'))

        self.assertTrue(hasattr(SalesTransaction, 'sale_date'))
        self.assertTrue(hasattr(SalesTransaction, 'or_number'))
        self.assertTrue(hasattr(SalesItem, 'quantity_pieces'))
        self.assertTrue(hasattr(SalesItem, 'unit_price'))
        self.assertTrue(hasattr(SalesItem, 'amount'))
        self.assertTrue(hasattr(SalesItem, 'total_amount'))

        self.assertTrue(hasattr(HarvestForecast, 'forecast_date'))
        self.assertTrue(hasattr(SalesForecast, 'forecast_date'))
