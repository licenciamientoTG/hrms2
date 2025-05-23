from django import forms
from .models import Department

class DepartmentCreateForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'abbreviated']
        labels = {
            'name': 'Nombre',
            'abbreviated': 'Abreviatura',
        }

class DepartmentUpdateForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'abbreviated']
        labels = {
            'name': 'Nombre',
            'abbreviated': 'Abreviatura',
        }
