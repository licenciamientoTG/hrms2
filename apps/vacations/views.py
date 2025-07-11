from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.employee.models import Employee

@login_required
def vacation_request_view(request):
    try:
        empleado = Employee.objects.get(user=request.user)
        vacation_balance = empleado.vacation_balance
    except Employee.DoesNotExist:
        vacation_balance = 0  # o None, o lo que prefieras como default

    return render(request, 'vacations/user/vacation_form_user.html', {
        'vacation_balance': vacation_balance
    })
