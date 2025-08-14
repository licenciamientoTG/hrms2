from django.urls import path
from .views import request_form_view, generar_carta_recomendacion 
from . import views


urlpatterns = [
    path('', request_form_view, name='request_form'),
    path('solicitud/usuario/', views.user_forms_view, name='user_forms'),
    path('solicitud/admin/', views.admin_forms_view, name='admin_forms'),
    path('constancia-laboral/', views.generar_constancia_laboral, name='constancia_laboral'),
    path('constancia-especial/', views.generar_constancia_especial, name='constancia_especial'),
    path("guardar-constancia-guarderia/", views.guardar_constancia_guarderia, name="guardar_constancia_guarderia"),
    path("guarderia/<int:pk>/detalle/", views.guarderia_detalle, name="guarderia_detalle"),
    path("guarderia/<int:pk>/responder/", views.responder_guarderia, name="responder_guarderia"),
    path('carta-recomendacion/', generar_carta_recomendacion, name='carta_recomendacion'),
    path('api/validar-empleado-numero/', views.validar_empleado_numero, name='validar_empleado_numero'),
]
