from django.urls import path, include
from .views import calculator_view

urlpatterns = [
    path('', calculator_view, name='calculator_view'),
]