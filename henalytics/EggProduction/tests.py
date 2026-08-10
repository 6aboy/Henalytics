from decimal import Decimal
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import (
    Flock,
    GradingLog,
    HarvestForecast,
    ModelVersion,
    ProductionLog,
    SalesForecast,
    SalesItem,
    SalesTransaction,
    UserProfile,
)
from .forecasting_service import ForecastingService
from .serializers import FlockSerializer, SalesTransactionSerializer, UserProfileSerializer
from .views import build_actual_vs_forecast_payload


def create_flock(**overrides):
    defaults = {
        'house_no': 1,
        'breed_strain': 'Lohmann Brown',
        'date_started': timezone.now().date(),
        'initial_hen_count': 1800,
        'status': 'active',
    }
    defaults.update(overrides)
    return Flock.objects.create(**defaults)


class UserProfileModelTest(TestCase):
    def test_create_user_profile(self):
        user = User.objects.create_user(username='staff', password='pass12345')

        profile = UserProfile.objects.create(user=user, role='staff', assigned_house='1')

        self.assertEqual(profile.role, 'staff')
        self.assertEqual(str(profile), 'staff - Staff')


class FlockModelTest(TestCase):
    def test_create_flock(self):
        flock = create_flock()

        self.assertEqual(flock.house_no, 1)
        self.assertEqual(flock.breed_strain, 'Lohmann Brown')
        self.assertEqual(str(flock), 'Flock House 1 - Lohmann Brown')

    def test_house_and_start_date_are_unique_together(self):
        started = timezone.now().date()
        create_flock(date_started=started)

        with self.assertRaises(Exception):
            create_flock(date_started=started)


class ProductionAndGradingLogModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='encoder', password='pass12345')
        self.flock = create_flock()

    def test_create_production_log(self):
        log = ProductionLog.objects.create(
            flock=self.flock,
            log_date=timezone.now().date(),
            age_weeks=30,
            age_days=210,
            hen_count=1780,
            dead_count=1,
            culled_count=0,
            feed_bags=12,
            eggs_total=1500,
            pct_hen_day=Decimal('84.27'),
            pct_hen_housed=Decimal('83.33'),
            fcr=Decimal('1.250'),
            entered_by=self.user,
        )

        self.assertEqual(log.eggs_total, 1500)
        self.assertEqual(log.entered_by, self.user)
        self.assertEqual(log.hen_count, 1799)
        self.assertEqual(log.pct_hen_day, Decimal('83.38'))
        self.assertEqual(log.pct_hen_housed, Decimal('83.33'))
        self.assertEqual(log.fcr, Decimal('6.667'))

    def test_production_log_recalculates_laying_percentages(self):
        log = ProductionLog.objects.create(
            flock=self.flock,
            log_date=timezone.now().date(),
            age_weeks=30,
            age_days=210,
            hen_count=1500,
            feed_bags=12,
            eggs_total=1200,
            pct_hen_day=Decimal('1.00'),
            pct_hen_housed=Decimal('1.00'),
            entered_by=self.user,
        )

        self.assertEqual(log.hen_count, 1800)
        self.assertEqual(log.pct_hen_day, Decimal('66.67'))
        self.assertEqual(log.pct_hen_housed, Decimal('66.67'))
        self.assertEqual(log.fcr, Decimal('8.333'))

    def test_production_log_recalculates_cumulative_live_hens(self):
        today = timezone.now().date()
        first = ProductionLog.objects.create(
            flock=self.flock,
            log_date=today,
            age_weeks=30,
            age_days=210,
            hen_count=0,
            dead_count=10,
            culled_count=5,
            feed_bags=12,
            eggs_total=1200,
            pct_hen_day=Decimal('0.00'),
            pct_hen_housed=Decimal('0.00'),
            entered_by=self.user,
        )
        second = ProductionLog.objects.create(
            flock=self.flock,
            log_date=today + timedelta(days=1),
            age_weeks=30,
            age_days=211,
            hen_count=0,
            dead_count=2,
            culled_count=0,
            feed_bags=12,
            eggs_total=1000,
            pct_hen_day=Decimal('0.00'),
            pct_hen_housed=Decimal('0.00'),
            entered_by=self.user,
        )

        first.refresh_from_db()
        second.refresh_from_db()

        self.assertEqual(first.hen_count, 1785)
        self.assertEqual(second.hen_count, 1783)
        self.assertEqual(second.pct_hen_day, Decimal('56.09'))
        self.assertEqual(second.fcr, Decimal('10.000'))

    def test_create_grading_log(self):
        log = GradingLog.objects.create(
            flock=self.flock,
            log_date=timezone.now().date(),
            age_weeks=30,
            eggs_total=1500,
            eggs_aa=100,
            eggs_a=800,
            eggs_b=500,
            eggs_small=80,
            eggs_broken=20,
        )

        self.assertEqual(log.eggs_a, 800)
        self.assertEqual(log.eggs_broken, 20)


class SalesModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cashier', password='pass12345')
        self.flock = create_flock()

    def test_sales_item_computes_total_amount(self):
        transaction = SalesTransaction.objects.create(
            flock=self.flock,
            sale_date=timezone.now().date(),
            recorded_by=self.user,
        )

        item = SalesItem.objects.create(
            transaction=transaction,
            grade='large',
            quantity_pieces=10,
            amount=Decimal('2200.00'),
        )

        self.assertEqual(item.unit_price, Decimal('220.00'))
        self.assertEqual(item.total_amount, Decimal('2200.00'))
        self.assertEqual(transaction.total_amount, Decimal('2200.00'))


class ForecastModelTest(TestCase):
    def test_create_harvest_and_sales_forecasts(self):
        flock = create_flock()
        user = User.objects.create_user(username='admin', password='pass12345')
        model_version = ModelVersion.objects.create(model_type='mlr', triggered_by=user, training_rows=30)
        forecast_date = timezone.now().date() + timedelta(days=1)

        harvest = HarvestForecast.objects.create(
            flock=flock,
            model_version=model_version,
            forecast_date=forecast_date,
            grade='large',
            predicted_qty=1500,
        )
        sales = SalesForecast.objects.create(
            model_version=model_version,
            forecast_date=forecast_date,
            grade='large',
            predicted_trays=50,
        )

        self.assertEqual(harvest.predicted_qty, 1500)
        self.assertEqual(sales.predicted_trays, 50)

    def test_arima_service_generates_database_forecasts(self):
        flock = create_flock(date_started=timezone.now().date() - timedelta(days=20))
        user = User.objects.create_user(username='forecaster', password='pass12345')
        start_date = timezone.now().date() - timedelta(days=14)

        for day in range(12):
            log_date = start_date + timedelta(days=day)
            ProductionLog.objects.create(
                flock=flock,
                log_date=log_date,
                age_weeks=30,
                age_days=210 + day,
                hen_count=1780,
                feed_bags=12,
                eggs_total=1400 + day,
                pct_hen_day=Decimal('78.00'),
                pct_hen_housed=Decimal('77.00'),
                entered_by=user,
            )
            GradingLog.objects.create(
                flock=flock,
                log_date=log_date,
                age_weeks=30,
                eggs_total=1400 + day,
                eggs_a=700 + day,
            )
            transaction = SalesTransaction.objects.create(
                flock=flock,
                sale_date=log_date,
                recorded_by=user,
            )
            SalesItem.objects.create(
                transaction=transaction,
                grade='large',
                quantity_pieces=100,
                amount=Decimal(1000 + day),
            )

        egg_result = ForecastingService.generate_egg_forecasts(flock, periods=3, user=user, include_sizes=True)
        sales_result = ForecastingService.generate_sales_forecasts(periods=3, user=user, include_sizes=True)

        self.assertTrue(egg_result['success'])
        self.assertTrue(sales_result['success'])
        self.assertTrue(HarvestForecast.objects.filter(grade='overall').exists())
        self.assertFalse(HarvestForecast.objects.exclude(grade='overall').exists())
        self.assertTrue(SalesForecast.objects.filter(grade='overall', predicted_amount__gt=0).exists())
        self.assertTrue(SalesForecast.objects.filter(grade='large', predicted_amount__gt=0).exists())

    def test_forecast_evaluation_compares_against_baseline(self):
        flock = create_flock(date_started=timezone.now().date() - timedelta(days=40))
        user = User.objects.create_user(username='evaluser', password='pass12345')
        start_date = timezone.now().date() - timedelta(days=30)

        for day in range(25):
            log_date = start_date + timedelta(days=day)
            ProductionLog.objects.create(
                flock=flock,
                log_date=log_date,
                age_weeks=30,
                age_days=210 + day,
                hen_count=1780,
                feed_bags=12,
                eggs_total=1400 + (day % 7) * 10,
                pct_hen_day=Decimal('78.00'),
                pct_hen_housed=Decimal('77.00'),
                entered_by=user,
            )

        results = ForecastingService.evaluate_egg_forecasts(flock, include_sizes=False)

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]['success'])
        self.assertIn(results[0]['winner'], ['ARIMA', 'Baseline'])
        self.assertIn('rmse', results[0]['arima'])
        self.assertIn('rmse', results[0]['baseline'])

    def test_missing_forecast_dates_are_interpolated_not_zero_filled(self):
        start_date = timezone.now().date() - timedelta(days=20)
        rows = []
        for day in range(11):
            if day == 5:
                continue
            rows.append({
                'date': start_date + timedelta(days=day),
                'value': 1000 + (day * 10),
            })

        prepared = ForecastingService._prepare_daily_dataset(rows)
        missing_date = start_date + timedelta(days=5)

        self.assertIsNotNone(prepared)
        self.assertEqual(prepared['series'].loc[str(missing_date)], 1050)
        self.assertNotEqual(prepared['series'].loc[str(missing_date)], 0)

    def test_egg_sarimax_features_match_notebook_predictors(self):
        self.assertEqual(
            ForecastingService.EGG_FEATURE_FIELDS,
            ('hen_count', 'dead_count', 'culled_count', 'feed_bags'),
        )
        self.assertEqual(ForecastingService.SEASONAL_PERIOD, 7)

        start_date = timezone.now().date() - timedelta(days=20)
        rows = []
        for day in range(12):
            rows.append({
                'date': start_date + timedelta(days=day),
                'value': 1300 + day,
                'hen_count': 1780 - day,
                'dead_count': day % 2,
                'culled_count': day % 3,
                'feed_bags': 12,
                'age_weeks': 30,
                'age_days': 210 + day,
                'pct_hen_day': Decimal('78.00'),
                'pct_hen_housed': Decimal('77.00'),
            })

        prepared = ForecastingService._prepare_daily_dataset(rows, use_exog=True)

        self.assertIsNotNone(prepared)
        self.assertEqual(
            list(prepared['exog'].columns),
            ['hen_count', 'dead_count', 'culled_count', 'feed_bags'],
        )


class APIAuthenticationTest(APITestCase):
    def test_api_requires_authentication(self):
        response = self.client.get(reverse('eggproduction:api-flock-list'))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authenticated_user_can_list_flocks(self):
        user = User.objects.create_user(username='apiuser', password='pass12345')
        create_flock()
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse('eggproduction:api-flock-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_active_flocks_action(self):
        user = User.objects.create_user(username='apiuser', password='pass12345')
        create_flock(status='active')
        create_flock(house_no=2, status='inactive')
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse('eggproduction:api-flock-active'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class TemplateRenderTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='staffer', password='pass12345', is_staff=True)
        self.flock = create_flock()
        self.client.force_login(self.user)

    def test_flock_list_uses_correct_table_columns(self):
        ProductionLog.objects.create(
            flock=self.flock,
            log_date=self.flock.date_started + timedelta(days=30),
            age_weeks=0,
            age_days=0,
            hen_count=1780,
            dead_count=2,
            culled_count=3,
            feed_bags=12,
            eggs_total=1500,
            pct_hen_day=Decimal('0.00'),
            pct_hen_housed=Decimal('0.00'),
            entered_by=self.user,
        )

        response = self.client.get(reverse('eggproduction:flock-list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Flock Management')
        self.assertContains(response, '<th>Age</th>', html=True)
        self.assertContains(response, '4w 30d')
        self.assertContains(response, '3 | 2')
        self.assertContains(response, '12')
        self.assertNotContains(response, 'Lohmann Brown')

    def test_production_log_list_renders_with_filter(self):
        other_flock = create_flock(house_no=2, date_started=timezone.now().date() - timedelta(days=1))
        ProductionLog.objects.create(
            flock=self.flock,
            log_date=timezone.now().date(),
            age_weeks=30,
            age_days=210,
            hen_count=1780,
            feed_bags=12,
            eggs_total=1500,
            pct_hen_day=Decimal('84.27'),
            pct_hen_housed=Decimal('83.33'),
            entered_by=self.user,
        )
        ProductionLog.objects.create(
            flock=other_flock,
            log_date=timezone.now().date(),
            age_weeks=30,
            age_days=210,
            hen_count=1700,
            feed_bags=10,
            eggs_total=900,
            pct_hen_day=Decimal('52.94'),
            pct_hen_housed=Decimal('50.00'),
            entered_by=self.user,
        )

        response = self.client.get(reverse('eggproduction:production-log-list'), {'flock_id': self.flock.id})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Egg Production')
        self.assertContains(response, 'class="table table-striped table-hover prototype-table js-data-table"')
        self.assertContains(response, 'data-export-enabled="false"')
        self.assertContains(response, 'data-total-column="1"')
        self.assertContains(response, 'data-swal-filter')
        self.assertContains(response, 'data-swal-delete-link')
        self.assertEqual(list(response.context['production_logs'])[0].flock_id, self.flock.id)

    def test_production_log_today_filter_uses_local_date(self):
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        ProductionLog.objects.create(
            flock=self.flock,
            log_date=today,
            age_weeks=30,
            age_days=210,
            hen_count=1780,
            feed_bags=12,
            eggs_total=1500,
            pct_hen_day=Decimal('84.27'),
            pct_hen_housed=Decimal('83.33'),
            entered_by=self.user,
        )
        ProductionLog.objects.create(
            flock=self.flock,
            log_date=yesterday,
            age_weeks=30,
            age_days=209,
            hen_count=1780,
            feed_bags=12,
            eggs_total=900,
            pct_hen_day=Decimal('50.56'),
            pct_hen_housed=Decimal('50.00'),
            entered_by=self.user,
        )

        response = self.client.get(reverse('eggproduction:production-log-list'), {'period': 'today'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, today.strftime('%b %d, %Y'))
        self.assertContains(response, '<strong>1,500</strong>')
        self.assertNotContains(response, yesterday.strftime('%b %d, %Y'))

    def test_dashboard_period_cards_total_eggs(self):
        ProductionLog.objects.create(
            flock=self.flock,
            log_date=timezone.now().date(),
            age_weeks=30,
            age_days=210,
            hen_count=1780,
            feed_bags=12,
            eggs_total=1234,
            pct_hen_day=Decimal('69.33'),
            pct_hen_housed=Decimal('68.56'),
            entered_by=self.user,
        )

        response = self.client.get(reverse('eggproduction:dashboard'), {'period': 'all'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['period_egg_total'], 1234)
        self.assertContains(response, 'Total Eggs')
        self.assertContains(response, 'Production Notebook')
        self.assertContains(response, 'dashboardNotebookChart')
        self.assertContains(response, 'notebook-bookmark')
        self.assertIn('dashboard_charts_payload_json', response.context)

    def test_dashboard_defaults_to_recent_data_and_separate_loss_totals(self):
        today = timezone.localdate()
        rows = [
            (today - timedelta(days=5), 1, 0),
            (today - timedelta(days=20), 1, 1),
            (today - timedelta(days=45), 2, 1),
        ]
        for log_date, dead, culled in rows:
            ProductionLog.objects.create(
                flock=self.flock,
                log_date=log_date,
                age_weeks=30,
                age_days=210,
                hen_count=1780,
                dead_count=dead,
                culled_count=culled,
                feed_bags=12,
                eggs_total=1000,
                pct_hen_day=Decimal('56.18'),
                pct_hen_housed=Decimal('55.56'),
                entered_by=self.user,
            )

        response = self.client.get(reverse('eggproduction:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['dashboard_period'], 'last_30')
        self.assertEqual(response.context['dashboard_period_label'], 'Last 30 Days')
        self.assertEqual(response.context['period_egg_total'], 2000)
        self.assertEqual(response.context['recent_losses_7d'], 1)
        self.assertEqual(response.context['recent_losses_30d'], 3)
        self.assertEqual(response.context['recent_losses_60d'], 6)

    def test_primary_detail_pages_render_real_values(self):
        log = ProductionLog.objects.create(
            flock=self.flock,
            log_date=timezone.now().date(),
            age_weeks=30,
            age_days=210,
            hen_count=1780,
            feed_bags=12,
            eggs_total=1500,
            pct_hen_day=Decimal('84.27'),
            pct_hen_housed=Decimal('83.33'),
            entered_by=self.user,
        )
        grading = GradingLog.objects.create(
            flock=self.flock,
            log_date=timezone.now().date(),
            age_weeks=30,
            eggs_total=1500,
            eggs_aa=100,
            eggs_a=900,
            eggs_b=400,
            eggs_small=100,
        )
        transaction = SalesTransaction.objects.create(
            flock=self.flock,
            sale_date=timezone.now().date(),
            recorded_by=self.user,
        )

        urls = [
            reverse('eggproduction:production-log-detail', args=[log.pk]),
            reverse('eggproduction:grading-log-detail', args=[grading.pk]),
            reverse('eggproduction:sales-transaction-detail', args=[transaction.pk]),
            reverse('eggproduction:flock-detail', args=[self.flock.pk]),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'detail-panel')
            self.assertNotContains(response, 'flock_id')
            self.assertNotContains(response, '{{')

    def test_admin_tables_enable_datatable_exports(self):
        admin = User.objects.create_superuser(
            username='adminuser',
            email='admin@example.com',
            password='pass12345',
        )
        self.client.force_login(admin)

        response = self.client.get(reverse('eggproduction:production-log-list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-export-enabled="true"')
        self.assertContains(response, 'class="no-export">Actions</th>')

    def test_staff_cannot_access_analytics_pages(self):
        urls = [
            reverse('eggproduction:experimental-forecasting'),
            reverse('eggproduction:harvest-forecast-list'),
            reverse('eggproduction:sales-forecast-list'),
            reverse('eggproduction:model-version-list'),
        ]

        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)

    def test_staff_sidebar_hides_analytics_link(self):
        response = self.client.get(reverse('eggproduction:production-log-list'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Analytics')
        self.assertNotContains(response, 'Forecasting')
        self.assertNotContains(response, reverse('eggproduction:experimental-forecasting'))
        self.assertNotContains(response, reverse('eggproduction:harvest-forecast-list'))

    def test_sidebar_account_uses_direct_logout_button(self):
        response = self.client.get(reverse('eggproduction:production-log-list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'account-summary')
        self.assertContains(response, 'account-logout-button')
        self.assertContains(response, 'sign-out.svg')
        self.assertContains(response, 'data-swal-logout')
        self.assertNotContains(response, 'account-dropdown')
        self.assertNotContains(response, 'data-bs-toggle="dropdown"')

    def test_admin_can_access_forecast_pages_without_analytics_nav(self):
        admin = User.objects.create_superuser(
            username='analyticsadmin',
            email='analytics@example.com',
            password='pass12345',
        )
        self.client.force_login(admin)

        response = self.client.get(reverse('eggproduction:harvest-forecast-list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Forecasting')
        self.assertNotContains(response, '<span>Analytics</span>', html=True)
        self.assertContains(response, 'dashboard-tabs')
        self.assertContains(response, 'Egg Forecasts')
        self.assertContains(response, 'Sales Forecasts')

    def test_sales_forecast_page_opens_with_forecast_tabs(self):
        admin = User.objects.create_superuser(
            username='salesforecastadmin',
            email='salesforecast@example.com',
            password='pass12345',
        )
        self.client.force_login(admin)

        response = self.client.get(reverse('eggproduction:sales-forecast-list'), {'range': 'month', 'scope': 'overall'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Forecast Setup')
        self.assertContains(response, 'Forecasting')
        self.assertNotContains(response, '<span>Analytics</span>', html=True)
        self.assertContains(response, 'dashboard-tabs')
        self.assertContains(response, 'Egg Forecasts')
        self.assertContains(response, 'Sales Forecasts')

    def test_admin_can_access_database_forecasting_page(self):
        admin = User.objects.create_superuser(
            username='forecastadmin',
            email='forecast@example.com',
            password='pass12345',
        )
        self.client.force_login(admin)

        response = self.client.get(reverse('eggproduction:experimental-forecasting'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Overall Egg Forecasting')
        self.assertContains(response, 'notebook-style SARIMAX forecasts')
        self.assertContains(response, 'All active flocks')
        self.assertContains(response, 'Generate Forecast')
        self.assertContains(response, 'value="overall"')
        self.assertNotContains(response, 'Overall and per size')
        self.assertContains(response, 'Chart Reading')
        self.assertContains(response, 'Forecast Direction')
        self.assertContains(response, 'Expected Average')
        self.assertContains(response, 'data-swal-forecast-run')
        self.assertContains(response, 'do not close the system')
        self.assertContains(response, 'cdn.plot.ly')
        self.assertContains(response, 'Plotly.newPlot')
        self.assertContains(response, 'scrollZoom: true')
        self.assertContains(response, "dragmode: 'pan'")
        self.assertContains(response, 'showspikes: true')
        self.assertContains(response, "tickformat: '%b %d'")
        self.assertContains(response, "standoff: 18")
        self.assertNotContains(response, 'rangeselector')
        self.assertContains(response, 'payload.x_max')

    def test_actual_vs_forecast_payload_includes_chart_bounds(self):
        today = timezone.localdate()
        payload = build_actual_vs_forecast_payload(
            [{'log_date': today, 'total': 1000}],
            [{'forecast_date': today + timedelta(days=1), 'total': 1010, 'lower': 950, 'upper': 1070}],
        )

        self.assertEqual(payload['x_min'], today.strftime('%b %d, %Y'))
        self.assertEqual(payload['x_max'], (today + timedelta(days=1)).strftime('%b %d, %Y'))
        self.assertEqual(payload['x_min_iso'], today.isoformat())
        self.assertEqual(payload['x_max_iso'], (today + timedelta(days=1)).isoformat())

    def test_production_log_create_auto_calculates_percentages(self):
        response = self.client.post(reverse('eggproduction:production-log-create'), {
            'flock': self.flock.id,
            'log_date': timezone.now().date(),
            'age_weeks': 30,
            'age_days': 210,
            'dead_count': 0,
            'culled_count': 0,
            'feed_bags': 12,
            'eggs_total': 1200,
            'pct_hen_day': '',
            'pct_hen_housed': '',
            'fcr': '',
            'remarks': '',
        })

        self.assertEqual(response.status_code, 302)
        log = ProductionLog.objects.get(flock=self.flock, log_date=timezone.now().date())
        self.assertEqual(log.hen_count, 1800)
        self.assertEqual(log.pct_hen_day, Decimal('66.67'))
        self.assertEqual(log.pct_hen_housed, Decimal('66.67'))
        self.assertEqual(log.fcr, Decimal('8.333'))
        queued_messages = list(response.wsgi_request._messages)
        self.assertTrue(any('swal' in message.tags for message in queued_messages))

        list_response = self.client.get(reverse('eggproduction:production-log-list'))
        self.assertContains(list_response, 'alert-success swal')
        self.assertContains(list_response, 'Egg production record created successfully.')

    def test_production_log_create_auto_calculates_flock_age(self):
        log_date = timezone.now().date()
        self.flock.date_started = log_date - timedelta(days=24)
        self.flock.save()

        response = self.client.post(reverse('eggproduction:production-log-create'), {
            'flock': self.flock.id,
            'log_date': log_date,
            'dead_count': 0,
            'culled_count': 0,
            'feed_bags': 12,
            'eggs_total': 1200,
            'pct_hen_day': '',
            'pct_hen_housed': '',
            'fcr': '',
            'remarks': '',
        })

        self.assertEqual(response.status_code, 302)
        log = ProductionLog.objects.get(flock=self.flock, log_date=log_date)
        self.assertEqual(log.age_days, 24)
        self.assertEqual(log.age_weeks, 3)

    def test_production_log_can_be_recreated_after_delete_with_stale_metric_values(self):
        log_date = timezone.localdate()
        payload = {
            'flock': self.flock.id,
            'log_date': log_date,
            'dead_count': 0,
            'culled_count': 0,
            'feed_bags': 12,
            'eggs_total': 1200,
            'pct_hen_day': '999.99',
            'pct_hen_housed': '999.99',
            'fcr': '999.999',
            'remarks': '',
        }

        first_response = self.client.post(reverse('eggproduction:production-log-create'), payload)
        self.assertEqual(first_response.status_code, 302)
        first_log = ProductionLog.objects.get(flock=self.flock, log_date=log_date)

        delete_response = self.client.post(reverse('eggproduction:production-log-delete', args=[first_log.pk]))
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(ProductionLog.objects.filter(flock=self.flock, log_date=log_date).exists())

        second_response = self.client.post(reverse('eggproduction:production-log-create'), payload)
        self.assertEqual(second_response.status_code, 302)
        second_log = ProductionLog.objects.get(flock=self.flock, log_date=log_date)
        self.assertEqual(second_log.pct_hen_day, Decimal('66.67'))
        self.assertEqual(second_log.pct_hen_housed, Decimal('66.67'))
        self.assertEqual(second_log.fcr, Decimal('8.333'))

    def test_production_log_rejects_future_log_date(self):
        future_date = timezone.localdate() + timedelta(days=1)

        response = self.client.post(reverse('eggproduction:production-log-create'), {
            'flock': self.flock.id,
            'log_date': future_date,
            'dead_count': 0,
            'culled_count': 0,
            'feed_bags': 12,
            'eggs_total': 1200,
            'pct_hen_day': '',
            'pct_hen_housed': '',
            'fcr': '',
            'remarks': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Log date cannot be in the future.')
        self.assertFalse(ProductionLog.objects.filter(flock=self.flock, log_date=future_date).exists())

    def test_production_log_rejects_date_before_flock_start(self):
        invalid_date = self.flock.date_started - timedelta(days=1)

        response = self.client.post(reverse('eggproduction:production-log-create'), {
            'flock': self.flock.id,
            'log_date': invalid_date,
            'dead_count': 0,
            'culled_count': 0,
            'feed_bags': 12,
            'eggs_total': 1200,
            'pct_hen_day': '',
            'pct_hen_housed': '',
            'fcr': '',
            'remarks': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Log date cannot be earlier than the flock start date.')
        self.assertFalse(ProductionLog.objects.filter(flock=self.flock, log_date=invalid_date).exists())

    def test_sales_transaction_list_renders_total_amount(self):
        transaction = SalesTransaction.objects.create(
            flock=self.flock,
            sale_date=timezone.now().date(),
            recorded_by=self.user,
        )
        SalesItem.objects.create(
            transaction=transaction,
            grade='large',
            quantity_pieces=60,
            amount=Decimal('400.00'),
        )

        response = self.client.get(reverse('eggproduction:sales-transaction-list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '₱ 400.00')

    def test_sales_transaction_create_saves_item_rows(self):
        response = self.client.post(reverse('eggproduction:sales-transaction-create'), {
            'flock': self.flock.id,
            'sale_date': timezone.now().date(),
            'notes': 'Counter sale',
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '1',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-grade': 'large',
            'items-0-quantity_pieces': '90',
            'items-0-price_per_piece': '7.00',
        })

        transaction = SalesTransaction.objects.get(notes='Counter sale')
        self.assertRedirects(
            response,
            reverse('eggproduction:sales-transaction-detail', args=[transaction.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(transaction.items.count(), 1)
        self.assertEqual(transaction.total_amount, Decimal('630.00'))
        self.assertEqual(transaction.total_pieces, 90)
        self.assertEqual(transaction.items.first().unit_price, Decimal('7.00'))

        detail_response = self.client.get(reverse('eggproduction:sales-transaction-detail', args=[transaction.pk]))
        self.assertContains(detail_response, 'alert-success swal')
        self.assertContains(detail_response, 'Sales transaction created successfully.')

    def test_sales_transaction_missing_size_shows_red_field_error(self):
        response = self.client.post(reverse('eggproduction:sales-transaction-create'), {
            'flock': self.flock.id,
            'sale_date': timezone.now().date(),
            'notes': 'Missing size',
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '1',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-grade': '',
            'items-0-quantity_pieces': '90',
            'items-0-price_per_piece': '7.00',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'has-error')
        self.assertContains(response, 'form-error')
        self.assertContains(response, 'This field is required.')


class SerializerTest(TestCase):
    def test_current_serializers_match_current_models(self):
        user = User.objects.create_user(username='serial', email='serial@example.com', password='pass12345')
        profile = UserProfile.objects.create(user=user, role='admin')
        flock = create_flock()
        transaction = SalesTransaction.objects.create(
            flock=flock,
            sale_date=timezone.now().date(),
            recorded_by=user,
        )

        self.assertEqual(UserProfileSerializer(profile).data['username'], 'serial')
        self.assertEqual(FlockSerializer(flock).data['breed_strain'], 'Lohmann Brown')
        self.assertEqual(SalesTransactionSerializer(transaction).data['total_amount'], 0)
