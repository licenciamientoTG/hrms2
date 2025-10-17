# apps/vacations/urls.py
from django.urls import path
from .views import vacation_dashboard, vacation_form_admin, vacation_form_user
urlpatterns = [
    # Dispatcher: decide a dónde ir (admin vs usuario)
    path('', vacation_dashboard, name='vacation_dashboard'),

    # Vistas
    path('admin/', vacation_form_admin, name='vacation_form_admin'),
    path('mis-solicitudes/', vacation_form_user, name='vacation_form_user'),


]
