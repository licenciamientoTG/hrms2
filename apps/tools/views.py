from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test

from apps.employee.models import Employee  # <-- importa tu modelo


@login_required
def calculator_view(request):
    if request.user.is_superuser:
        return redirect('calculator_admin')
    else:
        return redirect('calculator_user')

@login_required
def calculator_user(request):
    employee = Employee.objects.filter(user=request.user).first()

    fondo_ahorro = 0
    if employee and employee.saving_fund is not None:
        # lo pasamos como entero para el input number
        fondo_ahorro = int(employee.saving_fund)

    return render(
        request,
        "tools/user/calculator_user.html",
        {"fondo_ahorro": fondo_ahorro},
    )


@login_required
@user_passes_test(lambda u: u.is_superuser)
def calculator_admin(request):
    employee = Employee.objects.filter(user=request.user).first()

    fondo_ahorro = 0
    if employee and employee.saving_fund is not None:
        # lo pasamos como entero para el input number
        fondo_ahorro = int(employee.saving_fund)

    return render(
        request,
        "tools/admin/calculator_admin.html",
        {"fondo_ahorro": fondo_ahorro},
    )