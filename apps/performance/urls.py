from django.urls import path
from .views import performance_view, performance_view_admin, performance_view_user

urlpatterns = [
    path('', performance_view, name='performance'),
    path('admin/', performance_view_admin, name='performance_view_admin'),
    path('user/', performance_view_user, name='performance_view_user'),
]
