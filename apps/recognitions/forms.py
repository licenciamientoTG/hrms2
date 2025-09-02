from django import forms
from .models import RecognitionCategory

class RecognitionCategoryForm(forms.ModelForm):
    class Meta:
        model = RecognitionCategory
        fields = ["title", "points", "color_hex",
                  "confetti_enabled", "show_points",
                  "cover_image", "order", "is_active"]
        widgets = {
            "title": forms.TextInput(attrs={"class":"form-control","placeholder":"Nombre de la categoría"}),
            "points": forms.NumberInput(attrs={"class":"form-control","min":0}),
            "color_hex": forms.TextInput(attrs={"class":"form-control","type":"color","id":"colorPicker"}),
            "confetti_enabled": forms.CheckboxInput(attrs={"class":"form-check-input","id":"confettiSwitch"}),
            "show_points": forms.CheckboxInput(attrs={"class":"form-check-input","id":"pointsSwitch"}),
            "cover_image": forms.ClearableFileInput(attrs={"class":"form-control","accept":"image/*","id":"coverInput"}),
            "order": forms.NumberInput(attrs={"class":"form-control","min":0}),
            "is_active": forms.CheckboxInput(attrs={"class":"form-check-input"}),
        }
