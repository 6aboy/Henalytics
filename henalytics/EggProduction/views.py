from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DetailView, DeleteView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib.auth.views import LoginView
from django.db import models, transaction
from django.utils import timezone
from django.conf import settings
from datetime import date, timedelta
import logging
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
from .forms import SalesItemFormSet, SalesTransactionForm
from .forecasting_service import ForecastingService

logger = logging.getLogger(__name__)


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


# Dashboard View
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'index.html'

    def get_period_bounds(self):
        today = timezone.now().date()
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
            today = timezone.now().date()
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
                'today': timezone.now().date(),
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


class FlockDeleteView(ManagerAccessMixin, DeleteView):
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
        today = timezone.now().date()
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
        context['feed_bag_kg'] = getattr(settings, 'HENALYTICS_FEED_BAG_KG', 50)
        context['avg_egg_kg'] = getattr(settings, 'HENALYTICS_AVG_EGG_KG', 0.06)
        return context

    def form_valid(self, form):
        form.instance.update_laying_percentages()
        return super().form_valid(form)


class ProductionLogCreateView(StaffAccessMixin, ProductionLogFormMixin, CreateView):
    model = ProductionLog
    template_name = 'egg_production/production_log_form.html'
    fields = ['flock', 'log_date', 'age_weeks', 'age_days', 'dead_count',
              'culled_count', 'feed_bags', 'eggs_total', 'pct_hen_day', 'pct_hen_housed',
              'fcr', 'remarks']
    success_url = reverse_lazy('eggproduction:production-log-list')
    
    def form_valid(self, form):
        form.instance.entered_by = self.request.user
        return super().form_valid(form)


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
    fields = ['flock', 'log_date', 'age_weeks', 'age_days', 'dead_count',
              'culled_count', 'feed_bags', 'eggs_total', 'pct_hen_day', 'pct_hen_housed',
              'fcr', 'remarks']
    success_url = reverse_lazy('eggproduction:production-log-list')


class ProductionLogDeleteView(StaffAccessMixin, DeleteView):
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


class GradingLogDeleteView(StaffAccessMixin, DeleteView):
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


class SalesTransactionDeleteView(StaffAccessMixin, DeleteView):
    model = SalesTransaction
    template_name = 'egg_production/sales_transaction_confirm_delete.html'
    success_url = reverse_lazy('eggproduction:sales-transaction-list')


# ======================== Sales Item Views ========================

class SalesItemAddView(StaffAccessMixin, CreateView):
    model = SalesItem
    template_name = 'egg_production/sales_item_form.html'
    fields = ['grade', 'quantity_pieces', 'amount']
    
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
    fields = ['grade', 'quantity_pieces', 'amount']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['transaction'] = self.object.transaction
        return context
    
    def get_success_url(self):
        return reverse_lazy('eggproduction:sales-transaction-detail',
                          kwargs={'pk': self.object.transaction.pk})


class SalesItemDeleteView(StaffAccessMixin, DeleteView):
    model = SalesItem
    template_name = 'egg_production/sales_item_confirm_delete.html'
    
    def get_success_url(self):
        return reverse_lazy('eggproduction:sales-transaction-detail',
                          kwargs={'pk': self.object.transaction.pk})


# ======================== Forecast Views ========================

class HarvestForecastListView(LoginRequiredMixin, ListView):
    model = HarvestForecast
    template_name = 'egg_production/harvest_forecast_list.html'
    context_object_name = 'forecasts'
    paginate_by = 20
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
            messages.success(request, f'Generated {total_created} egg forecast rows.')
        if errors:
            messages.warning(request, '; '.join(errors[:3]))
        return redirect('eggproduction:harvest-forecast-list')
    
    def get_queryset(self):
        qs = super().get_queryset().select_related('flock', 'model_version')
        flock_id = self.request.GET.get('flock_id')
        if flock_id:
            qs = qs.filter(flock_id=flock_id)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        forecasts = self.get_queryset()
        upcoming = forecasts.order_by('forecast_date')[:30]
        context.update({
            'flocks': Flock.objects.filter(status='active').order_by('house_no'),
            'range_options': self._range_options(),
            'forecast_total': forecasts.aggregate(total=models.Sum('predicted_qty'))['total'] or 0,
            'forecast_rows': forecasts.count(),
            'forecast_peak': forecasts.order_by('-predicted_qty').first(),
            'chart_labels': [item.forecast_date.strftime('%b %d') for item in upcoming],
            'chart_values': [item.predicted_qty for item in upcoming],
        })
        return context

    @staticmethod
    def _range_options():
        return [
            ('week', '1 Week'),
            ('month', '1 Month'),
            ('three_months', '3 Months'),
            ('six_months', '6 Months'),
            ('year', '1 Year'),
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


class HarvestForecastDetailView(LoginRequiredMixin, DetailView):
    model = HarvestForecast
    template_name = 'egg_production/harvest_forecast_detail.html'
    context_object_name = 'forecast'


class SalesForecastListView(LoginRequiredMixin, ListView):
    model = SalesForecast
    template_name = 'egg_production/sales_forecast_list.html'
    context_object_name = 'forecasts'
    paginate_by = 20
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
            messages.success(request, f'Generated {result["created_count"]} sales revenue forecast rows.')
        if result['errors']:
            messages.warning(request, '; '.join(result['errors'][:3]))
        return redirect('eggproduction:sales-forecast-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        forecasts = self.get_queryset()
        upcoming = forecasts.order_by('forecast_date')[:30]
        context.update({
            'range_options': HarvestForecastListView._range_options(),
            'forecast_total': forecasts.aggregate(total=models.Sum('predicted_amount'))['total'] or 0,
            'forecast_rows': forecasts.count(),
            'forecast_peak': forecasts.order_by('-predicted_amount').first(),
            'chart_labels': [item.forecast_date.strftime('%b %d') for item in upcoming],
            'chart_values': [float(item.predicted_amount) for item in upcoming],
        })
        return context


class SalesForecastDetailView(LoginRequiredMixin, DetailView):
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
        today = timezone.now().date()
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
        today = timezone.now().date()
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
        today = timezone.now().date()
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
        start_date = timezone.now().date()
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
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=days)
        forecasts = self.queryset.filter(forecast_date__range=[start_date, end_date])
        serializer = self.get_serializer(forecasts, many=True)
        return Response(serializer.data)

