from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from decimal import Decimal, ROUND_HALF_UP
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

    def save(self, *args, **kwargs):
        old_initial_hen_count = None
        if self.pk:
            old_initial_hen_count = (
                Flock.objects.filter(pk=self.pk)
                .values_list('initial_hen_count', flat=True)
                .first()
            )

        super().save(*args, **kwargs)

        if old_initial_hen_count is not None and old_initial_hen_count != self.initial_hen_count:
            ProductionLog.recalculate_flock_snapshots(self.pk)
    
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

    def update_live_hen_count(self):
        previous_losses = ProductionLog.objects.filter(
            flock=self.flock,
            log_date__lt=self.log_date,
        )
        if self.pk:
            previous_losses = previous_losses.exclude(pk=self.pk)

        totals = previous_losses.aggregate(
            dead=models.Sum('dead_count'),
            culled=models.Sum('culled_count'),
        )
        previous_dead = totals['dead'] or 0
        previous_culled = totals['culled'] or 0
        current_losses = (self.dead_count or 0) + (self.culled_count or 0)

        self.hen_count = max(
            (self.flock.initial_hen_count if self.flock_id and self.flock else 0)
            - previous_dead
            - previous_culled
            - current_losses,
            0,
        )

    def update_laying_percentages(self):
        self.pct_hen_day = self._calculate_percentage(self.eggs_total, self.hen_count)
        initial_hens = self.flock.initial_hen_count if self.flock_id and self.flock else 0
        self.pct_hen_housed = self._calculate_percentage(self.eggs_total, initial_hens)

    def update_fcr(self):
        self.fcr = self._calculate_fcr(self.feed_bags, self.eggs_total)

    def save(self, *args, **kwargs):
        self.update_live_hen_count()
        self.update_laying_percentages()
        self.update_fcr()
        super().save(*args, **kwargs)
        self.recalculate_flock_snapshots(self.flock_id)

    def delete(self, *args, **kwargs):
        flock_id = self.flock_id
        result = super().delete(*args, **kwargs)
        self.recalculate_flock_snapshots(flock_id)
        return result

    @classmethod
    def recalculate_flock_snapshots(cls, flock_id):
        if not flock_id:
            return

        try:
            flock = Flock.objects.get(pk=flock_id)
        except Flock.DoesNotExist:
            return

        live_hens = flock.initial_hen_count
        logs = cls.objects.filter(flock_id=flock_id).order_by('log_date', 'pk')
        for log in logs:
            live_hens = max(live_hens - (log.dead_count or 0) - (log.culled_count or 0), 0)
            hen_day = cls._calculate_percentage(log.eggs_total, live_hens)
            hen_housed = cls._calculate_percentage(log.eggs_total, flock.initial_hen_count)
            fcr = cls._calculate_fcr(log.feed_bags, log.eggs_total)
            if (
                log.hen_count != live_hens
                or log.pct_hen_day != hen_day
                or log.pct_hen_housed != hen_housed
                or log.fcr != fcr
            ):
                cls.objects.filter(pk=log.pk).update(
                    hen_count=live_hens,
                    pct_hen_day=hen_day,
                    pct_hen_housed=hen_housed,
                    fcr=fcr,
                )

    @staticmethod
    def _calculate_percentage(eggs_total, hen_count):
        if not eggs_total or not hen_count:
            return Decimal('0.00')

        percentage = (Decimal(eggs_total) / Decimal(hen_count)) * Decimal('100')
        return percentage.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def _calculate_fcr(feed_bags, eggs_total):
        if not feed_bags or not eggs_total:
            return Decimal('0.000')

        feed_kg = Decimal(feed_bags) * Decimal(str(getattr(settings, 'HENALYTICS_FEED_BAG_KG', 50)))
        egg_kg = Decimal(eggs_total) * Decimal(str(getattr(settings, 'HENALYTICS_AVG_EGG_KG', 0.06)))
        if egg_kg == 0:
            return Decimal('0.000')

        return (feed_kg / egg_kg).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
    
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

