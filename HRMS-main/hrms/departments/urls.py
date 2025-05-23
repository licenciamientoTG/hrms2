from django.urls import path
from . import views

urlpatterns = [
    path('', views.department_list, name='department_list'),
    path('create/', views.department_create, name='department_create'),
    path('<int:pk>/update/', views.department_update, name='department_update'),
    path('<int:pk>/delete/', views.department_delete, name='department_delete'),
]