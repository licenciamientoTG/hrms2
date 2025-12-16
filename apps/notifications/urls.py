from django.urls import path
from . import views

urlpatterns = [
    path('api/notifications/', views.api_list, name='notifications_api_list'),
    path('api/notifications/mark-all-read/', views.api_mark_all_read, name='notifications_api_mark_all'),
    path('api/notifications/<int:pk>/read/', views.api_mark_read, name='notifications_api_mark_read'), 
    path('api/mark-module-read/<str:module_name>/', views.api_mark_module_read, name='api_mark_module_read'),
]
