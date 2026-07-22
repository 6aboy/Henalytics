from django.contrib import admin
from .models import (
    UserProfile, Flock, ProductionLog, GradingLog,
    SalesTransaction, SalesItem, ModelVersion, HarvestForecast, SalesForecast
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'assigned_house', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('user__username', 'user__email')


@admin.register(Flock)
class FlockAdmin(admin.ModelAdmin):
    list_display = ('house_no', 'breed_strain', 'date_started', 'initial_hen_count', 'status')
    list_filter = ('status', 'breed_strain', 'date_started')
    search_fields = ('house_no', 'breed_strain')
    fieldsets = (
        ('Basic Information', {
            'fields': ('house_no', 'breed_strain')
        }),
        ('Population', {
            'fields': ('initial_hen_count', 'status')
        }),
        ('Timeline', {
            'fields': ('date_started',)
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )


class ProductionLogInline(admin.TabularInline):
    model = ProductionLog
    extra = 1
    fields = ('log_date', 'age_weeks', 'hen_count', 'eggs_total', 'pct_hen_day')


@admin.register(ProductionLog)
class ProductionLogAdmin(admin.ModelAdmin):
    list_display = ('flock', 'log_date', 'hen_count', 'eggs_total', 'pct_hen_day', 'pct_hen_housed')
    list_filter = ('flock', 'log_date')
    search_fields = ('flock__house_no',)
    date_hierarchy = 'log_date'
    readonly_fields = ('entered_by', 'created_at', 'updated_at')
    fieldsets = (
        ('Flock Information', {
            'fields': ('flock', 'log_date')
        }),
        ('Age Data', {
            'fields': ('age_weeks', 'age_days')
        }),
        ('Population Metrics', {
            'fields': ('hen_count', 'dead_count', 'culled_count')
        }),
        ('Production Data', {
            'fields': ('eggs_total', 'pct_hen_day', 'pct_hen_housed')
        }),
        ('Feed & Conversion', {
            'fields': ('feed_bags', 'fcr')
        }),
        ('Additional Info', {
            'fields': ('remarks', 'entered_by', 'created_at', 'updated_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.entered_by = request.user
        super().save_model(request, obj, form, change)


class GradingLogInline(admin.TabularInline):
    model = GradingLog
    extra = 1


@admin.register(GradingLog)
class GradingLogAdmin(admin.ModelAdmin):
    list_display = ('flock', 'log_date', 'age_weeks', 'eggs_total', 'eggs_aa', 'eggs_a', 'eggs_b')
    list_filter = ('flock', 'log_date')
    search_fields = ('flock__house_no',)
    date_hierarchy = 'log_date'
    fieldsets = (
        ('Flock Information', {
            'fields': ('flock', 'log_date', 'age_weeks')
        }),
        ('Total & Grade Distribution', {
            'fields': ('eggs_total', 'eggs_aa', 'eggs_a', 'eggs_b', 'eggs_small')
        }),
        ('Defects & Special', {
            'fields': ('eggs_broken', 'eggs_decode', 'eggs_source')
        }),
    )


class SalesItemInline(admin.TabularInline):
    model = SalesItem
    extra = 1
    fields = ('grade', 'quantity_pieces', 'amount', 'unit_price')
    readonly_fields = ('unit_price',)


@admin.register(SalesTransaction)
class SalesTransactionAdmin(admin.ModelAdmin):
    list_display = ('flock', 'sale_date', 'or_number', 'recorded_by', 'created_at')
    list_filter = ('flock', 'sale_date', 'recorded_by')
    search_fields = ('flock__house_no', 'notes')
    date_hierarchy = 'sale_date'
    inlines = [SalesItemInline]
    readonly_fields = ('recorded_by', 'created_at', 'updated_at')
    fieldsets = (
        ('Transaction Information', {
            'fields': ('flock', 'sale_date', 'or_number')
        }),
        ('Notes & User', {
            'fields': ('notes', 'recorded_by', 'created_at', 'updated_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ModelVersion)
class ModelVersionAdmin(admin.ModelAdmin):
    list_display = ('model_type', 'trained_at', 'r2_score', 'rmse', 'is_active')
    list_filter = ('model_type', 'trained_at', 'is_active')
    search_fields = ('triggered_by__username',)
    readonly_fields = ('created_at', 'trained_at')
    fieldsets = (
        ('Model Information', {
            'fields': ('model_type', 'trained_at', 'triggered_by')
        }),
        ('Performance Metrics', {
            'fields': ('r2_score', 'rmse', 'aic_score')
        }),
        ('ARIMA Configuration', {
            'fields': ('arima_order', 'training_rows')
        }),
        ('Storage', {
            'fields': ('pkl_path', 'is_active', 'created_at')
        }),
    )


@admin.register(HarvestForecast)
class HarvestForecastAdmin(admin.ModelAdmin):
    list_display = ('flock', 'forecast_date', 'grade', 'predicted_qty', 'model_version')
    list_filter = ('flock', 'forecast_date', 'grade', 'model_version')
    search_fields = ('flock__house_no',)
    date_hierarchy = 'forecast_date'
    readonly_fields = ('created_at',)


@admin.register(SalesForecast)
class SalesForecastAdmin(admin.ModelAdmin):
    list_display = ('forecast_date', 'grade', 'predicted_amount', 'model_version')
    list_filter = ('forecast_date', 'grade', 'model_version')
    date_hierarchy = 'forecast_date'
    readonly_fields = ('created_at',)

