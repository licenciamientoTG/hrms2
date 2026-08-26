from django.urls import path
from .views import monitoring_view, module_panel_api, live_stats_api, user_modules_api

urlpatterns = [
    path("", monitoring_view, name="monitoring_view"),
    path("api/panel/", module_panel_api, name="module_panel_api"),
    path("api/live/", live_stats_api, name="live_stats_api"),
    path("api/user-modules/", user_modules_api, name="user_modules_api"),
]
