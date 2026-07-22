from datetime import date, datetime, timedelta
from decimal import Decimal
import calendar
import re

from django.contrib.auth.models import User
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from openpyxl import load_workbook

from EggProduction.models import (
    Flock,
    GradingLog,
    HarvestForecast,
    ProductionLog,
    SalesItem,
    SalesTransaction,
)


class Command(BaseCommand):
    help = 'Import the Henalytics historical Excel datasets into the database for ARIMA training.'

    EGG_GRADE_COLUMNS = {
        'jumbo': 'eggs_aa',
        'xl': 'eggs_aa',
        'x-large': 'eggs_aa',
        'large': 'eggs_a',
        'medium': 'eggs_b',
        'small': 'eggs_small',
        'pullets': 'eggs_decode',
        'pullet': 'eggs_decode',
        'pewee': 'eggs_decode',
        'peewee': 'eggs_decode',
        'broken': 'eggs_broken',
    }
    SALES_GRADES = {
        'JUMBO': 'jumbo',
        'X-LARGE': 'xl',
        'LARGE': 'large',
        'MEDIUM': 'medium',
        'SMALL': 'small',
        'PULLETS': 'pullets',
        'PEEWEE': 'pewee',
        'BROKEN': 'broken',
        'CULL': 'cull',
        'SACK': 'sack',
    }
    def add_arguments(self, parser):
        parser.add_argument('--egg-file', default='Egg Production DATASET.xlsx')
        parser.add_argument('--sales-file', default='Sales Dataset.xlsx')
        parser.add_argument('--house-no', type=int, default=3)
        parser.add_argument('--flock-start-date', default='2024-06-01')
        parser.add_argument('--username', default='historical_import_admin')
        parser.add_argument('--replace-existing', action='store_true', help='Delete prior imported dataset rows for this flock first.')

    def handle(self, *args, **options):
        user, _ = User.objects.get_or_create(
            username=options['username'],
            defaults={
                'is_staff': True,
                'is_superuser': True,
                'email': 'historical-import@example.com',
            },
        )
        if options['replace_existing']:
            self._delete_imported_rows_for_house(options['house_no'])
        flock = self._get_dataset_flock(options['house_no'], options['flock_start_date'])

        egg_file = self._resolve_file(options['egg_file'])
        sales_file = self._resolve_file(options['sales_file'])
        production_count = self._import_production(egg_file, flock, user)
        grading_count = self._import_classified_eggs(egg_file, flock)
        transaction_count, item_count = self._import_sales(sales_file, flock, user)

        self.stdout.write(
            self.style.SUCCESS(
                'Imported historical dataset: '
                f'{production_count} production rows, '
                f'{grading_count} grading rows, '
                f'{transaction_count} sales transactions, '
                f'{item_count} sales items.'
            )
        )

    @staticmethod
    def _delete_imported_rows_for_house(house_no):
        flocks = Flock.objects.filter(house_no=house_no)
        HarvestForecast.objects.filter(flock__in=flocks).delete()
        ProductionLog.objects.filter(flock__in=flocks, remarks__startswith='Imported from').delete()
        GradingLog.objects.filter(flock__in=flocks, eggs_source__startswith='Imported from').delete()
        SalesTransaction.objects.filter(flock__in=flocks, notes__startswith='Imported from').delete()

    @staticmethod
    def _delete_imported_rows(flock):
        ProductionLog.objects.filter(flock=flock, remarks__startswith='Imported from').delete()
        GradingLog.objects.filter(flock=flock, eggs_source__startswith='Imported from').delete()
        SalesTransaction.objects.filter(flock=flock, notes__startswith='Imported from').delete()

    @staticmethod
    def _resolve_file(file_path):
        from pathlib import Path

        path = Path(file_path)
        if path.exists():
            return path
        base_path = Path(settings.BASE_DIR) / file_path
        if base_path.exists():
            return base_path
        return path

    def _get_dataset_flock(self, house_no, flock_start_date):
        start_date = date.fromisoformat(flock_start_date)
        flock, _ = Flock.objects.update_or_create(
            house_no=house_no,
            date_started=start_date,
            defaults={
                'breed_strain': 'Historical Dataset Layer',
                'initial_hen_count': 1985,
                'status': 'active',
                'notes': 'Imported historical dataset for ARIMA training.',
            },
        )
        return flock

    def _import_production(self, file_path, flock, user):
        wb = load_workbook(file_path, data_only=True)
        current_date = None
        current_age_week = 0
        imported = 0

        for sheet_name in wb.sheetnames:
            if not sheet_name.startswith('H3_'):
                continue

            ws = wb[sheet_name]
            for row in ws.iter_rows(min_row=1, values_only=True):
                if not row or str(row[0]).strip().lower() == 'age week':
                    continue

                raw_date = self._cell(row, 1)
                if isinstance(raw_date, datetime):
                    current_date = raw_date.date()

                pieces = self._int_or_none(self._cell(row, 5))
                bird_no = self._int_or_none(self._cell(row, 2))
                if pieces is None or bird_no is None:
                    continue

                if isinstance(raw_date, datetime):
                    resolved_date = raw_date.date()
                else:
                    resolved_date = self._resolve_running_date(raw_date, current_date)
                    if resolved_date is None:
                        continue
                current_date = resolved_date

                age_week = self._int_or_none(self._cell(row, 0))
                if age_week is not None:
                    current_age_week = age_week

                dead = self._int_or_zero(self._cell(row, 3))
                cull = self._int_or_zero(self._cell(row, 4))
                feed_bags = self._feed_bags(self._cell(row, 8))

                ProductionLog.objects.update_or_create(
                    flock=flock,
                    log_date=resolved_date,
                    defaults={
                        'age_weeks': current_age_week,
                        'age_days': max((resolved_date - flock.date_started).days, 0),
                        'hen_count': bird_no,
                        'dead_count': dead,
                        'culled_count': cull,
                        'feed_bags': feed_bags,
                        'eggs_total': pieces,
                        'pct_hen_day': Decimal('0.00'),
                        'pct_hen_housed': Decimal('0.00'),
                        'remarks': f'Imported from {sheet_name}.',
                        'entered_by': user,
                    },
                )
                imported += 1

        return imported

    def _import_classified_eggs(self, file_path, flock):
        wb = load_workbook(file_path, data_only=True)
        imported = 0

        for sheet_name in wb.sheetnames:
            if not sheet_name.startswith('ClassifiedEggs-'):
                continue

            month, year = self._month_year_from_sheet(sheet_name)
            if not month or not year:
                continue

            ws = wb[sheet_name]
            headers = [self._normalize_header(cell.value) for cell in ws[2]]
            for row in ws.iter_rows(min_row=3, values_only=True):
                day = self._int_or_none(self._cell(row, 0))
                if day is None:
                    continue

                log_date = date(year, month, day)
                values = {
                    'eggs_aa': 0,
                    'eggs_a': 0,
                    'eggs_b': 0,
                    'eggs_small': 0,
                    'eggs_broken': 0,
                    'eggs_decode': 0,
                }
                for index, header in enumerate(headers):
                    field = self.EGG_GRADE_COLUMNS.get(header)
                    if field:
                        values[field] += self._int_or_zero(self._cell(row, index))

                eggs_total = sum(values.values())
                if eggs_total <= 0:
                    continue

                GradingLog.objects.update_or_create(
                    flock=flock,
                    log_date=log_date,
                    defaults={
                        'age_weeks': max(((log_date - flock.date_started).days // 7), 0),
                        'eggs_total': eggs_total,
                        'eggs_source': f'Imported from {sheet_name}.',
                        **values,
                    },
                )
                imported += 1

        return imported

    def _import_sales(self, file_path, flock, user):
        wb = load_workbook(file_path, data_only=True)
        transactions = 0
        items = 0

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            category_pairs = self._sales_category_pairs(ws)
            current_date = None

            for row in ws.iter_rows(min_row=1, values_only=True):
                first = self._cell(row, 0)
                if isinstance(first, datetime):
                    current_date = first.date()
                    continue
                if first in (None, 'DATE') or current_date is None:
                    continue

                or_number = self._cell(row, 1)
                if or_number in (None, 'OR'):
                    continue

                transaction = SalesTransaction.objects.create(
                    flock=flock,
                    sale_date=current_date,
                    or_number=str(int(or_number)) if isinstance(or_number, (int, float)) else str(or_number).strip(),
                    recorded_by=user,
                    notes=f'Imported from {sheet_name}.',
                )
                transactions += 1

                for grade, pcs_col, amount_col in category_pairs:
                    quantity = self._int_or_zero(self._cell(row, pcs_col))
                    amount = self._decimal_or_zero(self._cell(row, amount_col))
                    if quantity <= 0 and amount <= 0:
                        continue
                    SalesItem.objects.create(
                        transaction=transaction,
                        grade=grade,
                        quantity_pieces=quantity,
                        amount=amount,
                    )
                    items += 1

        return transactions, items

    def _sales_category_pairs(self, ws):
        labels = [cell.value for cell in ws[2]]
        pairs = []
        for index, label in enumerate(labels):
            grade = self.SALES_GRADES.get(str(label).strip().upper()) if label else None
            if grade and index + 1 < len(labels):
                pairs.append((grade, index, index + 1))
        return pairs

    @staticmethod
    def _resolve_running_date(raw_value, previous_date):
        if isinstance(raw_value, datetime):
            return raw_value.date()
        if not isinstance(raw_value, (int, float)):
            return None

        day = int(raw_value)
        if not 1 <= day <= 31:
            return None
        if previous_date is None:
            return None

        year = previous_date.year
        month = previous_date.month
        candidate = Command._safe_date(year, month, day)
        while candidate is None:
            month += 1
            if month > 12:
                month = 1
                year += 1
            candidate = Command._safe_date(year, month, day)
        while candidate <= previous_date and day < previous_date.day:
            month += 1
            if month > 12:
                month = 1
                year += 1
            candidate = Command._safe_date(year, month, day)
            while candidate is None:
                month += 1
                if month > 12:
                    month = 1
                    year += 1
                candidate = Command._safe_date(year, month, day)
        return candidate

    @staticmethod
    def _safe_date(year, month, day):
        if day > calendar.monthrange(year, month)[1]:
            return None
        return date(year, month, day)

    @staticmethod
    def _month_year_from_sheet(sheet_name):
        match = re.search(r'ClassifiedEggs-([A-Za-z]+)\s*(\d{2})', sheet_name)
        if not match:
            return None, None
        month_name, short_year = match.groups()
        month = datetime.strptime(month_name[:3], '%b').month
        return month, 2000 + int(short_year)

    @staticmethod
    def _normalize_header(value):
        return str(value or '').strip().lower().replace('_', '-')

    @staticmethod
    def _cell(row, index):
        return row[index] if index < len(row) else None

    @staticmethod
    def _int_or_none(value):
        if value in (None, ''):
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @classmethod
    def _int_or_zero(cls, value):
        return cls._int_or_none(value) or 0

    @staticmethod
    def _decimal_or_zero(value):
        if value in (None, ''):
            return Decimal('0.00')
        try:
            return Decimal(str(value)).quantize(Decimal('0.01'))
        except Exception:
            return Decimal('0.00')

    @staticmethod
    def _feed_bags(value):
        if value in (None, ''):
            return 0
        if isinstance(value, str) and 'kg' in value.lower():
            match = re.search(r'([0-9]+(?:\.[0-9]+)?)', value)
            if match:
                return int(round(float(match.group(1)) / 50))
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return 0
