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
from .serializers import FlockSerializer, SalesTransactionSerializer, UserProfileSerializer


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
            grade='A',
            quantity_trays=10,
            price_per_tray=Decimal('220.00'),
        )

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
            grade='A',
            predicted_qty=1500,
        )
        sales = SalesForecast.objects.create(
            model_version=model_version,
            forecast_date=forecast_date,
            grade='A',
            predicted_trays=50,
        )

        self.assertEqual(harvest.predicted_qty, 1500)
        self.assertEqual(sales.predicted_trays, 50)


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

    def test_production_log_list_renders_with_filter(self):
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

        response = self.client.get(reverse('eggproduction:production-log-list'), {'flock_id': self.flock.id})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Egg Production')

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

    def test_sales_transaction_list_renders_total_amount(self):
        transaction = SalesTransaction.objects.create(
            flock=self.flock,
            sale_date=timezone.now().date(),
            recorded_by=self.user,
        )
        SalesItem.objects.create(
            transaction=transaction,
            grade='A',
            quantity_trays=2,
            price_per_tray=Decimal('200.00'),
        )

        response = self.client.get(reverse('eggproduction:sales-transaction-list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PHP 400.00')


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
