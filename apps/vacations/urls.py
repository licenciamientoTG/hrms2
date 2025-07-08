from django.urls import path
from .views import vacation_request_view

urlpatterns = [
    path('', vacation_request_view, name='vacation_request'),
]
