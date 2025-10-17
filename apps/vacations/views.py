from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from apps.employee.models import Employee
from .models import VacationRequest
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test

# esta vista te redirige a las vistas de usuario y administrador
@login_required
def vacation_dashboard(request):
    if request.user.is_superuser:
        return redirect('vacation_form_admin')
    else:
        return redirect('vacation_form_user')

# esta vista es para el administrador
@login_required
@user_passes_test(lambda u: u.is_superuser)
def vacation_form_admin(request):

    return render(request, 'vacations/admin/vacation_form_admin.html')

# esta vista es para el usuario
@login_required
def vacation_form_user(request):

    return render(request, 'vacations/user/vacation_form_user.html')