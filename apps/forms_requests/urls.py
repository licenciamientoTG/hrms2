from django.urls import path
from .views import request_form_view
from . import views


urlpatterns = [
    path('', request_form_view, name='request_form'),
    path('solicitud/usuario/', views.user_forms_view, name='user_forms'),
    path('solicitud/admin/', views.admin_forms_view, name='admin_forms'),

]
