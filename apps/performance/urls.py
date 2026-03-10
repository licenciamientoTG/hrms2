from django.urls import path
from .views import (
    performance_view, performance_view_admin, performance_view_user,
    create_cycle, evaluate_person, close_performance_cycle,
    my_cycle_history_detail, admin_cycle_participants, admin_employee_cycle_reviews,
)

urlpatterns = [
    path('', performance_view, name='performance'),
    path('admin/', performance_view_admin, name='performance_view_admin'),
    path('user/', performance_view_user, name='performance_view_user'),
    path('create_cycle/', create_cycle, name='create_cycle'),
    path('evaluate/<int:review_id>/', evaluate_person, name='evaluate_person'),
    path('performance/cycle/close/<int:cycle_id>/', close_performance_cycle, name='close_performance_cycle'),
    path('historial/ciclo/<int:cycle_id>/', my_cycle_history_detail, name='my_cycle_history_detail'),
    path('admin/ciclo/<int:cycle_id>/participantes/', admin_cycle_participants, name='admin_cycle_participants'),
    path('admin/ciclo/<int:cycle_id>/empleado/<int:employee_id>/evaluaciones/', admin_employee_cycle_reviews, name='admin_employee_cycle_reviews'),
]
