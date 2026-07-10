from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import datetime, timedelta


# User Profile Model (aligned with ERD)
class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('admin', 'Administrator'),
        ('staff', 'Staff'),
        ('manager', 'Manager'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    full_name = models.CharField(max_length=150, blank=True, null=True)
    assigned_house = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"
    
    class Meta:
        verbose_name_plural = "User Profiles"


# Flock Management Model (aligned with ERD)
class Flock(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('culled', 'Culled'),
    )
    
    house_no = models.IntegerField()
    breed_strain = models.CharField(max_length=100)
    date_started = models.DateField()
    initial_hen_count = models.IntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Flock House {self.house_no} - {self.breed_strain}"
    
    class Meta:
        ordering = ['-date_started']
        unique_together = ['house_no', 'date_started']


class ModelVersion(models.Model):
    MODEL_TYPE_CHOICES = (
        ('arima', 'ARIMA'),
        ('mlr', 'Multiple Linear Regression'),
        ('hybrid', 'Hybrid Model'),
        ('lstm', 'LSTM Neural Network'),
    )
    
    model_type = models.CharField(max_length=20, choices=MODEL_TYPE_CHOICES)
    trained_at = models.DateTimeField(auto_now_add=True)
    triggered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    r2_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    mae = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    rmse = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    aic_score = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    arima_order = models.CharField(max_length=20, null=True, blank=True, help_text="Format: (p,d,q)")
    pkl_path = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    training_rows = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.get_model_type_display()} - {self.trained_at.strftime('%Y-%m-%d %H:%M')}"
    
    class Meta:
        ordering = ['-trained_at']
        verbose_name_plural = "Model Versions"


# Production Logging (aligned with ERD - ProductionLog)
class ProductionLog(models.Model):
    flock = models.ForeignKey(Flock, on_delete=models.CASCADE, related_name='production_logs')
    production_date = models.DateField()
    age_weeks = models.IntegerField(validators=[MinValueValidator(0)])
    age_days = models.IntegerField(validators=[MinValueValidator(0)])
    live_hen_count = models.IntegerField(validators=[MinValueValidator(0)])
    daily_mortality = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    daily_culls = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    feed_consumed_bags = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    eggs_collected = models.IntegerField(validators=[MinValueValidator(0)])
    hen_day_production = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    hen_housed_production = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    feed_conversion_ratio = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True, help_text="Feed Conversion Ratio")
    management_remarks = models.TextField(blank=True, null=True)
    entered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='production_logs')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def log_date(self):
        return self.production_date

    @log_date.setter
    def log_date(self, value):
        self.production_date = value

    @property
    def hen_count(self):
        return self.live_hen_count

    @hen_count.setter
    def hen_count(self, value):
        self.live_hen_count = value

    @property
    def dead_count(self):
        return self.daily_mortality

    @dead_count.setter
    def dead_count(self, value):
        self.daily_mortality = value

    @property
    def culled_count(self):
        return self.daily_culls

    @culled_count.setter
    def culled_count(self, value):
        self.daily_culls = value

    @property
    def feed_bags(self):
        return self.feed_consumed_bags

    @feed_bags.setter
    def feed_bags(self, value):
        self.feed_consumed_bags = value

    @property
    def eggs_total(self):
        return self.eggs_collected

    @eggs_total.setter
    def eggs_total(self, value):
        self.eggs_collected = value

    @property
    def pct_hen_day(self):
        return self.hen_day_production

    @pct_hen_day.setter
    def pct_hen_day(self, value):
        self.hen_day_production = value

    @property
    def pct_hen_housed(self):
        return self.hen_housed_production

    @pct_hen_housed.setter
    def pct_hen_housed(self, value):
        self.hen_housed_production = value

    @property
    def fcr(self):
        return self.feed_conversion_ratio

    @fcr.setter
    def fcr(self, value):
        self.feed_conversion_ratio = value

    @property
    def remarks(self):
        return self.management_remarks

    @remarks.setter
    def remarks(self, value):
        self.management_remarks = value
    
    def __str__(self):
        return f"Production - Flock {self.flock.house_no} - {self.production_date}"
    
    class Meta:
        ordering = ['-production_date']
        unique_together = ('flock', 'production_date')


# Grading Logging (aligned with ERD - GradingLog)
class GradingLog(models.Model):
    flock = models.ForeignKey(Flock, on_delete=models.CASCADE, related_name='grading_logs')
    grading_date = models.DateField()
    age_weeks = models.IntegerField(validators=[MinValueValidator(0)])
    grade_jumbo = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    grade_extra_large = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    grade_large = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    grade_medium = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    grade_small = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    grade_pullets = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    grade_peewee = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    cracked_eggs = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    source = models.CharField(max_length=20, default='hardware')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def log_date(self):
        return self.grading_date

    @log_date.setter
    def log_date(self, value):
        self.grading_date = value

    @property
    def eggs_total(self):
        return self.grade_jumbo + self.grade_extra_large + self.grade_large + self.grade_medium + self.grade_small + self.grade_pullets + self.grade_peewee

    @eggs_total.setter
    def eggs_total(self, value):
        return None

    @property
    def eggs_aa(self):
        return self.grade_jumbo

    @eggs_aa.setter
    def eggs_aa(self, value):
        self.grade_jumbo = value

    @property
    def eggs_a(self):
        return self.grade_extra_large

    @eggs_a.setter
    def eggs_a(self, value):
        self.grade_extra_large = value

    @property
    def eggs_b(self):
        return self.grade_large

    @eggs_b.setter
    def eggs_b(self, value):
        self.grade_large = value

    @property
    def eggs_small(self):
        return self.grade_small

    @eggs_small.setter
    def eggs_small(self, value):
        self.grade_small = value

    @property
    def eggs_broken(self):
        return self.cracked_eggs

    @eggs_broken.setter
    def eggs_broken(self, value):
        self.cracked_eggs = value

    @property
    def eggs_decode(self):
        return self.grade_pullets

    @eggs_decode.setter
    def eggs_decode(self, value):
        self.grade_pullets = value

    @property
    def eggs_source(self):
        return self.source

    @eggs_source.setter
    def eggs_source(self, value):
        self.source = value
    
    def __str__(self):
        return f"Grading - Flock {self.flock.house_no} - {self.grading_date}"
    
    class Meta:
        ordering = ['-grading_date']
        unique_together = ('flock', 'grading_date')


# Sales Models (aligned with ERD)
class SalesTransaction(models.Model):
    flock = models.ForeignKey(Flock, on_delete=models.CASCADE, related_name='sales_transactions')
    sale_date = models.DateField()
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sales_transactions')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Sale Transaction - {self.sale_date} - Flock {self.flock.house_no}"
    
    class Meta:
        ordering = ['-sale_date']


class SalesItem(models.Model):
    transaction = models.ForeignKey(SalesTransaction, on_delete=models.CASCADE, related_name='items')
    grade = models.CharField(max_length=2, choices=[('AA', 'AA'), ('A', 'A'), ('B', 'B'), ('C', 'C')])
    quantity_trays = models.IntegerField(validators=[MinValueValidator(0)])
    price_per_tray = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    def save(self, *args, **kwargs):
        self.total_amount = self.quantity_trays * self.price_per_tray
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Grade {self.grade} - {self.quantity_trays} trays"
    
    class Meta:
        verbose_name_plural = "Sales Items"


# Forecasting Models (aligned with ERD)
class HarvestForecast(models.Model):
    flock = models.ForeignKey(Flock, on_delete=models.CASCADE, related_name='harvest_forecasts')
    model_version = models.ForeignKey(ModelVersion, on_delete=models.CASCADE, related_name='harvest_forecasts')
    forecast_date = models.DateField()
    grade = models.CharField(max_length=2, choices=[('AA', 'AA'), ('A', 'A'), ('B', 'B'), ('C', 'C')])
    predicted_qty = models.IntegerField(validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Harvest Forecast - Grade {self.grade} - {self.forecast_date}"
    
    class Meta:
        ordering = ['-forecast_date']
        unique_together = ('flock', 'model_version', 'forecast_date', 'grade')


class SalesForecast(models.Model):
    model_version = models.ForeignKey(ModelVersion, on_delete=models.CASCADE, related_name='sales_forecasts')
    forecast_date = models.DateField()
    grade = models.CharField(max_length=2, choices=[('AA', 'AA'), ('A', 'A'), ('B', 'B'), ('C', 'C')])
    predicted_trays = models.IntegerField(validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Sales Forecast - Grade {self.grade} - {self.forecast_date}"
    
    class Meta:
        ordering = ['-forecast_date']
        unique_together = ('model_version', 'forecast_date', 'grade')

