from django.urls import path
from .views import vacation_request_view, vacation_success_view

urlpatterns = [
    path('', vacation_request_view, name='vacation_request'),
    path('success/', vacation_success_view, name='vacation_success'),
]
