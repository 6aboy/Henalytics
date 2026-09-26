from django import forms
from django.forms import inlineformset_factory
from django.db.models import Q
from django.utils import timezone

from .models import Flock, ProductionLog, SalesItem, SalesTransaction


def active_flocks_for_instance(instance=None):
    queryset = Flock.objects.filter(status='active')
    flock_id = getattr(instance, 'flock_id', None)
    if flock_id:
        queryset = Flock.objects.filter(Q(status='active') | Q(pk=flock_id))
    return queryset.order_by('house_no', '-date_started', 'id')


class ProductionLogForm(forms.ModelForm):
    class Meta:
        model = ProductionLog
        fields = [
            'flock',
            'log_date',
            'dead_count',
            'culled_count',
            'feed_bags',
            'eggs_total',
            'remarks',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields['flock'].empty_label = 'Choose a Flock'
        self.fields['flock'].queryset = active_flocks_for_instance(self.instance)
        self.fields['remarks'].label = 'Notes'
        self.fields['remarks'].widget.attrs.update({
            'class': 'form-control compact-note-input',
            'rows': 2,
        })
        self.fields['log_date'].initial = self.initial.get('log_date') or today
        self.fields['log_date'].widget.input_type = 'date'
        self.fields['log_date'].widget.attrs['max'] = today.isoformat()

    def clean_log_date(self):
        log_date = self.cleaned_data['log_date']
        today = timezone.localdate()
        if log_date > today:
            raise forms.ValidationError('Log date cannot be in the future.')
        return log_date

    def clean(self):
        cleaned_data = super().clean()
        flock = cleaned_data.get('flock')
        log_date = cleaned_data.get('log_date')
        dead_count = cleaned_data.get('dead_count') or 0
        culled_count = cleaned_data.get('culled_count') or 0
        eggs_total = cleaned_data.get('eggs_total') or 0
        if flock and log_date and log_date < flock.date_started:
            self.add_error('log_date', 'Log date cannot be earlier than the flock start date.')
        if flock and log_date:
            previous_logs = ProductionLog.objects.filter(
                flock=flock,
                log_date__lt=log_date,
            )
            if self.instance and self.instance.pk:
                previous_logs = previous_logs.exclude(pk=self.instance.pk)

            previous_dead = sum(log.dead_count or 0 for log in previous_logs)
            previous_culled = sum(log.culled_count or 0 for log in previous_logs)
            available_hens_before_log = max(
                flock.initial_hen_count - previous_dead - previous_culled,
                0,
            )
            current_losses = dead_count + culled_count
            live_hens_after_losses = max(available_hens_before_log - current_losses, 0)

            if current_losses > available_hens_before_log:
                self.add_error(
                    'dead_count',
                    f'Dead and culled count cannot exceed the available live hens ({available_hens_before_log:,}).',
                )
                self.add_error(
                    'culled_count',
                    f'Dead and culled count cannot exceed the available live hens ({available_hens_before_log:,}).',
                )
            if eggs_total > live_hens_after_losses:
                self.add_error(
                    'eggs_total',
                    f'Eggs total cannot exceed the calculated live hen count for this date ({live_hens_after_losses:,}).',
                )
        return cleaned_data


class ProductionLogImportForm(forms.Form):
    DATE_MODE_CHOICES = (
        ('clsu_markers', 'CLSU month markers'),
        ('stored', 'Use file dates exactly'),
    )
    CONFLICT_STRATEGY_CHOICES = (
        ('update', 'Add missing and update existing'),
        ('skip', 'Add missing only'),
        ('replace_range', 'Replace selected date range'),
    )

    flock = forms.ModelChoiceField(
        queryset=Flock.objects.none(),
        empty_label='Choose a Flock',
    )
    data_file = forms.FileField(
        label='Excel or CSV file',
        help_text='Accepted files: .xlsx, .xlsm, .csv',
    )
    date_mode = forms.ChoiceField(
        choices=DATE_MODE_CHOICES,
        initial='clsu_markers',
        label='Date reading',
        help_text='Use CLSU month markers when dates like 1/6/2026 mean June 1, 2026.',
    )
    conflict_strategy = forms.ChoiceField(
        choices=CONFLICT_STRATEGY_CHOICES,
        initial='update',
        label='Existing records',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['flock'].queryset = active_flocks_for_instance()
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        self.fields['flock'].widget.attrs['class'] = 'form-select'
        self.fields['date_mode'].widget.attrs['class'] = 'form-select'
        self.fields['conflict_strategy'].widget.attrs['class'] = 'form-select'

    def clean_data_file(self):
        data_file = self.cleaned_data['data_file']
        filename = data_file.name.lower()
        if not filename.endswith(('.xlsx', '.xlsm', '.csv')):
            raise forms.ValidationError('Upload an Excel or CSV file.')
        return data_file


class SalesTransactionForm(forms.ModelForm):
    class Meta:
        model = SalesTransaction
        fields = ['flock', 'sale_date', 'or_number', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['flock'].queryset = active_flocks_for_instance(self.instance)
        self.fields['notes'].widget.attrs.update({
            'class': 'form-control compact-note-input',
            'rows': 2,
        })


class SalesItemForm(forms.ModelForm):
    price_per_piece = forms.DecimalField(
        label='Price per piece',
        min_value=0,
        max_digits=10,
        decimal_places=2,
    )

    class Meta:
        model = SalesItem
        fields = ['grade', 'quantity_pieces', 'price_per_piece']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['price_per_piece'].initial = self.instance.unit_price

    def save(self, commit=True):
        instance = super().save(commit=False)
        unit_price = self.cleaned_data.get('price_per_piece') or 0
        quantity = instance.quantity_pieces or 0
        instance.amount = unit_price * quantity
        if commit:
            instance.save()
            self.save_m2m()
        return instance


SalesItemFormSet = inlineformset_factory(
    SalesTransaction,
    SalesItem,
    form=SalesItemForm,
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True,
)
