from django.urls import path
from .views import request_form_view, form_success_view

urlpatterns = [
    path('', request_form_view, name='request_form'),
    path('success/', form_success_view, name='form_success'),
]
