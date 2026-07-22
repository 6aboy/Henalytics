"""
Excel import helpers for the current Henalytics schema.
"""
import logging
from decimal import Decimal

import pandas as pd
from django.contrib.auth.models import User

from .models import Flock, GradingLog, ProductionLog, SalesItem, SalesTransaction

logger = logging.getLogger(__name__)


class DataImporter:
    """Import flock, production, grading, and sales sheets into the database."""

    def __init__(self, file_path, user=None):
        self.file_path = file_path
        self.user = user or User.objects.filter(is_staff=True).first()
        self.import_log = {
            'total_records': 0,
            'successful_imports': 0,
            'failed_imports': 0,
            'errors': [],
        }

    def import_flocks(self, sheet_name='Flocks'):
        df = self._read_sheet(sheet_name)
        if df is None:
            return self.import_log

        for idx, row in df.iterrows():
            try:
                house_no = int(row.get('house_no', row.get('flock_id', 1)))
                date_started = pd.to_datetime(row.get('date_started')).date()
                Flock.objects.update_or_create(
                    house_no=house_no,
                    date_started=date_started,
                    defaults={
                        'breed_strain': str(row.get('breed_strain', row.get('breed', 'Unknown'))).strip(),
                        'initial_hen_count': int(row.get('initial_hen_count', row.get('initial_count', 1))),
                        'status': str(row.get('status', 'active')).lower(),
                        'notes': str(row.get('notes', '')).strip(),
                    },
                )
                self._mark_success()
            except Exception as exc:
                self._mark_failure('Flocks', idx, exc)

        return self.import_log

    def import_production_logs(self, sheet_name='ProductionLogs'):
        df = self._read_sheet(sheet_name)
        if df is None:
            return self.import_log

        for idx, row in df.iterrows():
            try:
                flock = self._find_flock(row)
                log_date = pd.to_datetime(row.get('log_date', row.get('record_date'))).date()
                eggs_total = int(row.get('eggs_total', row.get('eggs_collected', 0)))
                hen_count = int(row.get('hen_count', row.get('live_hen_count', flock.initial_hen_count)))
                ProductionLog.objects.update_or_create(
                    flock=flock,
                    log_date=log_date,
                    defaults={
                        'age_weeks': int(row.get('age_weeks', 0)),
                        'age_days': int(row.get('age_days', 0)),
                        'hen_count': hen_count,
                        'dead_count': int(row.get('dead_count', row.get('daily_mortality', 0))),
                        'culled_count': int(row.get('culled_count', row.get('daily_culls', 0))),
                        'feed_bags': int(row.get('feed_bags', row.get('feed_consumed_bags', 0))),
                        'eggs_total': eggs_total,
                        'pct_hen_day': Decimal(str(row.get('pct_hen_day', self._percent(eggs_total, hen_count)))),
                        'pct_hen_housed': Decimal(
                            str(row.get('pct_hen_housed', self._percent(eggs_total, flock.initial_hen_count)))
                        ),
                        'fcr': self._decimal_or_none(row.get('fcr')),
                        'remarks': str(row.get('remarks', row.get('management_remarks', ''))).strip(),
                        'entered_by': self.user,
                    },
                )
                self._mark_success()
            except Exception as exc:
                self._mark_failure('ProductionLogs', idx, exc)

        return self.import_log

    def import_grading_logs(self, sheet_name='GradingLogs'):
        df = self._read_sheet(sheet_name)
        if df is None:
            return self.import_log

        for idx, row in df.iterrows():
            try:
                flock = self._find_flock(row)
                log_date = pd.to_datetime(row.get('log_date', row.get('grading_date'))).date()
                GradingLog.objects.update_or_create(
                    flock=flock,
                    log_date=log_date,
                    defaults={
                        'age_weeks': int(row.get('age_weeks', 0)),
                        'eggs_total': int(row.get('eggs_total', 0)),
                        'eggs_aa': int(row.get('eggs_aa', row.get('grade_jumbo', 0))),
                        'eggs_a': int(row.get('eggs_a', row.get('grade_large', 0))),
                        'eggs_b': int(row.get('eggs_b', row.get('grade_medium', 0))),
                        'eggs_small': int(row.get('eggs_small', row.get('grade_small', 0))),
                        'eggs_broken': int(row.get('eggs_broken', row.get('cracked_eggs', 0))),
                        'eggs_decode': int(row.get('eggs_decode', 0)),
                        'eggs_source': str(row.get('eggs_source', row.get('source', 'manual'))).strip(),
                    },
                )
                self._mark_success()
            except Exception as exc:
                self._mark_failure('GradingLogs', idx, exc)

        return self.import_log

    def import_sales(self, sheet_name='Sales'):
        df = self._read_sheet(sheet_name)
        if df is None:
            return self.import_log

        for idx, row in df.iterrows():
            try:
                flock = self._find_flock(row)
                transaction = SalesTransaction.objects.create(
                    flock=flock,
                    sale_date=pd.to_datetime(row.get('sale_date')).date(),
                    or_number=str(row.get('or_number', row.get('OR', row.get('or', '')))).strip(),
                    recorded_by=self.user,
                    notes=str(row.get('notes', row.get('buyer_name', ''))).strip(),
                )
                SalesItem.objects.create(
                    transaction=transaction,
                    grade=self._egg_size(row.get('grade', row.get('size', row.get('egg_size', 'large')))),
                    quantity_pieces=int(row.get('quantity_pieces', row.get('pcs', row.get('quantity_trays', row.get('trays', 0))))),
                    amount=Decimal(str(row.get('amount', row.get('total_amount', 0)))),
                )
                self._mark_success()
            except Exception as exc:
                self._mark_failure('Sales', idx, exc)

        return self.import_log

    def import_all(self):
        for importer in (
            self.import_flocks,
            self.import_production_logs,
            self.import_grading_logs,
            self.import_sales,
        ):
            importer()
        return self.import_log

    def _read_sheet(self, sheet_name):
        try:
            return pd.read_excel(self.file_path, sheet_name=sheet_name)
        except Exception as exc:
            self.import_log['errors'].append(f'{sheet_name} import failed: {exc}')
            logger.exception("Unable to read sheet %s", sheet_name)
            return None

    def _find_flock(self, row):
        if pd.notna(row.get('flock_id')):
            try:
                return Flock.objects.get(id=int(row.get('flock_id')))
            except (Flock.DoesNotExist, ValueError):
                pass

        house_no = int(row.get('house_no', 1))
        return Flock.objects.filter(house_no=house_no, status='active').latest('date_started')

    def _mark_success(self):
        self.import_log['successful_imports'] += 1
        self.import_log['total_records'] += 1

    def _mark_failure(self, sheet_name, row_index, exc):
        self.import_log['failed_imports'] += 1
        self.import_log['errors'].append(f'{sheet_name} row {row_index}: {exc}')
        logger.exception("Import error in %s row %s", sheet_name, row_index)

    @staticmethod
    def _percent(numerator, denominator):
        return round((numerator / denominator) * 100, 2) if denominator else 0

    @staticmethod
    def _decimal_or_none(value):
        if value is None or pd.isna(value) or value == '':
            return None
        return Decimal(str(value))

    @staticmethod
    def _egg_size(value):
        normalized = str(value or 'large').strip().lower().replace('-', ' ').replace('_', ' ')
        mapping = {
            'jumbo': 'jumbo',
            'xl': 'xl',
            'extra large': 'xl',
            'extra-large': 'xl',
            'large': 'large',
            'medium': 'medium',
            'small': 'small',
            'pullets': 'pullets',
            'pullet': 'pullets',
            'pewee': 'pewee',
            'peewee': 'pewee',
            'broken': 'broken',
            'cracked': 'broken',
            'a': 'large',
            'aa': 'jumbo',
            'b': 'medium',
            'c': 'small',
        }
        return mapping.get(normalized, 'large')
