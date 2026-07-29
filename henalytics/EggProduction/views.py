from django.http import HttpResponse, JsonResponse
from django.http import QueryDict
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DetailView, DeleteView, View
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib.auth.views import LoginView
from django.db import models, transaction
from django.utils import timezone
from django.conf import settings
from datetime import date, timedelta
import json
import logging
import sys
from pathlib import Path
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import (
    UserProfile, Flock, ProductionLog, GradingLog,
    SalesTransaction, SalesItem, ModelVersion, HarvestForecast, SalesForecast
)
from .serializers import (
    UserProfileSerializer, FlockSerializer, ProductionLogSerializer, GradingLogSerializer,
    SalesTransactionSerializer, SalesItemSerializer, ModelVersionSerializer,
    HarvestForecastSerializer, SalesForecastSerializer
)
from .forms import ProductionLogForm, SalesItemForm, SalesItemFormSet, SalesTransactionForm
from .forecasting_service import ForecastingService

logger = logging.getLogger(__name__)


FORECAST_TABLE_LIMIT = 500
EXPERIMENTAL_FORECAST_RANGES = {
    'week': ('7 Days', 7),
    'three_weeks': ('3 Weeks', 21),
    'month': ('1 Month', 30),
    'three_months': ('3 Months', 90),
}


def build_forecast_chart_payload(queryset, value_field):
    rows = (
        queryset.values('forecast_date', 'grade')
        .annotate(total=models.Sum(value_field))
        .order_by('forecast_date', 'grade')
    )
    dates = sorted({row['forecast_date'] for row in rows})
    grades = sorted({row['grade'] for row in rows})
    labels = [forecast_date.strftime('%b %d, %Y') for forecast_date in dates]
    choice_map = dict(queryset.model._meta.get_field('grade').choices)

    series = {}
    for grade in grades:
        values_by_date = {
            row['forecast_date']: float(row['total'] or 0)
            for row in rows
            if row['grade'] == grade
        }
        series[grade] = {
            'label': choice_map.get(grade, grade.title()),
            'values': [values_by_date.get(forecast_date, 0) for forecast_date in dates],
        }

    return {
        'labels': labels,
        'series': series,
    }


def build_actual_vs_forecast_payload(actual_rows, forecast_rows):
    actual_by_date = {
        row['log_date']: float(row['total'] or 0)
        for row in actual_rows
    }
    forecast_by_date = {
        row['forecast_date']: float(row['total'] or 0)
        for row in forecast_rows
    }
    lower_by_date = {
        row['forecast_date']: float(row['lower'] or 0)
        for row in forecast_rows
        if 'lower' in row and row['lower'] is not None
    }
    upper_by_date = {
        row['forecast_date']: float(row['upper'] or 0)
        for row in forecast_rows
        if 'upper' in row and row['upper'] is not None
    }
    dates = sorted(set(actual_by_date) | set(forecast_by_date))
    last_actual_date = max(actual_by_date) if actual_by_date else None
    return {
        'labels': [item.strftime('%b %d, %Y') for item in dates],
        'actual': [actual_by_date.get(item) for item in dates],
        'forecast': [
            actual_by_date.get(item) if item == last_actual_date else forecast_by_date.get(item)
            for item in dates
        ],
        'lower': [
            actual_by_date.get(item) if item == last_actual_date else lower_by_date.get(item)
            for item in dates
        ],
        'upper': [
            actual_by_date.get(item) if item == last_actual_date else upper_by_date.get(item)
            for item in dates
        ],
    }


def build_sales_actual_vs_forecast_payload(actual_rows, forecast_rows):
    actual_by_date = {
        row['transaction__sale_date']: float(row['total'] or 0)
        for row in actual_rows
    }
    forecast_by_date = {
        row['forecast_date']: float(row['total'] or 0)
        for row in forecast_rows
    }
    dates = sorted(set(actual_by_date) | set(forecast_by_date))
    last_actual_date = max(actual_by_date) if actual_by_date else None
    return {
        'labels': [item.strftime('%b %d, %Y') for item in dates],
        'actual': [actual_by_date.get(item) for item in dates],
        'forecast': [
            actual_by_date.get(item) if item == last_actual_date else forecast_by_date.get(item)
            for item in dates
        ],
    }


def build_hen_performance_payload(logs):
    rows = (
        logs.values('log_date')
        .annotate(
            hen_day=models.Avg('pct_hen_day'),
            hen_housed=models.Avg('pct_hen_housed'),
        )
        .order_by('log_date')
    )
    labels = [row['log_date'].strftime('%b %d, %Y') for row in rows]
    return {
        'labels': labels,
        'hen_day': [float(row['hen_day'] or 0) for row in rows],
        'hen_housed': [float(row['hen_housed'] or 0) for row in rows],
        'threshold': [60 for _ in labels],
    }


def build_size_mix_payload(grading_logs, forecasts):
    grade_fields = [
        ('xl', 'XL', 'eggs_aa'),
        ('large', 'Large', 'eggs_a'),
        ('medium', 'Medium', 'eggs_b'),
        ('small', 'Small', 'eggs_small'),
        ('pewee', 'Pewee', 'eggs_decode'),
    ]
    historical_totals = grading_logs.aggregate(
        **{key: models.Sum(field_name) for key, _label, field_name in grade_fields}
    )
    forecast_totals = (
        forecasts.exclude(grade='overall')
        .values('grade')
        .annotate(total=models.Sum('predicted_qty'))
    )
    forecast_by_grade = {
        row['grade']: float(row['total'] or 0)
        for row in forecast_totals
    }

    return {
        'labels': [label for _key, label, _field_name in grade_fields],
        'historical': [float(historical_totals.get(key) or 0) for key, _label, _field_name in grade_fields],
        'forecast': [forecast_by_grade.get(key, 0) for key, _label, _field_name in grade_fields],
    }


def average(values):
    values = [float(value) for value in values if value is not None]
    return sum(values) / len(values) if values else None


def percent_change(previous, current):
    if previous in (None, 0) or current is None:
        return None
    return ((current - previous) / previous) * 100


def build_egg_insights(logs, grading_logs, forecasts):
    latest_log = logs.order_by('-log_date').first()
    latest_hen_housed = float(latest_log.pct_hen_housed) if latest_log else None
    latest_hen_day = float(latest_log.pct_hen_day) if latest_log else None

    recent_logs = list(logs.order_by('-log_date')[:14])
    previous_logs = list(logs.order_by('-log_date')[14:28])
    recent_avg_eggs = average([log.eggs_total for log in recent_logs])
    previous_avg_eggs = average([log.eggs_total for log in previous_logs])
    production_change = percent_change(previous_avg_eggs, recent_avg_eggs)

    overall_forecasts = list(forecasts.filter(grade='overall').order_by('forecast_date'))
    first_forecast_avg = average([forecast.predicted_qty for forecast in overall_forecasts[:7]])
    last_forecast_avg = average([forecast.predicted_qty for forecast in overall_forecasts[-7:]])
    forecast_change = percent_change(first_forecast_avg, last_forecast_avg)

    grading_rows = list(grading_logs.order_by('-log_date')[:28])
    recent_grades = grading_rows[:14]
    previous_grades = grading_rows[14:28]

    def small_share(rows):
        total = sum(row.eggs_total or 0 for row in rows)
        small = sum((row.eggs_small or 0) + (row.eggs_decode or 0) for row in rows)
        return (small / total * 100) if total else None

    recent_small_share = small_share(recent_grades)
    previous_small_share = small_share(previous_grades)
    small_share_change = (
        recent_small_share - previous_small_share
        if recent_small_share is not None and previous_small_share is not None
        else None
    )

    if latest_hen_housed is None:
        status = {
            'label': 'No Basis Yet',
            'tone': 'neutral',
            'value': 'No logs',
            'meta': 'Add production records to evaluate flock condition.',
        }
    elif latest_hen_housed < 60:
        status = {
            'label': 'Flock Status',
            'tone': 'danger',
            'value': 'Critical',
            'meta': f'Hen housed is {latest_hen_housed:.2f}%, below the 60% warning threshold.',
        }
    elif latest_hen_housed < 70:
        status = {
            'label': 'Flock Status',
            'tone': 'warning',
            'value': 'Watch',
            'meta': f'Hen housed is {latest_hen_housed:.2f}%, getting close to the 60% warning threshold.',
        }
    else:
        status = {
            'label': 'Flock Status',
            'tone': 'good',
            'value': 'Stable',
            'meta': f'Hen housed is {latest_hen_housed:.2f}%, above the 60% warning threshold.',
        }

    if forecast_change is None:
        forecast_card = {
            'label': 'Forecast Direction',
            'tone': 'neutral',
            'value': 'Pending',
            'meta': 'Run a forecast to compare early and late forecast periods.',
        }
    elif forecast_change < -5:
        forecast_card = {
            'label': 'Forecast Direction',
            'tone': 'danger',
            'value': 'Declining',
            'meta': f'Forecast average drops by {abs(forecast_change):.1f}% across the selected horizon.',
        }
    elif forecast_change > 5:
        forecast_card = {
            'label': 'Forecast Direction',
            'tone': 'good',
            'value': 'Improving',
            'meta': f'Forecast average rises by {forecast_change:.1f}% across the selected horizon.',
        }
    else:
        forecast_card = {
            'label': 'Forecast Direction',
            'tone': 'neutral',
            'value': 'Mostly Flat',
            'meta': f'Forecast average changes by {forecast_change:.1f}% across the selected horizon.',
        }

    if small_share_change is None:
        size_card = {
            'label': 'Egg Size Signal',
            'tone': 'neutral',
            'value': 'Insufficient',
            'meta': 'Add grading records to monitor whether egg sizes are shifting smaller.',
        }
    elif small_share_change > 5:
        size_card = {
            'label': 'Egg Size Signal',
            'tone': 'warning',
            'value': 'Smaller Shift',
            'meta': f'Small and pewee share increased by {small_share_change:.1f} percentage points recently.',
        }
    else:
        size_card = {
            'label': 'Egg Size Signal',
            'tone': 'good',
            'value': 'No Major Shift',
            'meta': f'Small and pewee share changed by {small_share_change:.1f} percentage points recently.',
        }

    notes = []
    if latest_hen_housed is not None and latest_hen_housed < 60:
        notes.append('Hen housed production is below 60%, so the flock should be reviewed for culling or replacement planning.')
    if latest_hen_day is not None and latest_hen_day < 60:
        notes.append('Hen day production is also below 60%, indicating weak daily laying performance.')
    if production_change is not None and production_change < -5:
        notes.append(f'Recent actual egg production is {abs(production_change):.1f}% lower than the previous comparable period.')
    if forecast_change is not None and forecast_change < -5:
        notes.append('The forecast continues downward, so the decline is expected to persist if conditions stay similar.')
    if small_share_change is not None and small_share_change > 5:
        notes.append('The grading data suggests a shift toward smaller eggs, which may affect revenue and flock assessment.')
    if not notes:
        notes.append('No critical signal was detected from the current production, grading, and forecast records.')

    return {
        'cards': [status, forecast_card, size_card],
        'notes': notes,
        'latest_hen_housed': latest_hen_housed,
        'latest_hen_day': latest_hen_day,
    }


def build_forecast_run_summary(forecasts, value_field):
    model_ids = list(forecasts.values_list('model_version_id', flat=True).distinct())
    model_count = len(model_ids)
    first_row = forecasts.order_by('forecast_date').first()
    last_row = forecasts.order_by('-forecast_date').first()
    rows = forecasts.count()
    total = forecasts.aggregate(total=models.Sum(value_field))['total'] or 0
    daily_points = forecasts.values('forecast_date').distinct().count()
    categories = forecasts.values('grade').distinct().count()

    return {
        'model_count': model_count,
        'first_row': first_row,
        'last_row': last_row,
        'rows': rows,
        'total': total,
        'daily_points': daily_points,
        'categories': categories,
        'is_single_run': model_count <= max(categories, 1),
    }


def build_sales_insights(actual_rows, forecasts):
    actual_values = [float(row['total'] or 0) for row in actual_rows]
    recent_actual = actual_values[-14:]
    previous_actual = actual_values[-28:-14]
    actual_change = percent_change(average(previous_actual), average(recent_actual))

    overall_forecasts = list(forecasts.filter(grade='overall').order_by('forecast_date'))
    first_forecast_avg = average([forecast.predicted_amount for forecast in overall_forecasts[:7]])
    last_forecast_avg = average([forecast.predicted_amount for forecast in overall_forecasts[-7:]])
    forecast_change = percent_change(first_forecast_avg, last_forecast_avg)

    if forecast_change is None:
        direction = {
            'label': 'Revenue Direction',
            'tone': 'neutral',
            'value': 'Pending',
            'meta': 'Run a forecast to compare early and late revenue periods.',
        }
    elif forecast_change < -5:
        direction = {
            'label': 'Revenue Direction',
            'tone': 'danger',
            'value': 'Declining',
            'meta': f'Forecast average drops by {abs(forecast_change):.1f}% across the selected horizon.',
        }
    elif forecast_change > 5:
        direction = {
            'label': 'Revenue Direction',
            'tone': 'good',
            'value': 'Improving',
            'meta': f'Forecast average rises by {forecast_change:.1f}% across the selected horizon.',
        }
    else:
        direction = {
            'label': 'Revenue Direction',
            'tone': 'neutral',
            'value': 'Mostly Flat',
            'meta': f'Forecast average changes by {forecast_change:.1f}% across the selected horizon.',
        }

    if actual_change is None:
        recent = {
            'label': 'Recent Sales',
            'tone': 'neutral',
            'value': 'No Basis',
            'meta': 'More sales records are needed for recent comparison.',
        }
    elif actual_change < -5:
        recent = {
            'label': 'Recent Sales',
            'tone': 'warning',
            'value': 'Lower',
            'meta': f'Recent revenue is {abs(actual_change):.1f}% lower than the previous period.',
        }
    elif actual_change > 5:
        recent = {
            'label': 'Recent Sales',
            'tone': 'good',
            'value': 'Higher',
            'meta': f'Recent revenue is {actual_change:.1f}% higher than the previous period.',
        }
    else:
        recent = {
            'label': 'Recent Sales',
            'tone': 'neutral',
            'value': 'Steady',
            'meta': f'Recent revenue changed by {actual_change:.1f}%.',
        }

    notes = []
    if actual_change is not None:
        notes.append(f'Recent actual revenue changed by {actual_change:.1f}% compared with the previous comparable period.')
    if forecast_change is not None:
        notes.append(f'The selected forecast horizon expects revenue to change by {forecast_change:.1f}% from its first week to its final week.')
    if not notes:
        notes.append('Run a sales forecast after adding sales records to generate revenue interpretation.')

    return {
        'cards': [direction, recent],
        'notes': notes,
    }


# Custom login view so staff users land on the dashboard instead of admin
class CustomLoginView(LoginView):
    def get_success_url(self):
        # Superusers keep default behavior (may use next)
        if self.request.user.is_superuser:
            return super().get_success_url()

        # Staff users go to the dashboard
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return reverse_lazy('eggproduction:dashboard')

        return super().get_success_url()


# Mixins for access control
class StaffAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin to restrict view to staff/admin users"""
    def test_func(self):
        user = self.request.user
        try:
            profile = UserProfile.objects.get(user=user)
            return profile.role in ['staff', 'admin', 'manager']
        except UserProfile.DoesNotExist:
            return user.is_staff or user.is_superuser


class ManagerAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin to restrict view to manager/admin users"""
    def test_func(self):
        user = self.request.user
        try:
            profile = UserProfile.objects.get(user=user)
            return profile.role in ['admin', 'manager']
        except UserProfile.DoesNotExist:
            return user.is_superuser


class DirectDeleteOnlyMixin:
    """Keep DeleteView POST behavior, but avoid rendering a second confirmation page."""
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        messages.info(request, 'Use the delete button to confirm removal.')
        return redirect(self.get_success_url())


# Dashboard View
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'index.html'

    def get_period_bounds(self):
        today = timezone.localdate()
        period = self.request.GET.get('period', 'month')
        start = None
        end = today

        if period == 'today':
            start = today
        elif period == 'six_months':
            start = today - timedelta(days=183)
        elif period == 'year':
            start = today.replace(month=1, day=1)
        elif period == 'all':
            end = None
        elif period == 'custom':
            start_value = self.request.GET.get('date_from')
            end_value = self.request.GET.get('date_to')
            try:
                start = date.fromisoformat(start_value) if start_value else None
                end = date.fromisoformat(end_value) if end_value else today
            except ValueError:
                start = today.replace(day=1)
                end = today
        else:
            period = 'month'
            start = today.replace(day=1)

        labels = {
            'today': 'Today',
            'month': 'This Month',
            'six_months': 'Last 6 Months',
            'year': 'This Year',
            'all': 'All Records',
            'custom': 'Custom Range',
        }
        return period, start, end, labels.get(period, 'This Month')

    @staticmethod
    def filter_by_date(queryset, field_name, start, end):
        if start:
            queryset = queryset.filter(**{f'{field_name}__gte': start})
        if end:
            queryset = queryset.filter(**{f'{field_name}__lte': end})
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            today = timezone.localdate()
            last_7_days = today - timedelta(days=7)
            last_30_days = today - timedelta(days=30)
            period, date_from, date_to, period_label = self.get_period_bounds()
            period_logs = self.filter_by_date(ProductionLog.objects.all(), 'log_date', date_from, date_to)
            period_sales_items = self.filter_by_date(SalesItem.objects.all(), 'transaction__sale_date', date_from, date_to)

            active_flocks = Flock.objects.filter(status='active').count()
            today_production = ProductionLog.objects.filter(log_date=today).aggregate(
                total=models.Sum('eggs_total')
            )['total'] or 0
            period_egg_total = period_logs.aggregate(
                total=models.Sum('eggs_total')
            )['total'] or 0
            period_feed_total = period_logs.aggregate(
                total=models.Sum('feed_bags')
            )['total'] or 0
            period_losses = period_logs.aggregate(
                lost=models.Sum(models.F('dead_count') + models.F('culled_count'))
            )['lost'] or 0
            period_revenue = period_sales_items.aggregate(total=models.Sum('amount'))['total'] or 0
            total_hens = Flock.objects.filter(status='active').aggregate(
                total=models.Sum('initial_hen_count')
            )['total'] or 0
            weekly_revenue = SalesItem.objects.filter(
                transaction__sale_date__gte=last_7_days
            ).aggregate(total=models.Sum('amount'))['total'] or 0
            avg_fcr_30d = ProductionLog.objects.filter(log_date__gte=last_30_days).aggregate(
                avg=models.Avg('fcr')
            )['avg'] or 0
            avg_lay_rate_30d = ProductionLog.objects.filter(log_date__gte=last_30_days).aggregate(
                avg=models.Avg('pct_hen_day')
            )['avg'] or 0
            feed_consumed_30d = ProductionLog.objects.filter(log_date__gte=last_30_days).aggregate(
                total=models.Sum('feed_bags')
            )['total'] or 0
            grading_logs = GradingLog.objects.filter(log_date__gte=last_30_days)
            broken_eggs = grading_logs.aggregate(total=models.Sum('eggs_broken'))['total'] or 0
            graded_total = grading_logs.aggregate(total=models.Sum('eggs_total'))['total'] or 0
            cracked_egg_loss = float(broken_eggs) / graded_total * 100 if graded_total else 0
            recent_losses_7d = ProductionLog.objects.filter(log_date__gte=last_7_days).aggregate(
                lost=models.Sum(models.F('dead_count') + models.F('culled_count'))
            )['lost'] or 0

            context.update({
                'today': today,
                'dashboard_period': period,
                'dashboard_date_from': date_from,
                'dashboard_date_to': date_to,
                'dashboard_period_label': period_label,
                'active_flocks': active_flocks,
                'today_production': today_production,
                'period_egg_total': period_egg_total,
                'period_feed_total': period_feed_total,
                'period_losses': period_losses,
                'period_revenue': float(period_revenue),
                'today_sales': SalesTransaction.objects.filter(sale_date=today).count(),
                'total_revenue': float(weekly_revenue),
                'total_hens': total_hens,
                'weekly_revenue': float(weekly_revenue),
                'avg_fcr_30d': round(avg_fcr_30d, 2) if avg_fcr_30d else 0,
                'avg_lay_rate_30d': round(avg_lay_rate_30d, 1) if avg_lay_rate_30d else 0,
                'feed_consumed_30d': feed_consumed_30d,
                'cracked_egg_loss': round(cracked_egg_loss, 1),
                'recent_losses_7d': recent_losses_7d,
            })
        except Exception as e:
            logger.exception("Dashboard error: %s", e)
            context.update({
                'today': timezone.localdate(),
                'dashboard_period': 'month',
                'dashboard_date_from': None,
                'dashboard_date_to': None,
                'dashboard_period_label': 'This Month',
                'active_flocks': 0,
                'today_production': 0,
                'period_egg_total': 0,
                'period_feed_total': 0,
                'period_losses': 0,
                'period_revenue': 0,
                'today_sales': 0,
                'total_revenue': 0,
                'total_hens': 0,
                'weekly_revenue': 0,
                'avg_fcr_30d': 0,
                'avg_lay_rate_30d': 0,
                'feed_consumed_30d': 0,
                'cracked_egg_loss': 0,
                'recent_losses_7d': 0,
            })
        return context


# ======================== Flock Views ========================

class FlockListView(LoginRequiredMixin, ListView):
    model = Flock
    template_name = 'egg_production/flock_list.html'
    context_object_name = 'flocks'
    ordering = ['-date_started']


class FlockCreateView(ManagerAccessMixin, CreateView):
    model = Flock
    template_name = 'egg_production/flock_form.html'
    fields = ['house_no', 'breed_strain', 'date_started', 'initial_hen_count', 'status', 'notes']
    success_url = reverse_lazy('eggproduction:flock-list')


class FlockDetailView(LoginRequiredMixin, DetailView):
    model = Flock
    template_name = 'egg_production/flock_detail.html'
    context_object_name = 'flock'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        flock = self.get_object()
        production_qs = ProductionLog.objects.filter(flock=flock)
        grading_qs = GradingLog.objects.filter(flock=flock)
        sales_qs = SalesTransaction.objects.filter(flock=flock)
        context['production_logs'] = production_qs.order_by('-log_date')[:5]
        context['grading_logs'] = grading_qs.order_by('-log_date')[:5]
        context['sales'] = sales_qs.order_by('-sale_date')[:5]
        context['production_log_count'] = production_qs.count()
        context['grading_log_count'] = grading_qs.count()
        context['sales_count'] = sales_qs.count()
        context['current_hen_count'] = (
            production_qs.order_by('-log_date', '-pk')
            .values_list('hen_count', flat=True)
            .first()
            or flock.initial_hen_count
        )
        return context


class FlockUpdateView(ManagerAccessMixin, UpdateView):
    model = Flock
    template_name = 'egg_production/flock_form.html'
    fields = ['house_no', 'breed_strain', 'date_started', 'initial_hen_count', 'status', 'notes']
    success_url = reverse_lazy('eggproduction:flock-list')


class FlockDeleteView(DirectDeleteOnlyMixin, ManagerAccessMixin, DeleteView):
    model = Flock
    template_name = 'egg_production/flock_confirm_delete.html'
    success_url = reverse_lazy('eggproduction:flock-list')


# ======================== Production Log Views ========================

class ProductionLogListView(StaffAccessMixin, ListView):
    model = ProductionLog
    template_name = 'egg_production/production_log_list.html'
    context_object_name = 'production_logs'
    ordering = ['-log_date']
    
    def get_queryset(self):
        qs = super().get_queryset().select_related('flock', 'entered_by')
        flock_id = self.request.GET.get('flock_id')
        if flock_id:
            qs = qs.filter(flock_id=flock_id)
        period = self.request.GET.get('period', 'all')
        today = timezone.localdate()
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')

        if period == 'today':
            qs = qs.filter(log_date=today)
        elif period == 'month':
            qs = qs.filter(log_date__gte=today.replace(day=1), log_date__lte=today)
        elif period == 'six_months':
            qs = qs.filter(log_date__gte=today - timedelta(days=183), log_date__lte=today)
        elif period == 'year':
            qs = qs.filter(log_date__gte=today.replace(month=1, day=1), log_date__lte=today)
        elif period == 'custom':
            if date_from:
                qs = qs.filter(log_date__gte=date_from)
            if date_to:
                qs = qs.filter(log_date__lte=date_to)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['flocks'] = Flock.objects.order_by('house_no', '-date_started')
        context['selected_flock_id'] = self.request.GET.get('flock_id', '')
        context['selected_period'] = self.request.GET.get('period', 'all')
        context['selected_date_from'] = self.request.GET.get('date_from', '')
        context['selected_date_to'] = self.request.GET.get('date_to', '')
        return context


class ProductionLogFormMixin:
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field_name in ('pct_hen_day', 'pct_hen_housed', 'fcr'):
            if field_name not in form.fields:
                continue
            form.fields[field_name].required = False
            form.fields[field_name].widget.attrs['readonly'] = True
            form.fields[field_name].widget.attrs['class'] = (
                form.fields[field_name].widget.attrs.get('class', '') + ' readonly-metric'
            ).strip()
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['flock_initial_counts'] = {
            str(flock.id): flock.initial_hen_count
            for flock in Flock.objects.only('id', 'initial_hen_count')
        }
        context['flock_start_dates'] = {
            str(flock.id): flock.date_started.isoformat()
            for flock in Flock.objects.only('id', 'date_started')
        }
        context['feed_bag_kg'] = getattr(settings, 'HENALYTICS_FEED_BAG_KG', 50)
        context['avg_egg_kg'] = getattr(settings, 'HENALYTICS_AVG_EGG_KG', 0.06)
        return context

    def form_valid(self, form):
        form.instance.update_flock_age()
        return super().form_valid(form)


class ProductionLogCreateView(StaffAccessMixin, ProductionLogFormMixin, CreateView):
    model = ProductionLog
    template_name = 'egg_production/production_log_form.html'
    form_class = ProductionLogForm
    success_url = reverse_lazy('eggproduction:production-log-list')
    
    def form_valid(self, form):
        form.instance.entered_by = self.request.user
        response = super().form_valid(form)
        messages.success(
            self.request,
            'Egg production record created successfully.',
            extra_tags='swal',
        )
        return response


class ProductionLogDetailView(StaffAccessMixin, DetailView):
    model = ProductionLog
    template_name = 'egg_production/production_log_detail.html'
    context_object_name = 'production_log'

    def get_queryset(self):
        return super().get_queryset().select_related('flock', 'entered_by')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        log = self.object
        context['entered_by_name'] = (
            log.entered_by.get_full_name()
            or log.entered_by.username
            if log.entered_by_id
            else 'N/A'
        )
        return context


class ProductionLogUpdateView(StaffAccessMixin, ProductionLogFormMixin, UpdateView):
    model = ProductionLog
    template_name = 'egg_production/production_log_form.html'
    form_class = ProductionLogForm
    success_url = reverse_lazy('eggproduction:production-log-list')


class ProductionLogDeleteView(DirectDeleteOnlyMixin, StaffAccessMixin, DeleteView):
    model = ProductionLog
    template_name = 'egg_production/production_log_confirm_delete.html'
    success_url = reverse_lazy('eggproduction:production-log-list')


# ======================== Grading Log Views ========================

class GradingLogListView(StaffAccessMixin, ListView):
    model = GradingLog
    template_name = 'egg_production/grading_log_list.html'
    context_object_name = 'grading_logs'
    paginate_by = 15
    ordering = ['-log_date']
    
    def get_queryset(self):
        qs = super().get_queryset().select_related('flock')
        flock_id = self.request.GET.get('flock_id')
        if flock_id:
            qs = qs.filter(flock_id=flock_id)
        return qs


class GradingLogCreateView(StaffAccessMixin, CreateView):
    model = GradingLog
    template_name = 'egg_production/grading_log_form.html'
    fields = ['flock', 'log_date', 'age_weeks', 'eggs_total', 'eggs_aa', 'eggs_a',
              'eggs_b', 'eggs_small', 'eggs_broken', 'eggs_decode', 'eggs_source']
    success_url = reverse_lazy('eggproduction:grading-log-list')


class GradingLogDetailView(StaffAccessMixin, DetailView):
    model = GradingLog
    template_name = 'egg_production/grading_log_detail.html'
    context_object_name = 'grading_log'

    def get_queryset(self):
        return super().get_queryset().select_related('flock')


class GradingLogUpdateView(StaffAccessMixin, UpdateView):
    model = GradingLog
    template_name = 'egg_production/grading_log_form.html'
    fields = ['flock', 'log_date', 'age_weeks', 'eggs_total', 'eggs_aa', 'eggs_a',
              'eggs_b', 'eggs_small', 'eggs_broken', 'eggs_decode', 'eggs_source']
    success_url = reverse_lazy('eggproduction:grading-log-list')


class GradingLogDeleteView(DirectDeleteOnlyMixin, StaffAccessMixin, DeleteView):
    model = GradingLog
    template_name = 'egg_production/grading_log_confirm_delete.html'
    success_url = reverse_lazy('eggproduction:grading-log-list')


# ======================== Sales Transaction Views ========================

class SalesTransactionListView(StaffAccessMixin, ListView):
    model = SalesTransaction
    template_name = 'egg_production/sales_transaction_list.html'
    context_object_name = 'sales_transactions'
    ordering = ['-sale_date']
    
    def get_queryset(self):
        qs = super().get_queryset().select_related('flock', 'recorded_by')
        flock_id = self.request.GET.get('flock_id')
        if flock_id:
            qs = qs.filter(flock_id=flock_id)
        return qs


class SalesTransactionCreateView(StaffAccessMixin, CreateView):
    model = SalesTransaction
    template_name = 'egg_production/sales_transaction_form.html'
    form_class = SalesTransactionForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['sales_item_formset'] = SalesItemFormSet(self.request.POST, prefix='items')
        else:
            context['sales_item_formset'] = SalesItemFormSet(prefix='items')
        return context

    def form_valid(self, form):
        context = self.get_context_data(form=form)
        formset = context['sales_item_formset']
        if not formset.is_valid():
            return self.form_invalid(form)

        with transaction.atomic():
            form.instance.recorded_by = self.request.user
            self.object = form.save()
            formset.instance = self.object
            formset.save()
        messages.success(
            self.request,
            'Sales transaction created successfully.',
            extra_tags='swal',
        )
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        context = self.get_context_data(form=form)
        return self.render_to_response(context)

    def get_success_url(self):
        return reverse_lazy('eggproduction:sales-transaction-detail', kwargs={'pk': self.object.pk})


class SalesTransactionDetailView(StaffAccessMixin, DetailView):
    model = SalesTransaction
    template_name = 'egg_production/sales_transaction_detail.html'
    context_object_name = 'sales_transaction'

    def get_queryset(self):
        return super().get_queryset().select_related('flock', 'recorded_by')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        transaction = self.get_object()
        items = SalesItem.objects.filter(transaction=transaction)
        context['items'] = items
        context['total_amount'] = sum(item.amount for item in items)
        context['recorded_by_name'] = (
            transaction.recorded_by.get_full_name()
            or transaction.recorded_by.username
            if transaction.recorded_by_id
            else 'N/A'
        )
        return context


class SalesTransactionUpdateView(StaffAccessMixin, UpdateView):
    model = SalesTransaction
    template_name = 'egg_production/sales_transaction_form.html'
    form_class = SalesTransactionForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['sales_item_formset'] = SalesItemFormSet(
                self.request.POST,
                instance=self.object,
                prefix='items',
            )
        else:
            context['sales_item_formset'] = SalesItemFormSet(
                instance=self.object,
                prefix='items',
            )
        return context

    def form_valid(self, form):
        context = self.get_context_data(form=form)
        formset = context['sales_item_formset']
        if not formset.is_valid():
            return self.form_invalid(form)

        with transaction.atomic():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        context = self.get_context_data(form=form)
        return self.render_to_response(context)

    def get_success_url(self):
        return reverse_lazy('eggproduction:sales-transaction-detail', kwargs={'pk': self.object.pk})


class SalesTransactionDeleteView(DirectDeleteOnlyMixin, StaffAccessMixin, DeleteView):
    model = SalesTransaction
    template_name = 'egg_production/sales_transaction_confirm_delete.html'
    success_url = reverse_lazy('eggproduction:sales-transaction-list')


# ======================== Sales Item Views ========================

class SalesItemAddView(StaffAccessMixin, CreateView):
    model = SalesItem
    template_name = 'egg_production/sales_item_form.html'
    form_class = SalesItemForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        transaction_id = self.kwargs.get('transaction_id')
        context['transaction'] = get_object_or_404(SalesTransaction, pk=transaction_id)
        return context
    
    def form_valid(self, form):
        transaction_id = self.kwargs.get('transaction_id')
        form.instance.transaction = get_object_or_404(SalesTransaction, pk=transaction_id)
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('eggproduction:sales-transaction-detail',
                          kwargs={'pk': self.object.transaction.pk})


class SalesItemUpdateView(StaffAccessMixin, UpdateView):
    model = SalesItem
    template_name = 'egg_production/sales_item_form.html'
    form_class = SalesItemForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['transaction'] = self.object.transaction
        return context
    
    def get_success_url(self):
        return reverse_lazy('eggproduction:sales-transaction-detail',
                          kwargs={'pk': self.object.transaction.pk})


class SalesItemDeleteView(DirectDeleteOnlyMixin, StaffAccessMixin, DeleteView):
    model = SalesItem
    template_name = 'egg_production/sales_item_confirm_delete.html'
    
    def get_success_url(self):
        return reverse_lazy('eggproduction:sales-transaction-detail',
                          kwargs={'pk': self.object.transaction.pk})


# ======================== Forecast Views ========================

class HarvestForecastListView(ManagerAccessMixin, ListView):
    model = HarvestForecast
    template_name = 'egg_production/harvest_forecast_list.html'
    context_object_name = 'forecasts'
    ordering = ['-forecast_date']

    def post(self, request, *args, **kwargs):
        if not ManagerAccessMixin.test_func(self):
            messages.error(request, 'Only admin or manager accounts can run forecasts.')
            return redirect('eggproduction:harvest-forecast-list')

        flock_id = request.POST.get('flock_id')
        range_key = request.POST.get('range', 'month')
        periods = self._get_periods(request, range_key)
        include_sizes = request.POST.get('scope', 'both') == 'both'

        flocks = Flock.objects.filter(status='active')
        if flock_id:
            flocks = flocks.filter(id=flock_id)

        total_created = 0
        errors = []
        for flock in flocks:
            result = ForecastingService.generate_egg_forecasts(
                flock=flock,
                periods=periods,
                user=request.user,
                include_sizes=include_sizes,
            )
            total_created += result['created_count']
            errors.extend([f'House {flock.house_no} {error}' for error in result['errors']])

        if total_created:
            messages.success(request, f'Generated {total_created} egg forecast rows for the next {periods} day{"s" if periods != 1 else ""}.')
        if errors:
            messages.warning(request, '; '.join(errors[:3]))
        redirect_url = reverse_lazy('eggproduction:harvest-forecast-list')
        query = QueryDict(mutable=True)
        if flock_id:
            query['flock_id'] = flock_id
        query['range'] = range_key
        query['scope'] = request.POST.get('scope', 'both')
        if range_key == 'custom':
            if request.POST.get('date_from'):
                query['date_from'] = request.POST.get('date_from')
            if request.POST.get('date_to'):
                query['date_to'] = request.POST.get('date_to')
        if query:
            redirect_url = f'{redirect_url}?{query.urlencode()}'
        return redirect(redirect_url)
    
    def get_queryset(self):
        qs = super().get_queryset().select_related('flock', 'model_version')
        flock_id = self.request.GET.get('flock_id')
        if flock_id:
            qs = qs.filter(flock_id=flock_id)
        periods = self._get_display_periods(self.request)
        first_date = qs.order_by('forecast_date').values_list('forecast_date', flat=True).first()
        if first_date:
            qs = qs.filter(forecast_date__lte=first_date + timedelta(days=periods - 1))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        forecasts = self.get_queryset()
        overall_forecasts = forecasts.filter(grade='overall')
        chart_payload = build_forecast_chart_payload(forecasts, 'predicted_qty')
        flock_id = self.request.GET.get('flock_id', '')
        selected_range = self.request.GET.get('range', 'month')
        selected_scope = self.request.GET.get('scope', 'both')
        selected_periods = self._get_display_periods(self.request)
        selected_range_label = self._range_label(selected_range, selected_periods)
        production_logs = ProductionLog.objects.select_related('flock')
        grading_logs = GradingLog.objects.select_related('flock')
        if flock_id:
            production_logs = production_logs.filter(flock_id=flock_id)
            grading_logs = grading_logs.filter(flock_id=flock_id)
        else:
            production_logs = production_logs.filter(flock__status='active')
            grading_logs = grading_logs.filter(flock__status='active')

        forecast_start_row = forecasts.order_by('forecast_date').first()
        if forecast_start_row:
            actual_chart_start = forecast_start_row.forecast_date - timedelta(days=self._history_days_for_horizon(selected_periods))
        else:
            actual_chart_start = timezone.localdate() - timedelta(days=self._history_days_for_horizon(selected_periods))
        chart_logs = production_logs.filter(log_date__gte=actual_chart_start)
        chart_grading_logs = grading_logs.filter(log_date__gte=actual_chart_start)
        actual_rows = (
            chart_logs.values('log_date')
            .annotate(total=models.Sum('eggs_total'))
            .order_by('log_date')
        )
        forecast_rows = (
            overall_forecasts.values('forecast_date')
            .annotate(
                total=models.Sum('predicted_qty'),
                lower=models.Sum('lower_qty'),
                upper=models.Sum('upper_qty'),
            )
            .order_by('forecast_date')
        )
        actual_forecast_payload = build_actual_vs_forecast_payload(actual_rows, forecast_rows)
        hen_payload = build_hen_performance_payload(chart_logs)
        size_mix_payload = build_size_mix_payload(chart_grading_logs, forecasts)
        egg_insights = build_egg_insights(production_logs, grading_logs, forecasts)
        run_summary = build_forecast_run_summary(forecasts, 'predicted_qty')
        latest_model = (
            ModelVersion.objects
            .filter(harvest_forecasts__in=forecasts)
            .order_by('-trained_at', '-pk')
            .distinct()
            .first()
        )
        context.update({
            'flocks': Flock.objects.filter(status='active').order_by('house_no'),
            'selected_flock_id': flock_id,
            'selected_range': selected_range,
            'selected_range_label': selected_range_label,
            'selected_scope': selected_scope,
            'selected_periods': selected_periods,
            'history_days': self._history_days_for_horizon(selected_periods),
            'range_options': self._range_options(),
            'forecast_total': overall_forecasts.aggregate(total=models.Sum('predicted_qty'))['total'] or 0,
            'forecast_rows': run_summary['rows'],
            'forecast_daily_points': run_summary['daily_points'],
            'forecast_categories': run_summary['categories'],
            'forecast_table_limit': FORECAST_TABLE_LIMIT,
            'table_forecasts': forecasts[:FORECAST_TABLE_LIMIT],
            'forecast_start': run_summary['first_row'],
            'forecast_end': run_summary['last_row'],
            'forecast_peak': forecasts.order_by('-predicted_qty').first(),
            'run_summary': run_summary,
            'latest_model': latest_model,
            'chart_payload_json': json.dumps(chart_payload),
            'actual_forecast_payload_json': json.dumps(actual_forecast_payload),
            'hen_payload_json': json.dumps(hen_payload),
            'size_mix_payload_json': json.dumps(size_mix_payload),
            'egg_insights': egg_insights,
        })
        return context

    @staticmethod
    def _range_options():
        return [
            ('week', '1 Week'),
            ('three_weeks', '3 Weeks'),
            ('month', '1 Month'),
            ('three_months', '3 Months'),
            ('custom', 'Custom'),
        ]

    @staticmethod
    def _get_periods(request, range_key):
        custom_start = custom_end = None
        if range_key == 'custom':
            try:
                custom_start = date.fromisoformat(request.POST.get('date_from'))
                custom_end = date.fromisoformat(request.POST.get('date_to'))
            except (TypeError, ValueError):
                return 30
        return ForecastingService.periods_for_range(range_key, custom_start, custom_end)

    @classmethod
    def _get_display_periods(cls, request):
        range_key = request.GET.get('range', 'month')
        if range_key != 'custom':
            return ForecastingService.periods_for_range(range_key)

        try:
            custom_start = date.fromisoformat(request.GET.get('date_from'))
            custom_end = date.fromisoformat(request.GET.get('date_to'))
        except (TypeError, ValueError):
            return ForecastingService.periods_for_range('month')
        return ForecastingService.periods_for_range(range_key, custom_start, custom_end)

    @staticmethod
    def _history_days_for_horizon(periods):
        if periods <= 7:
            return 30
        if periods <= 30:
            return 90
        if periods <= 90:
            return 180
        return 365

    @staticmethod
    def _range_label(range_key, periods):
        labels = {
            'week': 'Next 7 Days',
            'three_weeks': 'Next 3 Weeks',
            'month': 'Next 30 Days',
            'three_months': 'Next 3 Months',
            'custom': f'Custom Horizon ({periods} days)',
        }
        return labels.get(range_key, f'Next {periods} Days')


class HarvestForecastDetailView(ManagerAccessMixin, DetailView):
    model = HarvestForecast
    template_name = 'egg_production/harvest_forecast_detail.html'
    context_object_name = 'forecast'


class ForecastMaintenanceClearView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return ManagerAccessMixin.test_func(self)

    def post(self, request, *args, **kwargs):
        forecast_type = request.POST.get('forecast_type', 'egg')
        mode = request.POST.get('mode', 'clear_all')
        flock_id = request.POST.get('flock_id')
        redirect_to = request.POST.get('next') or reverse_lazy('eggproduction:harvest-forecast-list')

        if mode == 'keep_latest':
            deleted_count = self._keep_latest_only(forecast_type, flock_id)
            messages.success(request, f'Removed {deleted_count} older generated forecast rows and kept the latest run per category.')
            return redirect(redirect_to)

        deleted_count = self._clear_all(forecast_type, flock_id)
        self._delete_orphan_model_versions()
        messages.success(request, f'Cleared {deleted_count} generated forecast rows.')
        return redirect(redirect_to)

    @staticmethod
    def _clear_all(forecast_type, flock_id=None):
        if forecast_type == 'sales':
            queryset = SalesForecast.objects.all()
        elif forecast_type == 'all':
            egg_queryset = HarvestForecast.objects.all()
            if flock_id:
                egg_queryset = egg_queryset.filter(flock_id=flock_id)
            egg_count = egg_queryset.count()
            sales_count = SalesForecast.objects.count()
            egg_queryset.delete()
            SalesForecast.objects.all().delete()
            return egg_count + sales_count
        else:
            queryset = HarvestForecast.objects.all()
            if flock_id:
                queryset = queryset.filter(flock_id=flock_id)

        deleted_count = queryset.count()
        queryset.delete()
        return deleted_count

    @classmethod
    def _keep_latest_only(cls, forecast_type, flock_id=None):
        if forecast_type == 'sales':
            return cls._keep_latest_sales_forecasts()
        if forecast_type == 'all':
            return cls._keep_latest_harvest_forecasts(flock_id) + cls._keep_latest_sales_forecasts()
        return cls._keep_latest_harvest_forecasts(flock_id)

    @staticmethod
    def _keep_latest_harvest_forecasts(flock_id=None):
        queryset = HarvestForecast.objects.select_related('model_version')
        if flock_id:
            queryset = queryset.filter(flock_id=flock_id)

        deleted_count = 0
        groups = queryset.values('flock_id', 'grade').distinct()
        for group in groups:
            group_queryset = queryset.filter(flock_id=group['flock_id'], grade=group['grade'])
            latest_model_id = (
                group_queryset
                .order_by('-model_version__trained_at', '-model_version_id')
                .values_list('model_version_id', flat=True)
                .first()
            )
            if latest_model_id:
                stale_queryset = group_queryset.exclude(model_version_id=latest_model_id)
                deleted_count += stale_queryset.count()
                stale_queryset.delete()

        ForecastMaintenanceClearView._delete_orphan_model_versions()
        return deleted_count

    @staticmethod
    def _keep_latest_sales_forecasts():
        queryset = SalesForecast.objects.select_related('model_version')
        deleted_count = 0
        groups = queryset.values('grade').distinct()
        for group in groups:
            group_queryset = queryset.filter(grade=group['grade'])
            latest_model_id = (
                group_queryset
                .order_by('-model_version__trained_at', '-model_version_id')
                .values_list('model_version_id', flat=True)
                .first()
            )
            if latest_model_id:
                stale_queryset = group_queryset.exclude(model_version_id=latest_model_id)
                deleted_count += stale_queryset.count()
                stale_queryset.delete()

        ForecastMaintenanceClearView._delete_orphan_model_versions()
        return deleted_count

    @staticmethod
    def _delete_orphan_model_versions():
        ModelVersion.objects.filter(
            harvest_forecasts__isnull=True,
            sales_forecasts__isnull=True,
        ).delete()


class TestingDataClearView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return ManagerAccessMixin.test_func(self)

    def post(self, request, *args, **kwargs):
        data_type = request.POST.get('data_type', 'egg')
        redirect_to = request.POST.get('next') or reverse_lazy('eggproduction:harvest-forecast-list')

        if data_type == 'sales':
            sales_count = SalesTransaction.objects.count()
            item_count = SalesItem.objects.count()
            forecast_count = SalesForecast.objects.count()
            SalesTransaction.objects.all().delete()
            SalesForecast.objects.all().delete()
            ForecastMaintenanceClearView._delete_orphan_model_versions()
            messages.success(request, f'Cleared {sales_count} sales transactions, {item_count} sales items, and {forecast_count} sales forecast rows.')
            return redirect(redirect_to)

        production_count = ProductionLog.objects.count()
        grading_count = GradingLog.objects.count()
        forecast_count = HarvestForecast.objects.count()
        ProductionLog.objects.all().delete()
        GradingLog.objects.all().delete()
        HarvestForecast.objects.all().delete()
        ForecastMaintenanceClearView._delete_orphan_model_versions()
        messages.success(request, f'Cleared {production_count} production logs, {grading_count} grading logs, and {forecast_count} egg forecast rows.')
        return redirect(redirect_to)


class ExperimentalForecastingView(ManagerAccessMixin, TemplateView):
    template_name = 'egg_production/experimental_forecasting.html'

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        range_key = request.POST.get('range', 'month')
        context = self.get_context_data(range_key=range_key)

        if action == 'train':
            messages.info(
                request,
                'Training is handled by the Django management command so it does not run inside a browser request.',
                extra_tags='swal',
            )

        if action == 'forecast':
            try:
                context.update(self._build_prediction_context(range_key))
                messages.success(request, 'Experimental forecast generated from the saved SARIMAX model.', extra_tags='swal')
            except Exception as exc:
                logger.exception("Experimental forecast failed")
                messages.error(request, f'Forecast failed: {exc}', extra_tags='swal')

        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        range_key = kwargs.get('range_key') or self.request.GET.get('range', 'month')
        range_label, horizon = EXPERIMENTAL_FORECAST_RANGES.get(range_key, EXPERIMENTAL_FORECAST_RANGES['month'])
        status = self._artifact_status()
        context.update({
            'range_options': EXPERIMENTAL_FORECAST_RANGES.items(),
            'selected_range': range_key,
            'selected_range_label': range_label,
            'selected_horizon': horizon,
            **status,
            'forecast_payload_json': json.dumps({'labels': [], 'forecast': [], 'lower': [], 'upper': []}),
            'forecast_rows': [],
        })
        return context

    @staticmethod
    def _artifact_status():
        base_dir = Path(settings.BASE_DIR).parent
        dataset_path = base_dir / 'ml' / 'data' / 'Egg_Production_Final_Cleaned.csv'
        model_path = base_dir / 'ml' / 'models' / 'sarimax_clean_v1.pkl'
        metadata_path = base_dir / 'ml' / 'models' / 'sarimax_clean_v1.metadata.json'
        metadata = None
        if metadata_path.exists():
            try:
                metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                metadata = None

        return {
            'dataset_path': dataset_path,
            'model_path': model_path,
            'metadata_path': metadata_path,
            'dataset_exists': dataset_path.exists(),
            'model_exists': model_path.exists(),
            'metadata_exists': metadata_path.exists(),
            'model_metadata': metadata,
            'training_command': 'python henalytics/manage.py train_sarimax',
            'prediction_command': 'python henalytics/manage.py generate_experimental_forecast --horizon 30',
        }

    @staticmethod
    def _build_prediction_context(range_key):
        ExperimentalForecastingView._ensure_ml_import_path()
        from ml.predict import forecast

        range_label, horizon = EXPERIMENTAL_FORECAST_RANGES.get(range_key, EXPERIMENTAL_FORECAST_RANGES['month'])
        result = forecast(horizon=horizon)
        rows = result['forecasts']
        payload = {
            'labels': [row['date'] for row in rows],
            'forecast': [round(row['predicted_pieces'], 2) for row in rows],
            'lower': [round(row['lower_bound'], 2) for row in rows],
            'upper': [round(row['upper_bound'], 2) for row in rows],
        }
        return {
            'selected_range': range_key,
            'selected_range_label': range_label,
            'selected_horizon': horizon,
            'forecast_payload_json': json.dumps(payload),
            'forecast_rows': rows,
            'forecast_assumptions': result.get('assumptions'),
        }

    @staticmethod
    def _ensure_ml_import_path():
        project_root = Path(settings.BASE_DIR).parent
        project_root_text = str(project_root)
        if project_root_text not in sys.path:
            sys.path.insert(0, project_root_text)


class SalesForecastListView(ManagerAccessMixin, ListView):
    model = SalesForecast
    template_name = 'egg_production/sales_forecast_list.html'
    context_object_name = 'forecasts'
    ordering = ['-forecast_date']

    def post(self, request, *args, **kwargs):
        if not ManagerAccessMixin.test_func(self):
            messages.error(request, 'Only admin or manager accounts can run forecasts.')
            return redirect('eggproduction:sales-forecast-list')

        range_key = request.POST.get('range', 'month')
        periods = HarvestForecastListView._get_periods(request, range_key)
        include_sizes = request.POST.get('scope', 'both') == 'both'
        result = ForecastingService.generate_sales_forecasts(
            periods=periods,
            user=request.user,
            include_sizes=include_sizes,
        )

        if result['success']:
            messages.success(request, f'Generated {result["created_count"]} sales revenue forecast rows for the next {periods} day{"s" if periods != 1 else ""}.')
        if result['errors']:
            messages.warning(request, '; '.join(result['errors'][:3]))
        redirect_url = reverse_lazy('eggproduction:sales-forecast-list')
        query = QueryDict(mutable=True)
        query['range'] = range_key
        query['scope'] = request.POST.get('scope', 'both')
        if range_key == 'custom':
            if request.POST.get('date_from'):
                query['date_from'] = request.POST.get('date_from')
            if request.POST.get('date_to'):
                query['date_to'] = request.POST.get('date_to')
        return redirect(f'{redirect_url}?{query.urlencode()}')

    def get_queryset(self):
        qs = super().get_queryset().select_related('model_version')
        periods = HarvestForecastListView._get_display_periods(self.request)
        first_date = qs.order_by('forecast_date').values_list('forecast_date', flat=True).first()
        if first_date:
            qs = qs.filter(forecast_date__lte=first_date + timedelta(days=periods - 1))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        forecasts = self.get_queryset()
        chart_payload = build_forecast_chart_payload(forecasts, 'predicted_amount')
        selected_range = self.request.GET.get('range', 'month')
        selected_scope = self.request.GET.get('scope', 'both')
        selected_periods = HarvestForecastListView._get_display_periods(self.request)
        selected_range_label = HarvestForecastListView._range_label(selected_range, selected_periods)
        forecast_start_row = forecasts.order_by('forecast_date').first()
        if forecast_start_row:
            actual_chart_start = forecast_start_row.forecast_date - timedelta(days=HarvestForecastListView._history_days_for_horizon(selected_periods))
        else:
            actual_chart_start = timezone.localdate() - timedelta(days=HarvestForecastListView._history_days_for_horizon(selected_periods))
        actual_sales_rows = (
            SalesItem.objects
            .filter(transaction__sale_date__gte=actual_chart_start)
            .values('transaction__sale_date')
            .annotate(total=models.Sum('amount'))
            .order_by('transaction__sale_date')
        )
        forecast_rows = (
            forecasts.filter(grade='overall')
            .values('forecast_date')
            .annotate(total=models.Sum('predicted_amount'))
            .order_by('forecast_date')
        )
        actual_forecast_payload = build_sales_actual_vs_forecast_payload(actual_sales_rows, forecast_rows)
        sales_insights = build_sales_insights(actual_sales_rows, forecasts)
        run_summary = build_forecast_run_summary(forecasts, 'predicted_amount')
        context.update({
            'range_options': HarvestForecastListView._range_options(),
            'selected_range': selected_range,
            'selected_range_label': selected_range_label,
            'selected_scope': selected_scope,
            'selected_periods': selected_periods,
            'history_days': HarvestForecastListView._history_days_for_horizon(selected_periods),
            'forecast_total': forecasts.aggregate(total=models.Sum('predicted_amount'))['total'] or 0,
            'forecast_rows': run_summary['rows'],
            'forecast_daily_points': run_summary['daily_points'],
            'forecast_categories': run_summary['categories'],
            'forecast_table_limit': FORECAST_TABLE_LIMIT,
            'table_forecasts': forecasts[:FORECAST_TABLE_LIMIT],
            'forecast_start': run_summary['first_row'],
            'forecast_end': run_summary['last_row'],
            'forecast_peak': forecasts.order_by('-predicted_amount').first(),
            'run_summary': run_summary,
            'chart_payload_json': json.dumps(chart_payload),
            'actual_forecast_payload_json': json.dumps(actual_forecast_payload),
            'sales_insights': sales_insights,
        })
        return context


class SalesForecastDetailView(ManagerAccessMixin, DetailView):
    model = SalesForecast
    template_name = 'egg_production/sales_forecast_detail.html'
    context_object_name = 'forecast'


class ModelVersionListView(ManagerAccessMixin, ListView):
    model = ModelVersion
    template_name = 'egg_production/model_version_list.html'
    context_object_name = 'models'
    paginate_by = 10
    ordering = ['-trained_at']


class ModelVersionDetailView(ManagerAccessMixin, DetailView):
    model = ModelVersion
    template_name = 'egg_production/model_version_detail.html'
    context_object_name = 'model'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model = self.get_object()
        context['harvest_forecasts'] = HarvestForecast.objects.filter(model_version=model)[:10]
        context['sales_forecasts'] = SalesForecast.objects.filter(model_version=model)[:10]
        return context


# ======================== API ViewSets ========================

class FlockViewSet(viewsets.ModelViewSet):
    queryset = Flock.objects.all()
    serializer_class = FlockSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['house_no', 'breed_strain']
    ordering_fields = ['date_started', 'status']
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active flocks only"""
        flocks = self.queryset.filter(status='active')
        serializer = self.get_serializer(flocks, many=True)
        return Response(serializer.data)


class ProductionLogViewSet(viewsets.ModelViewSet):
    queryset = ProductionLog.objects.all()
    serializer_class = ProductionLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['flock__house_no']
    ordering_fields = ['log_date', 'eggs_total']
    
    def perform_create(self, serializer):
        serializer.save(entered_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        """Get today's production logs"""
        today = timezone.localdate()
        logs = self.queryset.filter(log_date=today)
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data)


class GradingLogViewSet(viewsets.ModelViewSet):
    queryset = GradingLog.objects.all()
    serializer_class = GradingLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['flock__house_no']
    ordering_fields = ['log_date']
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        """Get today's grading logs"""
        today = timezone.localdate()
        logs = self.queryset.filter(log_date=today)
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data)


class SalesTransactionViewSet(viewsets.ModelViewSet):
    queryset = SalesTransaction.objects.all()
    serializer_class = SalesTransactionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['flock__house_no']
    ordering_fields = ['sale_date']
    
    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        """Get today's sales"""
        today = timezone.localdate()
        sales = self.queryset.filter(sale_date=today).prefetch_related('items')
        serializer = self.get_serializer(sales, many=True)
        return Response(serializer.data)


class SalesItemViewSet(viewsets.ModelViewSet):
    queryset = SalesItem.objects.all()
    serializer_class = SalesItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['transaction__sale_date']


class ModelVersionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ModelVersion.objects.all()
    serializer_class = ModelVersionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['trained_at']
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active model versions"""
        models = self.queryset.filter(is_active=True)
        serializer = self.get_serializer(models, many=True)
        return Response(serializer.data)


class HarvestForecastViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HarvestForecast.objects.all()
    serializer_class = HarvestForecastSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['flock__house_no']
    ordering_fields = ['forecast_date']
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming forecasts"""
        days = int(request.query_params.get('days', 30))
        start_date = timezone.localdate()
        end_date = start_date + timedelta(days=days)
        forecasts = self.queryset.filter(forecast_date__range=[start_date, end_date])
        serializer = self.get_serializer(forecasts, many=True)
        return Response(serializer.data)


class SalesForecastViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SalesForecast.objects.all()
    serializer_class = SalesForecastSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['forecast_date']
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming sales forecasts"""
        days = int(request.query_params.get('days', 30))
        start_date = timezone.localdate()
        end_date = start_date + timedelta(days=days)
        forecasts = self.queryset.filter(forecast_date__range=[start_date, end_date])
        serializer = self.get_serializer(forecasts, many=True)
        return Response(serializer.data)

