from django.urls import path
from .views import (
    recognition_dashboard,
    recognition_dashboard_admin,
    recognition_dashboard_user,

    CategoryListView,
    CategoryCreateView,
    CategoryUpdateView,
    CategoryDeleteView,
    category_toggle_active,
)

urlpatterns = [
    # DASHBOARD
    path('', recognition_dashboard, name='recognition_dashboard'),
    path('admin/', recognition_dashboard_admin, name='recognition_dashboard_admin'),
    path('user/', recognition_dashboard_user, name='recognition_dashboard_user'),

    # CATEGORÍAS
    path('categories/', CategoryListView.as_view(), name='category_list'),
    path('categories/new/', CategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/edit/', CategoryUpdateView.as_view(), name='category_edit'),
    path('categories/<int:pk>/delete/', CategoryDeleteView.as_view(), name='category_delete'),
    path('categories/<int:pk>/toggle/', category_toggle_active, name='category_toggle'),
]
