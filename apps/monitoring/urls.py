from django.urls import path
from .views import monitoring_view, module_panel_api

urlpatterns = [
    path("", monitoring_view, name="monitoring_view"),
    path("api/panel/", module_panel_api, name="module_panel_api"),
]
