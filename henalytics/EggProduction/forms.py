from django import forms
from django.forms import inlineformset_factory

from .models import SalesItem, SalesTransaction


class SalesTransactionForm(forms.ModelForm):
    class Meta:
        model = SalesTransaction
        fields = ['flock', 'sale_date', 'notes']


SalesItemFormSet = inlineformset_factory(
    SalesTransaction,
    SalesItem,
    fields=['grade', 'quantity_trays', 'price_per_tray'],
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True,
)
