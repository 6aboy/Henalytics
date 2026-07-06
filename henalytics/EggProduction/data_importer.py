"""
Data Import Utility Module
Handles importing data from Excel files into Henalytics system
"""
import pandas as pd
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib.auth.models import User
from django.utils import timezone

from .models import (
    Flock, HenPerformance, EggProduction, EggGrading,
    SalesRecord, DailyRevenue, TimeSeriesData, SystemLog
)

logger = logging.getLogger(__name__)


class DataImporter:
    """Import data from Excel files into the database"""
    
    def __init__(self, file_path, user=None):
        """
        Initialize data importer
        
        Args:
            file_path: Path to Excel file
            user: User instance for logging and attribution
        """
        self.file_path = file_path
        self.user = user or User.objects.filter(is_staff=True).first()
        self.import_log = {
            'total_records': 0,
            'successful_imports': 0,
            'failed_imports': 0,
            'errors': []
        }
    
    def import_flocks(self, sheet_name='Flocks'):
        """Import flock data from Excel"""
        try:
            df = pd.read_excel(self.file_path, sheet_name=sheet_name)
            
            for idx, row in df.iterrows():
                try:
                    flock, created = Flock.objects.get_or_create(
                        flock_id=str(row['flock_id']).strip(),
                        defaults={
                            'breed': str(row.get('breed', 'Unknown')).strip(),
                            'initial_count': int(row.get('initial_count', 0)),
                            'current_count': int(row.get('current_count', 0)),
                            'status': str(row.get('status', 'active')).lower(),
                            'date_started': pd.to_datetime(row.get('date_started')),
                            'date_ended': pd.to_datetime(row.get('date_ended')) if pd.notna(row.get('date_ended')) else None,
                            'housing_type': str(row.get('housing_type', 'cage')).strip(),
                            'notes': str(row.get('notes', '')).strip(),
                        }
                    )
                    self.import_log['successful_imports'] += 1
                    self.import_log['total_records'] += 1
                
                except Exception as e:
                    self.import_log['failed_imports'] += 1
                    self.import_log['errors'].append(f"Flock row {idx}: {str(e)}")
                    logger.error(f"Error importing flock at row {idx}: {str(e)}")
            
            self._log_import('flocks', sheet_name)
            return self.import_log
        
        except Exception as e:
            logger.error(f"Error importing flocks: {str(e)}")
            self.import_log['errors'].append(f"Flocks import failed: {str(e)}")
            return self.import_log
    
    def import_egg_production(self, sheet_name='EggProduction'):
        """Import egg production data from Excel"""
        try:
            df = pd.read_excel(self.file_path, sheet_name=sheet_name)
            
            for idx, row in df.iterrows():
                try:
                    flock = Flock.objects.get(flock_id=str(row['flock_id']).strip())
                    
                    # Create or update egg production record
                    egg_prod, created = EggProduction.objects.get_or_create(
                        flock=flock,
                        record_date=pd.to_datetime(row['record_date']).date(),
                        defaults={
                            'eggs_collected': int(row.get('eggs_collected', 0)),
                            'broken_eggs': int(row.get('broken_eggs', 0)),
                            'defective_eggs': int(row.get('defective_eggs', 0)),
                            'good_eggs': int(row.get('good_eggs', 0)),
                            'collection_time': row.get('collection_time', '08:00'),
                            'eggs_per_hen': Decimal(str(row.get('eggs_per_hen', 0))),
                            'hen_day_production': Decimal(str(row.get('hen_day_production', 0))),
                            'hen_housed_production': Decimal(str(row.get('hen_housed_production', 0))),
                            'notes': str(row.get('notes', '')).strip(),
                            'created_by': self.user,
                        }
                    )
                    
                    # Add egg grading if provided
                    if 'grade_aa' in row.columns and pd.notna(row['grade_aa']):
                        for grade, count in [('AA', 'grade_aa'), ('A', 'grade_a'), 
                                             ('B', 'grade_b'), ('C', 'grade_c')]:
                            if count in row.columns and pd.notna(row[count]):
                                EggGrading.objects.get_or_create(
                                    egg_production=egg_prod,
                                    grade=grade,
                                    defaults={
                                        'count': int(row[count]),
                                        'average_weight': Decimal(str(row.get(f'avg_weight_{grade.lower()}', 0)))
                                    }
                                )
                    
                    self.import_log['successful_imports'] += 1
                    self.import_log['total_records'] += 1
                
                except Flock.DoesNotExist:
                    self.import_log['failed_imports'] += 1
                    self.import_log['errors'].append(f"EggProduction row {idx}: Flock not found")
                except Exception as e:
                    self.import_log['failed_imports'] += 1
                    self.import_log['errors'].append(f"EggProduction row {idx}: {str(e)}")
                    logger.error(f"Error importing egg production at row {idx}: {str(e)}")
            
            self._log_import('egg_production', sheet_name)
            return self.import_log
        
        except Exception as e:
            logger.error(f"Error importing egg production: {str(e)}")
            self.import_log['errors'].append(f"Egg production import failed: {str(e)}")
            return self.import_log
    
    def import_sales(self, sheet_name='Sales'):
        """Import sales data from Excel"""
        try:
            df = pd.read_excel(self.file_path, sheet_name=sheet_name)
            
            for idx, row in df.iterrows():
                try:
                    flock = Flock.objects.get(flock_id=str(row['flock_id']).strip())
                    
                    sale = SalesRecord.objects.create(
                        flock=flock,
                        sale_date=pd.to_datetime(row['sale_date']).date(),
                        eggs_sold=int(row.get('eggs_sold', 0)),
                        price_per_unit=Decimal(str(row.get('price_per_unit', 0))),
                        buyer_name=str(row.get('buyer_name', 'Unknown')).strip(),
                        buyer_contact=str(row.get('buyer_contact', '')).strip(),
                        status=str(row.get('status', 'completed')).lower(),
                        recorded_by=self.user,
                    )
                    
                    self.import_log['successful_imports'] += 1
                    self.import_log['total_records'] += 1
                
                except Flock.DoesNotExist:
                    self.import_log['failed_imports'] += 1
                    self.import_log['errors'].append(f"Sales row {idx}: Flock not found")
                except Exception as e:
                    self.import_log['failed_imports'] += 1
                    self.import_log['errors'].append(f"Sales row {idx}: {str(e)}")
                    logger.error(f"Error importing sales at row {idx}: {str(e)}")
            
            self._log_import('sales', sheet_name)
            return self.import_log
        
        except Exception as e:
            logger.error(f"Error importing sales: {str(e)}")
            self.import_log['errors'].append(f"Sales import failed: {str(e)}")
            return self.import_log
    
    def import_hen_performance(self, sheet_name='HenPerformance'):
        """Import hen performance data from Excel"""
        try:
            df = pd.read_excel(self.file_path, sheet_name=sheet_name)
            
            for idx, row in df.iterrows():
                try:
                    flock = Flock.objects.get(flock_id=str(row['flock_id']).strip())
                    
                    perf = HenPerformance.objects.create(
                        flock=flock,
                        record_date=pd.to_datetime(row['record_date']).date(),
                        average_weight=Decimal(str(row.get('average_weight', 0))),
                        feed_consumption=Decimal(str(row.get('feed_consumption', 0))),
                        water_consumption=Decimal(str(row.get('water_consumption', 0))),
                        mortality_count=int(row.get('mortality_count', 0)),
                        health_status=str(row.get('health_status', 'healthy')).lower(),
                        temperature=Decimal(str(row.get('temperature', 0))),
                        humidity=Decimal(str(row.get('humidity', 0))),
                        notes=str(row.get('notes', '')).strip(),
                        recorded_by=self.user,
                    )
                    
                    self.import_log['successful_imports'] += 1
                    self.import_log['total_records'] += 1
                
                except Flock.DoesNotExist:
                    self.import_log['failed_imports'] += 1
                    self.import_log['errors'].append(f"HenPerformance row {idx}: Flock not found")
                except Exception as e:
                    self.import_log['failed_imports'] += 1
                    self.import_log['errors'].append(f"HenPerformance row {idx}: {str(e)}")
                    logger.error(f"Error importing hen performance at row {idx}: {str(e)}")
            
            self._log_import('hen_performance', sheet_name)
            return self.import_log
        
        except Exception as e:
            logger.error(f"Error importing hen performance: {str(e)}")
            self.import_log['errors'].append(f"Hen performance import failed: {str(e)}")
            return self.import_log
    
    def import_all(self):
        """Import all data from Excel file"""
        sheets = {
            'Flocks': self.import_flocks,
            'EggProduction': self.import_egg_production,
            'HenPerformance': self.import_hen_performance,
            'Sales': self.import_sales,
        }
        
        for sheet_name, import_func in sheets.items():
            try:
                import_func(sheet_name)
            except Exception as e:
                logger.error(f"Error with sheet {sheet_name}: {str(e)}")
                self.import_log['errors'].append(f"Sheet {sheet_name} failed: {str(e)}")
        
        # Log final import summary
        SystemLog.objects.create(
            log_type='data_import',
            message=f'Data import completed. Total: {self.import_log["total_records"]}, '
                   f'Successful: {self.import_log["successful_imports"]}, '
                   f'Failed: {self.import_log["failed_imports"]}',
            user=self.user,
            status='info' if self.import_log['failed_imports'] == 0 else 'warning'
        )
        
        return self.import_log
    
    def _log_import(self, data_type, sheet_name):
        """Log import activity"""
        logger.info(f"Imported {data_type} from sheet '{sheet_name}'")
