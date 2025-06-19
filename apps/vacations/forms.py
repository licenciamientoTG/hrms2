from django import forms
from .models import VacationRequest

class VacationRequestForm(forms.ModelForm):
    class Meta:
        model = VacationRequest
        fields = ['start_date', 'end_date', 'reason']
