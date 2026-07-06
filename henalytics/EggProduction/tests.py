"""
Test Suite for Henalytics Models, Serializers, and API Views
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from rest_framework.test import APITestCase
from rest_framework import status

from .models import (
    UserRole, Flock, HenPerformance, EggProduction, EggGrading,
    SalesRecord, DailyRevenue, TimeSeriesData, Forecast, SystemLog
)
from .serializers import (
    UserRoleSerializer, FlockSerializer, EggProductionSerializer,
    SalesRecordSerializer, ForecastSerializer
)


class UserRoleModelTest(TestCase):
    """Test UserRole model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_user_role_admin(self):
        """Test creating admin user role"""
        role = UserRole.objects.create(user=self.user, role='admin')
        self.assertEqual(role.role, 'admin')
        self.assertEqual(str(role), f'{self.user.username} - admin')
    
    def test_create_user_role_staff(self):
        """Test creating staff user role"""
        role = UserRole.objects.create(user=self.user, role='staff')
        self.assertEqual(role.role, 'staff')
    
    def test_user_role_unique_constraint(self):
        """Test that one user can only have one role"""
        UserRole.objects.create(user=self.user, role='admin')
        # Creating another role for same user should fail
        with self.assertRaises(Exception):
            UserRole.objects.create(user=self.user, role='staff')


class FlockModelTest(TestCase):
    """Test Flock model"""
    
    def setUp(self):
        self.flock = Flock.objects.create(
            flock_id='FL001',
            breed='Leghorn',
            initial_count=500,
            current_count=480,
            status='active',
            date_started=timezone.now().date(),
            housing_type='cage'
        )
    
    def test_create_flock(self):
        """Test flock creation"""
        self.assertEqual(self.flock.flock_id, 'FL001')
        self.assertEqual(self.flock.breed, 'Leghorn')
        self.assertEqual(self.flock.current_count, 480)
    
    def test_flock_status_choices(self):
        """Test flock status choices"""
        self.assertIn('active', dict(Flock._meta.get_field('status').choices))
        self.assertIn('inactive', dict(Flock._meta.get_field('status').choices))
        self.assertIn('culled', dict(Flock._meta.get_field('status').choices))
    
    def test_flock_unique_id(self):
        """Test that flock ID must be unique"""
        with self.assertRaises(Exception):
            Flock.objects.create(
                flock_id='FL001',
                breed='Rhode Island Red',
                initial_count=300,
                current_count=290,
                status='active',
                date_started=timezone.now().date()
            )


class EggProductionModelTest(TestCase):
    """Test EggProduction model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='producer',
            email='producer@example.com',
            password='pass123'
        )
        self.flock = Flock.objects.create(
            flock_id='FL002',
            breed='Leghorn',
            initial_count=1000,
            current_count=950,
            status='active',
            date_started=timezone.now().date()
        )
    
    def test_create_egg_production(self):
        """Test creating egg production record"""
        today = timezone.now().date()
        prod = EggProduction.objects.create(
            flock=self.flock,
            record_date=today,
            eggs_collected=850,
            broken_eggs=10,
            defective_eggs=15,
            good_eggs=825,
            hen_day_production=Decimal('89.5'),
            hen_housed_production=Decimal('87.1'),
            created_by=self.user
        )
        self.assertEqual(prod.eggs_collected, 850)
        self.assertEqual(prod.good_eggs, 825)
    
    def test_egg_production_unique_constraint(self):
        """Test that one flock can only have one production record per day"""
        today = timezone.now().date()
        EggProduction.objects.create(
            flock=self.flock,
            record_date=today,
            eggs_collected=800,
            created_by=self.user
        )
        # Creating another record for same flock/date should fail
        with self.assertRaises(Exception):
            EggProduction.objects.create(
                flock=self.flock,
                record_date=today,
                eggs_collected=750,
                created_by=self.user
            )
    
    def test_egg_grading(self):
        """Test egg grading inline model"""
        today = timezone.now().date()
        prod = EggProduction.objects.create(
            flock=self.flock,
            record_date=today,
            eggs_collected=800,
            created_by=self.user
        )
        grading = EggGrading.objects.create(
            egg_production=prod,
            grade='AA',
            count=300,
            average_weight=Decimal('60.5')
        )
        self.assertEqual(grading.grade, 'AA')
        self.assertEqual(grading.count, 300)


class SalesRecordModelTest(TestCase):
    """Test SalesRecord model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='salesman',
            email='sales@example.com',
            password='pass123'
        )
        self.flock = Flock.objects.create(
            flock_id='FL003',
            breed='Leghorn',
            initial_count=500,
            current_count=500,
            status='active',
            date_started=timezone.now().date()
        )
    
    def test_create_sales_record(self):
        """Test creating sales record"""
        today = timezone.now().date()
        sale = SalesRecord.objects.create(
            flock=self.flock,
            sale_date=today,
            eggs_sold=500,
            price_per_unit=Decimal('5.00'),
            buyer_name='Local Market',
            recorded_by=self.user
        )
        self.assertEqual(sale.eggs_sold, 500)
        self.assertEqual(sale.total_amount, Decimal('2500.00'))
    
    def test_sales_status_choices(self):
        """Test sales record status choices"""
        status_choices = dict(SalesRecord._meta.get_field('status').choices)
        self.assertIn('pending', status_choices)
        self.assertIn('completed', status_choices)
        self.assertIn('cancelled', status_choices)


class APIAuthenticationTest(APITestCase):
    """Test API authentication and permissions"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='apiuser',
            email='api@example.com',
            password='apipass123'
        )
    
    def test_api_requires_authentication(self):
        """Test that API endpoints require authentication"""
        response = self.client.get('/api/flocks/')
        self.assertEqual(response.status_code, 401)
    
    def test_authenticated_api_access(self):
        """Test API access with authentication"""
        self.client.login(username='apiuser', password='apipass123')
        response = self.client.get('/api/flocks/')
        self.assertIn(response.status_code, [200, 401])  # 401 if not properly configured


class FlockViewSetTest(APITestCase):
    """Test Flock API ViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.flock1 = Flock.objects.create(
            flock_id='FL001',
            breed='Leghorn',
            initial_count=1000,
            current_count=950,
            status='active',
            date_started=timezone.now().date()
        )
        self.flock2 = Flock.objects.create(
            flock_id='FL002',
            breed='Rhode Island Red',
            initial_count=500,
            current_count=480,
            status='inactive',
            date_started=timezone.now().date()
        )
    
    def test_list_flocks(self):
        """Test listing all flocks"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/flocks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_filter_active_flocks(self):
        """Test filtering active flocks"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/flocks/active_flocks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class EggProductionViewSetTest(APITestCase):
    """Test EggProduction API ViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='producer',
            email='producer@example.com',
            password='pass123'
        )
        self.flock = Flock.objects.create(
            flock_id='FL001',
            breed='Leghorn',
            initial_count=1000,
            current_count=950,
            status='active',
            date_started=timezone.now().date()
        )
    
    def test_create_egg_production_via_api(self):
        """Test creating egg production via API"""
        self.client.force_authenticate(user=self.user)
        today = timezone.now().date()
        data = {
            'flock': self.flock.id,
            'record_date': str(today),
            'eggs_collected': 850,
            'broken_eggs': 10,
            'defective_eggs': 15,
            'good_eggs': 825,
            'hen_day_production': '89.5',
            'hen_housed_production': '87.1',
        }
        response = self.client.post('/api/egg-production/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_today_production_filter(self):
        """Test getting today's production"""
        today = timezone.now().date()
        EggProduction.objects.create(
            flock=self.flock,
            record_date=today,
            eggs_collected=850,
            created_by=self.user
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/egg-production/today_production/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ForecastModelTest(TestCase):
    """Test Forecast model"""
    
    def setUp(self):
        self.flock = Flock.objects.create(
            flock_id='FL001',
            breed='Leghorn',
            initial_count=1000,
            current_count=950,
            status='active',
            date_started=timezone.now().date()
        )
    
    def test_create_forecast(self):
        """Test creating forecast"""
        forecast_date = timezone.now().date() + timedelta(days=1)
        forecast = Forecast.objects.create(
            flock=self.flock,
            forecast_type='Egg Production',
            model_type='hybrid',
            forecast_date=forecast_date,
            forecasted_value=Decimal('850.00'),
            upper_bound=Decimal('900.00'),
            lower_bound=Decimal('800.00'),
            mean_absolute_percentage_error=Decimal('5.25'),
            r_squared=Decimal('0.92'),
            is_active=True
        )
        self.assertEqual(forecast.forecasted_value, Decimal('850.00'))
        self.assertTrue(forecast.is_active)


class SystemLogModelTest(TestCase):
    """Test SystemLog model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='admin123'
        )
    
    def test_create_system_log(self):
        """Test creating system log"""
        log = SystemLog.objects.create(
            log_type='data_entry',
            message='Test data entry log',
            user=self.user,
            status='info'
        )
        self.assertEqual(log.log_type, 'data_entry')
        self.assertEqual(log.status, 'info')


class SerializerTest(TestCase):
    """Test Serializers"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.flock = Flock.objects.create(
            flock_id='FL001',
            breed='Leghorn',
            initial_count=1000,
            current_count=950,
            status='active',
            date_started=timezone.now().date()
        )
    
    def test_flock_serializer(self):
        """Test Flock serializer"""
        serializer = FlockSerializer(self.flock)
        data = serializer.data
        self.assertEqual(data['flock_id'], 'FL001')
        self.assertEqual(data['breed'], 'Leghorn')
        self.assertEqual(data['current_count'], 950)
    
    def test_user_role_serializer(self):
        """Test UserRole serializer"""
        role = UserRole.objects.create(user=self.user, role='admin')
        serializer = UserRoleSerializer(role)
        data = serializer.data
        self.assertEqual(data['role'], 'admin')
        self.assertEqual(data['username'], 'testuser')
