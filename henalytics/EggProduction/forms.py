from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone

from .models import ProductionLog, SalesItem, SalesTransaction


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
            'pct_hen_day',
            'pct_hen_housed',
            'fcr',
            'remarks',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
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
        if flock and log_date and log_date < flock.date_started:
            self.add_error('log_date', 'Log date cannot be earlier than the flock start date.')
        return cleaned_data


class SalesTransactionForm(forms.ModelForm):
    class Meta:
        model = SalesTransaction
        fields = ['flock', 'sale_date', 'or_number', 'notes']


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
