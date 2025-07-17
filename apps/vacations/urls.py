from django.urls import path
from .views import vacation_request_view, submit_vacation_request

urlpatterns = [
    path('', vacation_request_view, name='vacation_request'),
    path('solicitar/', submit_vacation_request, name='submit_vacation'),
]
