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
    fields = ('production_date', 'age_weeks', 'live_hen_count', 'eggs_collected', 'hen_day_production')


@admin.register(ProductionLog)
class ProductionLogAdmin(admin.ModelAdmin):
    list_display = ('flock', 'production_date', 'live_hen_count', 'eggs_collected', 'hen_day_production', 'hen_housed_production')
    list_filter = ('flock', 'production_date')
    search_fields = ('flock__house_no',)
    date_hierarchy = 'production_date'
    readonly_fields = ('entered_by', 'created_at', 'updated_at')
    fieldsets = (
        ('Flock Information', {
            'fields': ('flock', 'production_date')
        }),
        ('Age Data', {
            'fields': ('age_weeks', 'age_days')
        }),
        ('Population Metrics', {
            'fields': ('live_hen_count', 'daily_mortality', 'daily_culls')
        }),
        ('Production Data', {
            'fields': ('eggs_collected', 'hen_day_production', 'hen_housed_production')
        }),
        ('Feed & Conversion', {
            'fields': ('feed_consumed_bags', 'feed_conversion_ratio')
        }),
        ('Additional Info', {
            'fields': ('management_remarks', 'entered_by', 'created_at', 'updated_at')
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
    list_display = ('flock', 'grading_date', 'age_weeks', 'grade_jumbo', 'grade_extra_large', 'grade_large')
    list_filter = ('flock', 'grading_date')
    search_fields = ('flock__house_no',)
    date_hierarchy = 'grading_date'
    fieldsets = (
        ('Flock Information', {
            'fields': ('flock', 'grading_date', 'age_weeks')
        }),
        ('Total & Grade Distribution', {
            'fields': ('grade_jumbo', 'grade_extra_large', 'grade_large', 'grade_medium')
        }),
        ('Defects & Special', {
            'fields': ('grade_small', 'grade_pullets', 'grade_peewee', 'cracked_eggs', 'source')
        }),
    )


class SalesItemInline(admin.TabularInline):
    model = SalesItem
    extra = 1
    fields = ('grade', 'quantity_trays', 'price_per_tray', 'total_amount')
    readonly_fields = ('total_amount',)


@admin.register(SalesTransaction)
class SalesTransactionAdmin(admin.ModelAdmin):
    list_display = ('flock', 'sale_date', 'recorded_by', 'created_at')
    list_filter = ('flock', 'sale_date', 'recorded_by')
    search_fields = ('flock__house_no', 'notes')
    date_hierarchy = 'sale_date'
    inlines = [SalesItemInline]
    readonly_fields = ('recorded_by', 'created_at', 'updated_at')
    fieldsets = (
        ('Transaction Information', {
            'fields': ('flock', 'sale_date')
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
    list_display = ('forecast_date', 'grade', 'predicted_trays', 'model_version')
    list_filter = ('forecast_date', 'grade', 'model_version')
    date_hierarchy = 'forecast_date'
    readonly_fields = ('created_at',)

