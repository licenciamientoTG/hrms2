from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from apps.employee.models import Employee  # <-- importa tu modelo

@login_required
def calculator_view(request):
    employee = Employee.objects.filter(user=request.user).first()

    fondo_ahorro = 0
    if employee and employee.saving_fund is not None:
        # lo pasamos como entero para el input number
        fondo_ahorro = int(employee.saving_fund)

    return render(
        request,
        "tools/loan_calculator_view.html",
        {"fondo_ahorro": fondo_ahorro},
    )
