from django.urls import path
from .views import (
    policies_dashboard_view,
    policies_admin_view,
    policies_user_view,
)

urlpatterns = [
    path("", policies_dashboard_view, name="policies_dashboard_view"),
    path("admin/", policies_admin_view, name="policies_admin_view"),
    path("user/", policies_user_view, name="policies_user_view"),
]
