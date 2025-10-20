from django.urls import path
from .views import objective_view, admin_objective, user_objective, create_objective

urlpatterns = [
    path('', objective_view, name='objective_view'),
    path('admin_objective/', admin_objective, name='admin_objective'),
    path('user_objective/', user_objective, name='user_objective'),
    path('create_objective/', create_objective, name='create_objective'), 
]
