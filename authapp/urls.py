from django.urls import path, include
from .views import login_view, register_view, logout_view

urlpatterns = [
    path("login/", login_view, name="login"),
    path("register/", register_view, name="register"),
    path("logout/", logout_view, name="logout"),
    path('accounts/', include('django.contrib.auth.urls')),
    path("auth/accounts/login/", login_view, name="login"),
]
