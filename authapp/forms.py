from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordResetForm
from django.contrib.auth.models import User
from apps.employee.models import Employee


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


class CustomPasswordResetForm(PasswordResetForm):

    def get_users(self, email):
        # Buscar por correo corporativo, si no por personal
        try:
            emp = Employee.objects.get(corporate_email__iexact=email, user__isnull=False)
            if emp.user.is_active and emp.user.has_usable_password():
                return [emp.user]
        except Employee.DoesNotExist:
            pass

        try:
            emp = Employee.objects.get(email__iexact=email, user__isnull=False)
            if emp.user.is_active and emp.user.has_usable_password():
                return [emp.user]
        except Employee.DoesNotExist:
            pass

        return []

    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        # Enviar al correo que ingresó el usuario
        super().send_mail(
            subject_template_name, email_template_name, context,
            from_email, self.cleaned_data['email'],
            html_email_template_name=html_email_template_name,
        )
