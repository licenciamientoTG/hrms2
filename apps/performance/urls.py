from django.urls import path
from .views import performance_review_view, performance_success_view

urlpatterns = [
    path('', performance_review_view, name='performance_review'),
    path('success/', performance_success_view, name='performance_success'),
]
