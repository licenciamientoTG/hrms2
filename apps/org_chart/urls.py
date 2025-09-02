# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.org_chart_view, name='org_chart'),
    path('admin/', views.org_chart_admin, name='org_chart_admin'),
    path('user/', views.org_chart_user, name='org_chart_user'),
    path("data/org_chart_1/", views.org_chart_data_1, name="org_chart_data_1"),

]
