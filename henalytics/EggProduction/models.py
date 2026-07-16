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
    log_date = models.DateField()
    age_weeks = models.IntegerField(validators=[MinValueValidator(0)])
    age_days = models.IntegerField(validators=[MinValueValidator(0)])
    hen_count = models.IntegerField(validators=[MinValueValidator(0)])
    dead_count = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    culled_count = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    feed_bags = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    eggs_total = models.IntegerField(validators=[MinValueValidator(0)])
    pct_hen_day = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    pct_hen_housed = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    fcr = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True, help_text="Feed Conversion Ratio")
    remarks = models.TextField(blank=True, null=True)
    entered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='production_logs')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Production - Flock {self.flock.house_no} - {self.log_date}"
    
    class Meta:
        ordering = ['-log_date']
        unique_together = ('flock', 'log_date')


# Grading Logging (aligned with ERD - GradingLog)
class GradingLog(models.Model):
    flock = models.ForeignKey(Flock, on_delete=models.CASCADE, related_name='grading_logs')
    log_date = models.DateField()
    age_weeks = models.IntegerField(validators=[MinValueValidator(0)])
    eggs_total = models.IntegerField(validators=[MinValueValidator(0)])
    eggs_aa = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    eggs_a = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    eggs_b = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    eggs_small = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    eggs_broken = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    eggs_decode = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    eggs_source = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Grading - Flock {self.flock.house_no} - {self.log_date}"
    
    class Meta:
        ordering = ['-log_date']
        unique_together = ('flock', 'log_date')


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

    @property
    def total_amount(self):
        return sum(item.total_amount for item in self.items.all())
    
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

