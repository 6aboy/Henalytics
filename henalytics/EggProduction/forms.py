from django import forms
from django.forms import inlineformset_factory

from .models import SalesItem, SalesTransaction


class SalesTransactionForm(forms.ModelForm):
    class Meta:
        model = SalesTransaction
        fields = ['flock', 'sale_date', 'or_number', 'notes']


SalesItemFormSet = inlineformset_factory(
    SalesTransaction,
    SalesItem,
    fields=['grade', 'quantity_pieces', 'amount'],
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True,
)
