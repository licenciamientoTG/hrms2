from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Usuario", widget=forms.TextInput(attrs={"class": "form-control"}))
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput(attrs={"class": "form-control"}))


class RegisterForm(UserCreationForm):
    username = forms.CharField(label="Usuario", widget=forms.TextInput(attrs={"class": "form-control"}))
    email = forms.EmailField(label="Correo electrónico", widget=forms.EmailInput(attrs={"class": "form-control"}))
    password1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput(attrs={"class": "form-control"}))
    password2 = forms.CharField(label="Confirmar contraseña", widget=forms.PasswordInput(attrs={"class": "form-control"}))

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]
