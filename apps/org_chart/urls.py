# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.org_chart_view, name='org_chart'),
    path('admin/', views.org_chart_admin, name='org_chart_admin'),
    path('user/', views.org_chart_user, name='org_chart_user'),
    path("data/org_chart_1/", views.org_chart_data_1, name="org_chart_data_1"),
    path('api/move_position/', views.api_move_position, name='api_move_position'),
    path('api/reorder_node/', views.api_reorder_node, name='api_reorder_node'),
    path('api/view_state/', views.api_view_state, name='api_view_state'),
    path('api/node_y_offset/', views.api_node_y_offset, name='api_node_y_offset'),
]
