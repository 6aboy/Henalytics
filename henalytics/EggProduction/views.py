from django.http import HttpResponse, JsonResponse
from django.http import QueryDict
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DetailView, DeleteView, View
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib.auth.views import LoginView
from django.db import models, transaction
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.conf import settings
from datetime import date, timedelta
import json
import logging
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, BasePermission, SAFE_METHODS

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
        'iso_labels': [item.isoformat() for item in dates],
        'x_min': dates[0].strftime('%b %d, %Y') if dates else None,
        'x_max': dates[-1].strftime('%b %d, %Y') if dates else None,
        'x_min_iso': dates[0].isoformat() if dates else None,
        'x_max_iso': dates[-1].isoformat() if dates else None,
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
        'iso_labels': [item.isoformat() for item in dates],
        'x_min': dates[0].strftime('%b %d, %Y') if dates else None,
        'x_max': dates[-1].strftime('%b %d, %Y') if dates else None,
        'x_min_iso': dates[0].isoformat() if dates else None,
        'x_max_iso': dates[-1].isoformat() if dates else None,
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


def average(values):
    values = [float(value) for value in values if value is not None]
    return sum(values) / len(values) if values else None


def percent_change(previous, current):
    if previous in (None, 0) or current is None:
        return None
    return ((current - previous) / previous) * 100


def build_egg_insights(logs, forecasts):
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

    notes = []
    if latest_hen_housed is not None and latest_hen_housed < 60:
        notes.append('Hen housed production is below 60%, so the flock should be reviewed for culling or replacement planning.')
    if latest_hen_day is not None and latest_hen_day < 60:
        notes.append('Hen day production is also below 60%, indicating weak daily laying performance.')
    if production_change is not None and production_change < -5:
        notes.append(f'Recent actual egg production is {abs(production_change):.1f}% lower than the previous comparable period.')
    if forecast_change is not None and forecast_change < -5:
        notes.append('The forecast continues downward, so the decline is expected to persist if conditions stay similar.')
    if not notes:
        notes.append('No critical signal was detected from the current production and forecast records.')

    return {
        'cards': [status, forecast_card],
        'notes': notes,
        'latest_hen_housed': latest_hen_housed,
        'latest_hen_day': latest_hen_day,
    }


def build_overall_forecast_insights(actual_rows, forecast_rows):
    actual_values = [float(row['total'] or 0) for row in actual_rows]
    forecast_values = [float(row['total'] or 0) for row in forecast_rows]

    recent_actual_avg = average(actual_values[-7:])
    first_forecast_avg = average(forecast_values[:7])
    last_forecast_avg = average(forecast_values[-7:])
    forecast_change = percent_change(first_forecast_avg, last_forecast_avg)
    actual_to_forecast_change = percent_change(recent_actual_avg, first_forecast_avg)

    if not forecast_values:
        return [
            {
                'label': 'Forecast Direction',
                'tone': 'neutral',
                'value': 'No Run',
                'meta': 'Generate a forecast to read the future trend.',
            },
            {
                'label': 'Expected Average',
                'tone': 'neutral',
                'value': 'N/A',
                'meta': 'No future forecast points yet.',
            },
            {
                'label': 'Chart Signal',
                'tone': 'neutral',
                'value': 'Pending',
                'meta': 'The system needs forecast rows before giving a chart interpretation.',
            },
        ]

    if forecast_change is None:
        direction = {
            'label': 'Forecast Direction',
            'tone': 'neutral',
            'value': 'Stable',
            'meta': 'Forecast movement cannot be compared yet.',
        }
    elif forecast_change <= -5:
        direction = {
            'label': 'Forecast Direction',
            'tone': 'danger',
            'value': 'Declining',
            'meta': f'Expected eggs drop by {abs(forecast_change):.1f}% across this horizon.',
        }
    elif forecast_change >= 5:
        direction = {
            'label': 'Forecast Direction',
            'tone': 'good',
            'value': 'Improving',
            'meta': f'Expected eggs rise by {forecast_change:.1f}% across this horizon.',
        }
    else:
        direction = {
            'label': 'Forecast Direction',
            'tone': 'neutral',
            'value': 'Mostly Flat',
            'meta': f'Expected eggs change by only {forecast_change:.1f}% across this horizon.',
        }

    forecast_avg = average(forecast_values)
    average_card = {
        'label': 'Expected Average',
        'tone': 'neutral',
        'value': f'{forecast_avg:,.0f}' if forecast_avg is not None else 'N/A',
        'meta': 'Average eggs per day in the selected forecast range.',
    }

    if actual_to_forecast_change is None:
        signal = {
            'label': 'Chart Signal',
            'tone': 'neutral',
            'value': 'No Baseline',
            'meta': 'More recent actual records are needed for comparison.',
        }
    elif actual_to_forecast_change <= -8:
        signal = {
            'label': 'Chart Signal',
            'tone': 'warning',
            'value': 'Lower Than Recent',
            'meta': f'Forecast starts {abs(actual_to_forecast_change):.1f}% below the recent actual average.',
        }
    elif actual_to_forecast_change >= 8:
        signal = {
            'label': 'Chart Signal',
            'tone': 'good',
            'value': 'Above Recent',
            'meta': f'Forecast starts {actual_to_forecast_change:.1f}% above the recent actual average.',
        }
    else:
        signal = {
            'label': 'Chart Signal',
            'tone': 'neutral',
            'value': 'Close To Recent',
            'meta': f'Forecast starts within {abs(actual_to_forecast_change):.1f}% of the recent actual average.',
        }

    return [direction, average_card, signal]


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
    """Allow staff and admin users to view operational records."""
    def test_func(self):
        user = self.request.user
        try:
            profile = UserProfile.objects.get(user=user)
            return profile.role in ['staff', 'admin']
        except UserProfile.DoesNotExist:
            return user.is_staff or user.is_superuser


class StaffInputAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict record creation, updates, and deletion to staff users."""
    def test_func(self):
        user = self.request.user
        try:
            profile = UserProfile.objects.get(user=user)
            return profile.role == 'staff'
        except UserProfile.DoesNotExist:
            return user.is_staff and not user.is_superuser


class AdminAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Allow admin users to access reports, exports, and forecasting."""
    def test_func(self):
        user = self.request.user
        try:
            profile = UserProfile.objects.get(user=user)
            return profile.role == 'admin' or user.username == 'gabrielnicholas'
        except UserProfile.DoesNotExist:
            return user.username == 'gabrielnicholas'


class StaffCrudAdminReadPermission(BasePermission):
    """Allow staff to write operational records while admin users read only."""
    def _role(self, user):
        try:
            return UserProfile.objects.get(user=user).role
        except UserProfile.DoesNotExist:
            return None

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        role = self._role(user)
        if request.method in SAFE_METHODS:
            return role in ['staff', 'admin'] or user.is_staff or user.is_superuser

        if role is not None:
            return role == 'staff'
        return user.is_staff and not user.is_superuser


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
        period = self.request.GET.get('period', 'last_30')
        start = None
        end = today
        selected_month = self.request.GET.get('month_value') or today.strftime('%Y-%m')

        if period == 'today':
            start = today
        elif period == 'last_30':
            start = today - timedelta(days=30)
        elif period == 'month':
            start = today.replace(day=1)
        elif period == 'last_month':
            first_this_month = today.replace(day=1)
            end = first_this_month - timedelta(days=1)
            start = end.replace(day=1)
        elif period == 'specific_month':
            try:
                year, month = [int(part) for part in selected_month.split('-', 1)]
                start = date(year, month, 1)
                end = date(year + (month // 12), (month % 12) + 1, 1) - timedelta(days=1)
            except (TypeError, ValueError):
                period = 'month'
                start = today.replace(day=1)
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
            period = 'last_30'
            start = today - timedelta(days=30)

        labels = {
            'today': 'Today',
            'last_30': 'Last 30 Days',
            'month': 'This Month',
            'last_month': 'Last Month',
            'specific_month': start.strftime('%B %Y') if start else 'Selected Month',
            'six_months': 'Last 6 Months',
            'year': 'This Year',
            'all': 'All Records',
            'custom': 'Custom Range',
        }
        return period, start, end, labels.get(period, 'Last 30 Days')

    @staticmethod
    def filter_by_date(queryset, field_name, start, end):
        if start:
            queryset = queryset.filter(**{f'{field_name}__gte': start})
        if end:
            queryset = queryset.filter(**{f'{field_name}__lte': end})
        return queryset

    @staticmethod
    def previous_period_bounds(start, end):
        if not start or not end:
            return None, None
        span = (end - start).days + 1
        previous_end = start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=span - 1)
        return previous_start, previous_end

    @staticmethod
    def percent_change(current, previous):
        current = float(current or 0)
        previous = float(previous or 0)
        if previous == 0:
            return None
        return round(((current - previous) / previous) * 100, 1)

    @staticmethod
    def format_change(change):
        if change is None:
            return 'No previous period'
        sign = '+' if change > 0 else ''
        return f'{sign}{change}% vs previous period'

    @staticmethod
    def change_tone(change, inverse=False):
        if change is None or change == 0:
            return 'neutral'
        improved = change > 0
        if inverse:
            improved = not improved
        return 'good' if improved else 'danger'

    @classmethod
    def build_monthly_payload(cls):
        production_rows = list(
            ProductionLog.objects
            .filter(flock__status='active')
            .annotate(month=TruncMonth('log_date'))
            .values('month')
            .annotate(
                eggs=models.Sum('eggs_total'),
                feed=models.Sum('feed_bags'),
                losses=models.Sum(models.F('dead_count') + models.F('culled_count')),
                hen_day=models.Avg('pct_hen_day'),
                hen_housed=models.Avg('pct_hen_housed'),
                fcr=models.Avg('fcr'),
            )
            .order_by('month')
        )
        revenue_by_month = {
            row['month']: float(row['revenue'] or 0)
            for row in (
                SalesItem.objects
                .annotate(month=TruncMonth('transaction__sale_date'))
                .values('month')
                .annotate(revenue=models.Sum('amount'))
                .order_by('month')
            )
        }
        cracked_by_month = {
            row['month']: {
                'broken': float(row['broken'] or 0),
                'total': float(row['total'] or 0),
            }
            for row in (
                GradingLog.objects
                .annotate(month=TruncMonth('log_date'))
                .values('month')
                .annotate(broken=models.Sum('eggs_broken'), total=models.Sum('eggs_total'))
                .order_by('month')
            )
        }
        labels = [row['month'].strftime('%b %Y') for row in production_rows]
        iso_labels = [
            (row['month'].date() if hasattr(row['month'], 'date') else row['month']).isoformat()
            for row in production_rows
        ]
        cracked_loss = []
        for row in production_rows:
            cracked = cracked_by_month.get(row['month'], {'broken': 0, 'total': 0})
            cracked_loss.append((cracked['broken'] / cracked['total'] * 100) if cracked['total'] else 0)

        return {
            'labels': labels,
            'iso_labels': iso_labels,
            'charts': {
                'monthly_eggs': {
                    'title': 'Monthly Egg Production',
                    'description': 'Total eggs grouped by month to show longer-term production direction.',
                    'unit': 'eggs',
                    'color': '#3360cf',
                    'type': 'bar',
                    'values': [float(row['eggs'] or 0) for row in production_rows],
                },
                'monthly_revenue': {
                    'title': 'Monthly Revenue',
                    'description': 'Sales amount grouped by month for financial performance tracking.',
                    'unit': 'peso',
                    'color': '#12a150',
                    'type': 'bar',
                    'values': [revenue_by_month.get(row['month'], 0) for row in production_rows],
                },
                'monthly_hen_day': {
                    'title': 'Monthly Hen Day',
                    'description': 'Average hen-day percentage per month.',
                    'unit': '%',
                    'color': '#7c3aed',
                    'type': 'line',
                    'values': [float(row['hen_day'] or 0) for row in production_rows],
                },
                'monthly_hen_housed': {
                    'title': 'Monthly Hen Housed',
                    'description': 'Average hen-housed percentage per month with the 60% warning threshold.',
                    'unit': '%',
                    'color': '#0f9f6e',
                    'type': 'line',
                    'values': [float(row['hen_housed'] or 0) for row in production_rows],
                    'threshold': [60 for _row in production_rows],
                    'threshold_label': '60% threshold',
                },
                'monthly_feed': {
                    'title': 'Monthly Feed Use',
                    'description': 'Total feed bags consumed per month.',
                    'unit': 'bags',
                    'color': '#e88411',
                    'type': 'bar',
                    'values': [float(row['feed'] or 0) for row in production_rows],
                },
                'monthly_losses': {
                    'title': 'Monthly Flock Losses',
                    'description': 'Dead and culled hens grouped by month.',
                    'unit': 'hens',
                    'color': '#d92d20',
                    'type': 'bar',
                    'values': [float(row['losses'] or 0) for row in production_rows],
                },
                'monthly_cracked': {
                    'title': 'Monthly Cracked Egg Loss',
                    'description': 'Cracked eggs as a percentage of graded eggs each month.',
                    'unit': '%',
                    'color': '#db2777',
                    'type': 'line',
                    'values': cracked_loss,
                },
            },
        }

    @classmethod
    def build_monthly_notes(cls, monthly_payload):
        charts = monthly_payload.get('charts', {})
        eggs = charts.get('monthly_eggs', {}).get('values', [])
        hen_housed = charts.get('monthly_hen_housed', {}).get('values', [])
        revenue = charts.get('monthly_revenue', {}).get('values', [])
        notes = []
        if len(eggs) >= 2:
            change = cls.percent_change(eggs[-1], eggs[-2])
            direction = 'increased' if change and change > 0 else 'declined' if change and change < 0 else 'remained stable'
            notes.append(f'Egg production {direction} compared with the previous month ({cls.format_change(change)}).')
        if hen_housed:
            latest_hh = hen_housed[-1]
            if latest_hh < 60:
                notes.append('Latest monthly hen-housed performance is below 60%, so the flock should be reviewed.')
            else:
                notes.append('Latest monthly hen-housed performance is above the 60% warning threshold.')
        if len(revenue) >= 2:
            change = cls.percent_change(revenue[-1], revenue[-2])
            notes.append(f'Revenue movement: {cls.format_change(change)}.')
        if not notes:
            notes.append('Monthly analytics will become more useful once more month-level records are available.')
        return notes

    @classmethod
    def build_monthly_summary(cls, monthly_payload):
        labels = monthly_payload.get('labels', [])
        charts = monthly_payload.get('charts', {})
        eggs = charts.get('monthly_eggs', {}).get('values', [])
        revenue = charts.get('monthly_revenue', {}).get('values', [])
        hen_housed = charts.get('monthly_hen_housed', {}).get('values', [])
        latest_eggs = eggs[-1] if eggs else 0
        latest_revenue = revenue[-1] if revenue else 0
        latest_housed = hen_housed[-1] if hen_housed else 0
        egg_change = cls.percent_change(latest_eggs, eggs[-2]) if len(eggs) >= 2 else None
        return {
            'month_label': labels[-1] if labels else 'No monthly records',
            'latest_eggs': latest_eggs,
            'latest_revenue': latest_revenue,
            'latest_housed': round(latest_housed, 1) if latest_housed else 0,
            'egg_change_label': cls.format_change(egg_change),
            'egg_change_tone': cls.change_tone(egg_change),
        }
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            today = timezone.localdate()
            last_7_days = today - timedelta(days=7)
            last_30_days = today - timedelta(days=30)
            last_60_days = today - timedelta(days=60)
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
            previous_start, previous_end = self.previous_period_bounds(date_from, date_to)
            previous_logs = self.filter_by_date(ProductionLog.objects.all(), 'log_date', previous_start, previous_end)
            previous_sales_items = self.filter_by_date(
                SalesItem.objects.all(),
                'transaction__sale_date',
                previous_start,
                previous_end,
            )
            previous_egg_total = previous_logs.aggregate(total=models.Sum('eggs_total'))['total'] or 0
            previous_feed_total = previous_logs.aggregate(total=models.Sum('feed_bags'))['total'] or 0
            previous_losses = previous_logs.aggregate(
                lost=models.Sum(models.F('dead_count') + models.F('culled_count'))
            )['lost'] or 0
            previous_revenue = previous_sales_items.aggregate(total=models.Sum('amount'))['total'] or 0
            period_egg_change = self.percent_change(period_egg_total, previous_egg_total)
            period_revenue_change = self.percent_change(period_revenue, previous_revenue)
            period_feed_change = self.percent_change(period_feed_total, previous_feed_total)
            period_loss_change = self.percent_change(period_losses, previous_losses)
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
            recent_losses_30d = ProductionLog.objects.filter(log_date__gte=last_30_days).aggregate(
                lost=models.Sum(models.F('dead_count') + models.F('culled_count'))
            )['lost'] or 0
            recent_losses_60d = ProductionLog.objects.filter(log_date__gte=last_60_days).aggregate(
                lost=models.Sum(models.F('dead_count') + models.F('culled_count'))
            )['lost'] or 0
            chart_rows = list(
                ProductionLog.objects
                .filter(flock__status='active')
                .values('log_date')
                .annotate(
                    eggs=models.Sum('eggs_total'),
                    hen_housed=models.Avg('pct_hen_housed'),
                    hen_day=models.Avg('pct_hen_day'),
                    feed=models.Sum('feed_bags'),
                    losses=models.Sum(models.F('dead_count') + models.F('culled_count')),
                )
                .order_by('log_date')
            )
            dashboard_chart_payload = {
                'labels': [row['log_date'].strftime('%b %d, %Y') for row in chart_rows],
                'iso_labels': [row['log_date'].isoformat() for row in chart_rows],
                'charts': {
                    'eggs': {
                        'title': 'Egg Production Trend',
                        'description': 'Daily total eggs recorded in the database.',
                        'unit': 'eggs',
                        'color': '#3360cf',
                        'values': [float(row['eggs'] or 0) for row in chart_rows],
                    },
                    'hen_housed': {
                        'title': 'Hen Housed Performance',
                        'description': 'Daily hen-housed percentage compared with the 60% warning threshold.',
                        'unit': '%',
                        'color': '#12a150',
                        'values': [float(row['hen_housed'] or 0) for row in chart_rows],
                        'threshold': [60 for _row in chart_rows],
                        'threshold_label': '60% threshold',
                    },
                    'hen_day': {
                        'title': 'Hen Day Laying Rate',
                        'description': 'Daily hen-day percentage from production records.',
                        'unit': '%',
                        'color': '#7c3aed',
                        'values': [float(row['hen_day'] or 0) for row in chart_rows],
                    },
                    'feed': {
                        'title': 'Feed Consumption',
                        'description': 'Daily feed bags recorded in the database.',
                        'unit': 'bags',
                        'color': '#e88411',
                        'values': [float(row['feed'] or 0) for row in chart_rows],
                    },
                    'losses': {
                        'title': 'Mortality and Cull Trend',
                        'description': 'Daily dead and culled hens from production records.',
                        'unit': 'hens',
                        'color': '#d92d20',
                        'values': [float(row['losses'] or 0) for row in chart_rows],
                    },
                },
            }
            monthly_payload = self.build_monthly_payload()
            monthly_summary = self.build_monthly_summary(monthly_payload)
            month_value = self.request.GET.get('month_value') or today.strftime('%Y-%m')

            context.update({
                'today': today,
                'dashboard_period': period,
                'dashboard_date_from': date_from,
                'dashboard_date_to': date_to,
                'dashboard_month_value': month_value,
                'dashboard_period_label': period_label,
                'active_flocks': active_flocks,
                'today_production': today_production,
                'period_egg_total': period_egg_total,
                'period_feed_total': period_feed_total,
                'period_losses': period_losses,
                'period_revenue': float(period_revenue),
                'period_egg_change_label': self.format_change(period_egg_change),
                'period_egg_change_tone': self.change_tone(period_egg_change),
                'period_revenue_change_label': self.format_change(period_revenue_change),
                'period_revenue_change_tone': self.change_tone(period_revenue_change),
                'period_feed_change_label': self.format_change(period_feed_change),
                'period_feed_change_tone': self.change_tone(period_feed_change, inverse=True),
                'period_loss_change_label': self.format_change(period_loss_change),
                'period_loss_change_tone': self.change_tone(period_loss_change, inverse=True),
                'today_sales': SalesTransaction.objects.filter(sale_date=today).count(),
                'total_revenue': float(weekly_revenue),
                'total_hens': total_hens,
                'weekly_revenue': float(weekly_revenue),
                'avg_fcr_30d': round(avg_fcr_30d, 2) if avg_fcr_30d else 0,
                'avg_lay_rate_30d': round(avg_lay_rate_30d, 1) if avg_lay_rate_30d else 0,
                'feed_consumed_30d': feed_consumed_30d,
                'cracked_egg_loss': round(cracked_egg_loss, 1),
                'recent_losses_7d': recent_losses_7d,
                'recent_losses_30d': recent_losses_30d,
                'recent_losses_60d': recent_losses_60d,
                'dashboard_charts_payload_json': json.dumps(dashboard_chart_payload),
                'monthly_dashboard_payload_json': json.dumps(monthly_payload),
                'monthly_dashboard_notes': self.build_monthly_notes(monthly_payload),
                'monthly_dashboard_summary': monthly_summary,
                'hen_housed_payload_json': json.dumps(dashboard_chart_payload['charts']['hen_housed']),
            })
        except Exception as e:
            logger.exception("Dashboard error: %s", e)
            context.update({
                'today': timezone.localdate(),
                'dashboard_period': 'last_30',
                'dashboard_date_from': None,
                'dashboard_date_to': None,
                'dashboard_period_label': 'Last 30 Days',
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
                'recent_losses_30d': 0,
                'recent_losses_60d': 0,
                'dashboard_charts_payload_json': json.dumps({'labels': [], 'iso_labels': [], 'charts': {}}),
                'monthly_dashboard_payload_json': json.dumps({'labels': [], 'iso_labels': [], 'charts': {}}),
                'monthly_dashboard_notes': ['Monthly analytics could not be loaded.'],
                'monthly_dashboard_summary': {
                    'month_label': 'No monthly records',
                    'latest_eggs': 0,
                    'latest_revenue': 0,
                    'latest_housed': 0,
                    'egg_change_label': 'No previous period',
                    'egg_change_tone': 'neutral',
                },
                'hen_housed_payload_json': json.dumps({'labels': [], 'actual': [], 'threshold': []}),
            })
        return context


# ======================== Flock Views ========================

class FlockListView(LoginRequiredMixin, ListView):
    model = Flock
    template_name = 'egg_production/flock_list.html'
    context_object_name = 'flocks'
    ordering = ['-date_started']

    def get_queryset(self):
        flocks = list(super().get_queryset())
        today = timezone.localdate()
        for flock in flocks:
            latest_log = (
                ProductionLog.objects
                .filter(flock=flock)
                .order_by('-log_date', '-pk')
                .first()
            )
            totals = ProductionLog.objects.filter(flock=flock).aggregate(
                dead=models.Sum('dead_count'),
                culled=models.Sum('culled_count'),
                feed=models.Sum('feed_bags'),
            )
            age_days = (
                latest_log.age_days
                if latest_log
                else max((today - flock.date_started).days, 0)
            )
            flock.table_age_weeks = age_days // 7
            flock.table_age_days = age_days
            flock.table_current_population = (
                latest_log.hen_count
                if latest_log
                else flock.initial_hen_count
            )
            flock.table_dead_count = totals['dead'] or 0
            flock.table_culled_count = totals['culled'] or 0
            flock.table_feed_bags = totals['feed'] or 0
        return flocks


class FlockCreateView(StaffInputAccessMixin, CreateView):
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


class FlockUpdateView(StaffInputAccessMixin, UpdateView):
    model = Flock
    template_name = 'egg_production/flock_form.html'
    fields = ['house_no', 'breed_strain', 'date_started', 'initial_hen_count', 'status', 'notes']
    success_url = reverse_lazy('eggproduction:flock-list')


class FlockDeleteView(DirectDeleteOnlyMixin, StaffInputAccessMixin, DeleteView):
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


class ProductionLogCreateView(StaffInputAccessMixin, ProductionLogFormMixin, CreateView):
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


class ProductionLogUpdateView(StaffInputAccessMixin, ProductionLogFormMixin, UpdateView):
    model = ProductionLog
    template_name = 'egg_production/production_log_form.html'
    form_class = ProductionLogForm
    success_url = reverse_lazy('eggproduction:production-log-list')


class ProductionLogDeleteView(DirectDeleteOnlyMixin, StaffInputAccessMixin, DeleteView):
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


class GradingLogCreateView(StaffInputAccessMixin, CreateView):
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


class GradingLogUpdateView(StaffInputAccessMixin, UpdateView):
    model = GradingLog
    template_name = 'egg_production/grading_log_form.html'
    fields = ['flock', 'log_date', 'age_weeks', 'eggs_total', 'eggs_aa', 'eggs_a',
              'eggs_b', 'eggs_small', 'eggs_broken', 'eggs_decode', 'eggs_source']
    success_url = reverse_lazy('eggproduction:grading-log-list')


class GradingLogDeleteView(DirectDeleteOnlyMixin, StaffInputAccessMixin, DeleteView):
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


class SalesTransactionCreateView(StaffInputAccessMixin, CreateView):
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


class SalesTransactionUpdateView(StaffInputAccessMixin, UpdateView):
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


class SalesTransactionDeleteView(DirectDeleteOnlyMixin, StaffInputAccessMixin, DeleteView):
    model = SalesTransaction
    template_name = 'egg_production/sales_transaction_confirm_delete.html'
    success_url = reverse_lazy('eggproduction:sales-transaction-list')


# ======================== Sales Item Views ========================

class SalesItemAddView(StaffInputAccessMixin, CreateView):
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


class SalesItemUpdateView(StaffInputAccessMixin, UpdateView):
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


class SalesItemDeleteView(DirectDeleteOnlyMixin, StaffInputAccessMixin, DeleteView):
    model = SalesItem
    template_name = 'egg_production/sales_item_confirm_delete.html'
    
    def get_success_url(self):
        return reverse_lazy('eggproduction:sales-transaction-detail',
                          kwargs={'pk': self.object.transaction.pk})


# ======================== Forecast Views ========================

class HarvestForecastListView(AdminAccessMixin, ListView):
    model = HarvestForecast
    template_name = 'egg_production/harvest_forecast_list.html'
    context_object_name = 'forecasts'
    ordering = ['-forecast_date']

    def post(self, request, *args, **kwargs):
        if not AdminAccessMixin.test_func(self):
            messages.error(request, 'Only admin accounts can run forecasts.')
            return redirect('eggproduction:harvest-forecast-list')

        flock_id = request.POST.get('flock_id')
        range_key = request.POST.get('range', 'month')
        periods = self._get_periods(request, range_key)

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
            )
            total_created += result['created_count']
            errors.extend([f'House {flock.house_no} {error}' for error in result['errors']])

        if total_created:
            messages.success(
                request,
                f'Generated {total_created} egg forecast rows for the next {periods} day{"s" if periods != 1 else ""}.',
                extra_tags='forecast-run-card',
            )
        if errors:
            messages.warning(request, '; '.join(errors[:3]))
        redirect_url = reverse_lazy('eggproduction:harvest-forecast-list')
        query = QueryDict(mutable=True)
        if flock_id:
            query['flock_id'] = flock_id
        query['range'] = range_key
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
        latest_actual_date = self._latest_actual_date_for_request()
        if latest_actual_date:
            qs = qs.filter(forecast_date__gte=latest_actual_date + timedelta(days=1))
        periods = self._get_display_periods(self.request)
        first_date = qs.order_by('forecast_date').values_list('forecast_date', flat=True).first()
        if first_date:
            qs = qs.filter(forecast_date__lte=first_date + timedelta(days=periods - 1))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        forecasts = self.get_queryset()
        overall_forecasts = forecasts.filter(grade='overall')
        flock_id = self.request.GET.get('flock_id', '')
        selected_range = self.request.GET.get('range', 'month')
        selected_periods = self._get_display_periods(self.request)
        selected_range_label = self._range_label(selected_range, selected_periods)
        production_logs = ProductionLog.objects.select_related('flock')
        if flock_id:
            production_logs = production_logs.filter(flock_id=flock_id)
        else:
            production_logs = production_logs.filter(flock__status='active')

        forecast_start_row = forecasts.order_by('forecast_date').first()
        if forecast_start_row:
            actual_chart_start = forecast_start_row.forecast_date - timedelta(days=self._history_days_for_horizon(selected_periods))
        elif self._latest_actual_date_for_request():
            actual_chart_start = self._latest_actual_date_for_request() - timedelta(days=self._history_days_for_horizon(selected_periods))
        else:
            actual_chart_start = timezone.localdate() - timedelta(days=self._history_days_for_horizon(selected_periods))
        chart_logs = production_logs.filter(log_date__gte=actual_chart_start)
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
        egg_insights = build_egg_insights(production_logs, forecasts)
        run_summary = build_forecast_run_summary(forecasts, 'predicted_qty')
        latest_model = (
            ModelVersion.objects
            .filter(harvest_forecasts__in=forecasts)
            .order_by('-trained_at', '-pk')
            .distinct()
            .first()
        )
        model_comparison = latest_model.comparison_summary if latest_model and latest_model.comparison_summary else {}
        context.update({
            'flocks': Flock.objects.filter(status='active').order_by('house_no'),
            'selected_flock_id': flock_id,
            'selected_range': selected_range,
            'selected_range_label': selected_range_label,
            'selected_periods': selected_periods,
            'history_days': self._history_days_for_horizon(selected_periods),
            'range_options': self._range_options(),
            'forecast_total': overall_forecasts.aggregate(total=models.Sum('predicted_qty'))['total'] or 0,
            'forecast_rows': run_summary['rows'],
            'forecast_daily_points': run_summary['daily_points'],
            'forecast_table_limit': FORECAST_TABLE_LIMIT,
            'table_forecasts': forecasts[:FORECAST_TABLE_LIMIT],
            'forecast_start': run_summary['first_row'],
            'forecast_end': run_summary['last_row'],
            'forecast_peak': forecasts.order_by('-predicted_qty').first(),
            'run_summary': run_summary,
            'latest_model': latest_model,
            'model_comparison': model_comparison,
            'actual_forecast_payload_json': json.dumps(actual_forecast_payload),
            'hen_payload_json': json.dumps(hen_payload),
            'egg_insights': egg_insights,
        })
        return context

    def _latest_actual_date_for_request(self):
        production_logs = ProductionLog.objects.all()
        flock_id = self.request.GET.get('flock_id')
        if flock_id:
            production_logs = production_logs.filter(flock_id=flock_id)
        else:
            production_logs = production_logs.filter(flock__status='active')
        return production_logs.order_by('-log_date').values_list('log_date', flat=True).first()

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


class HarvestForecastDetailView(AdminAccessMixin, DetailView):
    model = HarvestForecast
    template_name = 'egg_production/harvest_forecast_detail.html'
    context_object_name = 'forecast'


class ForecastMaintenanceClearView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return AdminAccessMixin.test_func(self)

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
        return AdminAccessMixin.test_func(self)

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


class ExperimentalForecastingView(AdminAccessMixin, TemplateView):
    template_name = 'egg_production/experimental_forecasting.html'

    def post(self, request, *args, **kwargs):
        range_key = request.POST.get('range', 'month')
        flock_id = request.POST.get('flock_id', '')
        scope = 'overall'
        periods = ForecastingService.periods_for_range(range_key)
        errors = []
        created_count = 0

        flocks = Flock.objects.filter(status='active').order_by('house_no')
        if flock_id:
            flocks = flocks.filter(pk=flock_id)

        for flock in flocks:
            result = ForecastingService.generate_egg_forecasts(
                flock=flock,
                periods=periods,
                user=request.user,
                include_sizes=False,
            )
            created_count += result['created_count']
            errors.extend([f'House {flock.house_no}: {error}' for error in result['errors']])

        if created_count:
            messages.success(
                request,
                f'Generated {created_count} database forecast rows.',
                extra_tags='forecast-run-card',
            )
        if errors:
            messages.warning(request, '; '.join(errors[:3]), extra_tags='swal')

        query = QueryDict(mutable=True)
        query['range'] = range_key
        query['scope'] = scope
        if flock_id:
            query['flock_id'] = flock_id
        return redirect(f'{reverse_lazy("eggproduction:experimental-forecasting")}?{query.urlencode()}')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        range_key = self.request.GET.get('range', 'month')
        flock_id = self.request.GET.get('flock_id', '')
        scope = 'overall'
        range_label, horizon = EXPERIMENTAL_FORECAST_RANGES.get(range_key, EXPERIMENTAL_FORECAST_RANGES['month'])
        forecasts = HarvestForecast.objects.select_related('flock', 'model_version')
        production_logs = ProductionLog.objects.select_related('flock')
        if flock_id:
            forecasts = forecasts.filter(flock_id=flock_id)
            production_logs = production_logs.filter(flock_id=flock_id)
        else:
            forecasts = forecasts.filter(flock__status='active')
            production_logs = production_logs.filter(flock__status='active')

        forecasts = forecasts.filter(grade='overall')
        first_forecast_date = forecasts.order_by('forecast_date').values_list('forecast_date', flat=True).first()
        if first_forecast_date:
            forecasts = forecasts.filter(forecast_date__lte=first_forecast_date + timedelta(days=horizon - 1))
            actual_start = first_forecast_date - timedelta(days=self._history_days_for_horizon(horizon))
        else:
            actual_start = timezone.localdate() - timedelta(days=self._history_days_for_horizon(horizon))

        chart_logs = production_logs.filter(log_date__gte=actual_start)
        overall_forecasts = forecasts
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
        forecast_insights = build_overall_forecast_insights(actual_rows, forecast_rows)
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
            'selected_scope': scope,
            'range_options': EXPERIMENTAL_FORECAST_RANGES.items(),
            'selected_range': range_key,
            'selected_range_label': range_label,
            'selected_horizon': horizon,
            'history_days': self._history_days_for_horizon(horizon),
            'forecast_total': overall_forecasts.aggregate(total=models.Sum('predicted_qty'))['total'] or 0,
            'forecast_rows': run_summary['rows'],
            'forecast_daily_points': run_summary['daily_points'],
            'forecast_categories': run_summary['categories'],
            'forecast_start': run_summary['first_row'],
            'forecast_end': run_summary['last_row'],
            'forecast_peak': forecasts.order_by('-predicted_qty').first(),
            'forecast_insights': forecast_insights,
            'latest_model': latest_model,
            'table_forecasts': forecasts[:FORECAST_TABLE_LIMIT],
            'forecast_table_limit': FORECAST_TABLE_LIMIT,
            'forecast_payload_json': json.dumps(build_actual_vs_forecast_payload(actual_rows, forecast_rows)),
        })
        return context

    @staticmethod
    def _history_days_for_horizon(horizon):
        if horizon <= 7:
            return 30
        if horizon <= 30:
            return 60
        return 120


class SalesForecastListView(AdminAccessMixin, ListView):
    model = SalesForecast
    template_name = 'egg_production/sales_forecast_list.html'
    context_object_name = 'forecasts'
    ordering = ['-forecast_date']

    def post(self, request, *args, **kwargs):
        if not AdminAccessMixin.test_func(self):
            messages.error(request, 'Only admin accounts can run forecasts.')
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
            messages.success(
                request,
                f'Generated {result["created_count"]} sales revenue forecast rows for the next {periods} day{"s" if periods != 1 else ""}.',
                extra_tags='forecast-run-card',
            )
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
        latest_model = (
            ModelVersion.objects
            .filter(sales_forecasts__in=forecasts)
            .order_by('-trained_at', '-pk')
            .distinct()
            .first()
        )
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
            'latest_model': latest_model,
        })
        return context


class SalesForecastDetailView(AdminAccessMixin, DetailView):
    model = SalesForecast
    template_name = 'egg_production/sales_forecast_detail.html'
    context_object_name = 'forecast'


class ModelVersionListView(AdminAccessMixin, ListView):
    model = ModelVersion
    template_name = 'egg_production/model_version_list.html'
    context_object_name = 'models'
    paginate_by = 10
    ordering = ['-trained_at']


class ModelVersionDetailView(AdminAccessMixin, DetailView):
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
    permission_classes = [StaffCrudAdminReadPermission]
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
    permission_classes = [StaffCrudAdminReadPermission]
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
    permission_classes = [StaffCrudAdminReadPermission]
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
    permission_classes = [StaffCrudAdminReadPermission]
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
    permission_classes = [StaffCrudAdminReadPermission]
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

