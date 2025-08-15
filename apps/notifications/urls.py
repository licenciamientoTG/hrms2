from django.urls import path
from . import views

urlpatterns = [
    path('api/notifications/', views.api_list, name='notifications_api_list'),
    path('api/notifications/mark-all-read/', views.api_mark_all_read, name='notifications_api_mark_all'),
]
