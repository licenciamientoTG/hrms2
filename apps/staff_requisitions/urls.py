from django.urls import path
from . import views

urlpatterns = [
    path('', views.staff_requisitions_view, name='staff_requisitions_home'),
    path('admin/', views.admin_staff_requisitions, name='admin_staff_requisitions'),
    path('usuario/', views.user_staff_requisitions, name='user_staff_requisitions'),
]
