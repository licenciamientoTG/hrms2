from django.urls import path, include
from .views import login_view, register_view, logout_view, terms_and_conditions_view
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("login/", login_view, name="login"),
    path("register/", register_view, name="register"),
    path("logout/", logout_view, name="logout"),
    path("terms/", terms_and_conditions_view, name="terms_and_conditions"),
    path('accounts/', include('django.contrib.auth.urls')),
    path("auth/accounts/login/", login_view, name="login"),
    # 1. Formulario para pedir correo
    path('reset_password/', 
         auth_views.PasswordResetView.as_view(template_name="registration/password_reset_form.html"), 
         name='password_reset'),

    # 2. Confirmación de envío
    path('reset_password_sent/', 
         auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"), 
         name='password_reset_done'),

    # 3. Link del correo (Token)
    path('reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(template_name="registration/password_reset_confirm.html"), 
         name='password_reset_confirm'),

    # 4. Éxito
    path('reset_password_complete/', 
         auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"), 
         name='password_reset_complete'),    

]
