from django.urls import path
from .views import org_chart_view

urlpatterns = [
    path('', org_chart_view, name='org_chart'),
]
