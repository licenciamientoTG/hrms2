from django import forms
from django.contrib.auth.password_validation import validate_password

class AdminPasswordResetForm(forms.Form):
    new_password1 = forms.CharField(
        widget=forms.PasswordInput, 
        label="Nueva contraseña",
        validators=[validate_password]
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput, 
        label="Repetir contraseña"
    )

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("new_password1")
        p2 = cleaned.get("new_password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Las dos contraseñas no coinciden.")
        return cleaned
