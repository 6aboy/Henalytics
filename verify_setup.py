#!/usr/bin/env python
"""
Henalytics Setup Verification Script
Verifies all components are in place and ready for deployment
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'henalytics.settings')
django.setup()

from django.conf import settings
from django.db import connection
from django.apps import apps

def check_section(title):
    """Print section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def check_item(name, condition, details=""):
    """Check and print a single item"""
    status = "✅" if condition else "❌"
    print(f"{status} {name}")
    if details:
        print(f"   → {details}")
    return condition

def main():
    print("\n" + "="*60)
    print("  HENALYTICS BACKEND VERIFICATION")
    print("="*60)
    
    checks_passed = 0
    checks_failed = 0
    
    # 1. Django Settings
    check_section("Django Configuration")
    
    if check_item(
        "DEBUG mode",
        settings.DEBUG,
        f"DEBUG={settings.DEBUG} (should be False in production)"
    ):
        checks_passed += 1
    else:
        checks_failed += 1
    
    if check_item(
        "SECRET_KEY configured",
        bool(settings.SECRET_KEY) and len(settings.SECRET_KEY) > 20,
        f"Length: {len(settings.SECRET_KEY)} characters"
    ):
        checks_passed += 1
    else:
        checks_failed += 1
    
    if check_item(
        "Database engine",
        'mysql' in settings.DATABASES['default']['ENGINE'],
        f"Engine: {settings.DATABASES['default']['ENGINE']}"
    ):
        checks_passed += 1
    else:
        checks_failed += 1
    
    # 2. Database Connection
    check_section("Database Connection")
    
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_connected = True
    except Exception as e:
        db_connected = False
    
    if check_item(
        "MySQL connection",
        db_connected,
        f"Host: {settings.DATABASES['default']['HOST']}, "
        f"DB: {settings.DATABASES['default']['NAME']}"
    ):
        checks_passed += 1
    else:
        checks_failed += 1
    
    # 3. Installed Apps
    check_section("Django Apps")
    
    required_apps = [
        'django.contrib.admin',
        'django.contrib.auth',
        'rest_framework',
        'EggProduction',
    ]
    
    for app in required_apps:
        installed = app in settings.INSTALLED_APPS
        if check_item(
            f"App: {app}",
            installed,
            "Installed" if installed else "Missing"
        ):
            checks_passed += 1
        else:
            checks_failed += 1
    
    # 4. Models
    check_section("Django Models")
    
    required_models = [
        ('EggProduction', 'UserRole'),
        ('EggProduction', 'Flock'),
        ('EggProduction', 'EggProduction'),
        ('EggProduction', 'SalesRecord'),
        ('EggProduction', 'HenPerformance'),
        ('EggProduction', 'Forecast'),
        ('EggProduction', 'TimeSeriesData'),
        ('EggProduction', 'SystemLog'),
    ]
    
    for app_label, model_name in required_models:
        try:
            model = apps.get_model(app_label, model_name)
            if check_item(
                f"Model: {model_name}",
                True,
                f"Fields: {len(model._meta.get_fields())}"
            ):
                checks_passed += 1
        except LookupError:
            if check_item(
                f"Model: {model_name}",
                False,
                "Model not found"
            ):
                checks_passed += 1
            else:
                checks_failed += 1
    
    # 5. Database Tables
    check_section("Database Tables")
    
    try:
        with connection.cursor() as cursor:
            # Check if tables exist
            cursor.execute("SHOW TABLES FROM `henalytics_db`")
            tables = [row[0] for row in cursor.fetchall()]
            
            if len(tables) > 0:
                check_item(
                    f"Database tables exist",
                    True,
                    f"Found {len(tables)} tables"
                )
                checks_passed += 1
            else:
                check_item(
                    f"Database tables exist",
                    False,
                    "No tables found - run migrations"
                )
                checks_failed += 1
    except Exception as e:
        check_item(
            f"Database tables check",
            False,
            f"Error: {str(e)}"
        )
        checks_failed += 1
    
    # 6. Python Dependencies
    check_section("Python Dependencies")
    
    required_packages = [
        'django',
        'rest_framework',
        'numpy',
        'pandas',
        'sklearn',
        'statsmodels',
    ]
    
    for package in required_packages:
        try:
            __import__(package)
            if check_item(
                f"Package: {package}",
                True,
                "Installed"
            ):
                checks_passed += 1
        except ImportError:
            if check_item(
                f"Package: {package}",
                False,
                "Not installed - run: pip install -r requirements.txt"
            ):
                checks_passed += 1
            else:
                checks_failed += 1
    
    # 7. ViewSets
    check_section("API ViewSets")
    
    try:
        from EggProduction import views
        viewsets = [
            'UserRoleViewSet',
            'FlockViewSet',
            'EggProductionViewSet',
            'SalesRecordViewSet',
            'HenPerformanceViewSet',
            'DailyRevenueViewSet',
            'TimeSeriesDataViewSet',
            'ForecastViewSet',
            'SystemLogViewSet',
        ]
        
        for viewset in viewsets:
            has_viewset = hasattr(views, viewset)
            if check_item(
                f"ViewSet: {viewset}",
                has_viewset,
                "Available" if has_viewset else "Missing"
            ):
                checks_passed += 1
            else:
                checks_failed += 1
    except ImportError as e:
        check_item(
            f"ViewSets import",
            False,
            f"Error: {str(e)}"
        )
        checks_failed += 1
    
    # 8. Serializers
    check_section("API Serializers")
    
    try:
        from EggProduction import serializers
        serializer_classes = [
            'UserRoleSerializer',
            'FlockSerializer',
            'EggProductionSerializer',
            'SalesRecordSerializer',
            'ForecastSerializer',
        ]
        
        for serializer in serializer_classes:
            has_serializer = hasattr(serializers, serializer)
            if check_item(
                f"Serializer: {serializer}",
                has_serializer,
                "Available" if has_serializer else "Missing"
            ):
                checks_passed += 1
            else:
                checks_failed += 1
    except ImportError as e:
        check_item(
            f"Serializers import",
            False,
            f"Error: {str(e)}"
        )
        checks_failed += 1
    
    # 9. Utility Modules
    check_section("Utility Modules")
    
    try:
        from EggProduction import forecasting_service
        check_item(
            "forecasting_service module",
            True,
            "ForecastingService class available"
        )
        checks_passed += 1
    except ImportError:
        check_item(
            "forecasting_service module",
            False,
            "Module not found"
        )
        checks_failed += 1
    
    try:
        from EggProduction import data_importer
        check_item(
            "data_importer module",
            True,
            "DataImporter class available"
        )
        checks_passed += 1
    except ImportError:
        check_item(
            "data_importer module",
            False,
            "Module not found"
        )
        checks_failed += 1
    
    # 10. Management Commands
    check_section("Management Commands")
    
    management_commands = Path('EggProduction/management/commands')
    if management_commands.exists():
        run_forecasts = management_commands / 'run_forecasts.py'
        check_item(
            "run_forecasts command",
            run_forecasts.exists(),
            "Available for forecast generation"
        )
        if run_forecasts.exists():
            checks_passed += 1
        else:
            checks_failed += 1
    
    # 11. Test Suite
    check_section("Test Suite")
    
    tests_file = Path('EggProduction/tests.py')
    check_item(
        "tests.py module",
        tests_file.exists(),
        f"Size: {tests_file.stat().st_size} bytes"
    )
    if tests_file.exists():
        checks_passed += 1
    else:
        checks_failed += 1
    
    # 12. Documentation
    check_section("Documentation")
    
    docs = [
        ('README_DEPLOYMENT.md', 'Deployment guide'),
        ('QUICKSTART.md', 'Quick start guide'),
    ]
    
    for doc_file, description in docs:
        exists = Path(doc_file).exists()
        check_item(
            doc_file,
            exists,
            description
        )
        if exists:
            checks_passed += 1
        else:
            checks_failed += 1
    
    # Summary
    check_section("VERIFICATION SUMMARY")
    
    total_checks = checks_passed + checks_failed
    pass_rate = (checks_passed / total_checks * 100) if total_checks > 0 else 0
    
    print(f"\nTotal Checks: {total_checks}")
    print(f"Passed: {checks_passed} ✅")
    print(f"Failed: {checks_failed} ❌")
    print(f"Pass Rate: {pass_rate:.1f}%")
    
    if checks_failed == 0:
        print("\n🎉 All systems GO! Ready for deployment.")
        return 0
    else:
        print(f"\n⚠️  {checks_failed} issue(s) need attention.")
        print("\nTo fix issues:")
        print("  1. Install dependencies: pip install -r requirements.txt")
        print("  2. Run migrations: python manage.py migrate")
        print("  3. Create superuser: python manage.py createsuperuser")
        return 1

if __name__ == '__main__':
    try:
        exit_code = main()
    except Exception as e:
        print(f"\n❌ Error during verification: {str(e)}")
        import traceback
        traceback.print_exc()
        exit_code = 1
    
    sys.exit(exit_code)
