from django.urls import path, include
from .views import tools_view

urlpatterns = [
    path('', tools_view, name='tools_view'),
]