from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from apps.employee.models import Employee
from .models import VacationRequest
from django.contrib import messages


@login_required
def vacation_request_view(request):
    try:
        empleado = Employee.objects.get(user=request.user)
        vacation_balance = empleado.vacation_balance
    except Employee.DoesNotExist:
        vacation_balance = 0

    solicitudes = VacationRequest.objects.filter(user=request.user).order_by('-created_at')

    return render(request, 'vacations/user/vacation_form_user.html', {
        'vacation_balance': vacation_balance,
        'solicitudes': solicitudes
    })

@login_required
def submit_vacation_request(request):
    if request.method == 'POST':
        tipo = request.POST.get('tipo_solicitud')
        inicio = request.POST.get('fecha_inicio')
        fin = request.POST.get('fecha_fin')
        observaciones = request.POST.get('observaciones')
        archivo = request.FILES.get('documento')

        VacationRequest.objects.create(
            user=request.user,
            tipo_solicitud=tipo,
            start_date=inicio,
            end_date=fin,
            reason=observaciones,
            documento=archivo
        )

        return redirect('vacation_request')  # o redirecciona a una vista donde se muestre el modal
    return redirect('vacation_request')
