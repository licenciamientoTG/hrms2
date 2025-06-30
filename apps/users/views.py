from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from apps.employee.models import Employee, JobPosition
from django.http import JsonResponse
from django.contrib.auth.models import User, Group, Permission
from django.views.decorators.http import require_POST
from django.shortcuts import redirect
from datetime import datetime
from departments.models import Department
from apps.employee.models import Employee, JobPosition, JobCategory
from apps.location.models import Location

import csv

@login_required
def user_dashboard(request):
    empleados = Employee.objects.all().select_related('user')
    return render(request, 'users/user_dashboard.html', {
        'empleados': empleados
    })

@login_required
@require_POST
def toggle_user_status(request):
    user_id = request.POST.get("user_id")
    user = get_object_or_404(User, id=user_id)
    user.is_active = not user.is_active
    user.save()
    return JsonResponse({
        "status": "ok",
        "is_active": user.is_active
    })

@login_required
def manage_user_permissions(request, user_id):
    user = get_object_or_404(User, id=user_id)
    groups = Group.objects.all()
    permissions = Permission.objects.all()

    if request.method == 'POST':
        selected_groups = request.POST.getlist('groups')
        selected_perms = request.POST.getlist('permissions')

        user.groups.set(selected_groups)
        user.user_permissions.set(selected_perms)

        user.save()
        return redirect('user_dashboard')

    return render(request, 'users/manage_permissions.html', {
        'user_obj': user,
        'groups': groups,
        'permissions': permissions,
    })

@login_required
def upload_employees_csv(request):
    if request.method == 'POST' and request.FILES['csv_file']:
        csv_file = request.FILES['csv_file']
        decoded_file = csv_file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(decoded_file)

        for row in reader:
            emp_number = (row.get('N�mero') or "").strip()[:20]
            first_name = (row.get('Nombre') or "").strip()[:255]

            department_name = (row.get('Departamento') or "").strip()[:100]
            job_position_name = (row.get('Puesto') or "").strip()[:100]
            start_date_raw = row.get('Fecha de Ingreso')
            activo_raw = (row.get('Activo') or "").strip().upper()
            termination_date_raw = row.get('Fecha de Baja')
            rehire_raw = (row.get('Recontratar') or "").strip().upper()
            termination_reason = (row.get('Motivo de Baja') or "").strip()[:255]

            rfc = (row.get('RFC') or "").strip().upper()[:13]
            imss_raw = (row.get('IMSS') or "").strip().upper()
            imss = imss_raw.replace("IMSS", "").strip()[:11]

            curp = (row.get('CURP') or "").strip().upper()[:18]

            gender_raw = (row.get('G�nero') or "").strip().lower()
            if gender_raw.startswith("masc"):
                gender = "M"
            elif gender_raw.startswith("fem"):
                gender = "F"
            else:
                gender = "M"

            vacation_balance = float(row.get('SaldodeVacaciones') or "0")

            phone_number = "".join(filter(str.isdigit, (row.get('Tel�fono') or "")))[:10]

            address = (row.get('Direcci�n') or "").strip()

            # ✅ Parse fechas
            start_date = None
            if start_date_raw:
                try:
                    start_date = datetime.fromisoformat(start_date_raw.replace("Z", "")).date()
                except Exception as e:
                    print(f"Error parsing Fecha de Ingreso: {e}")

            termination_date = None
            if termination_date_raw:
                try:
                    termination_date = datetime.fromisoformat(termination_date_raw.replace("Z", "")).date()
                except Exception as e:
                    print(f"Error parsing Fecha de Baja: {e}")

            # ✅ Parse booleans
            is_active = True if activo_raw == "SI" else False
            rehire_eligible = True if rehire_raw == "SI" else False

            # ✅ FK: Department
            department_obj = None
            if department_name:
                department_obj, _ = Department.objects.get_or_create(
                    name=department_name,
                    defaults={'abbreviated': department_name[:5]}
                )

            # ✅ FK: JobCategory
            default_category, _ = JobCategory.objects.get_or_create(
                name='Sin categoría',
                defaults={'description': 'Cargado desde CSV'}
            )

            # ✅ FK: JobPosition con department + category
            job_position_obj = None
            if job_position_name and department_obj:
                job_position_obj, _ = JobPosition.objects.get_or_create(
                    title=job_position_name,
                    department=department_obj,
                    job_category=default_category,
                    defaults={
                        'description': 'Generado desde CSV',
                        'requirements': '',
                        'skills': '',
                        'level': 1,
                        'is_managerial': False,
                        'remote_eligible': False,
                        'is_active': True,
                        'headcount': 1
                    }
                )

            # ✅ Guarda empleado
            emp, created = Employee.objects.get_or_create(
                employee_number=emp_number,
                defaults={
                    'first_name': first_name,
                    'start_date': start_date,
                    'department': department_obj,
                    'job_position': job_position_obj,
                    'rfc': rfc,
                    'imss': imss,
                    'curp': curp,
                    'gender': gender,
                    'vacation_balance': vacation_balance,
                    'phone_number': phone_number,
                    'address': address,
                    'termination_date': termination_date,
                    'termination_reason': termination_reason,
                    'rehire_eligible': rehire_eligible,
                    'is_active': is_active
                }
            )

            if not created:
                emp.first_name = first_name
                emp.start_date = start_date
                emp.department = department_obj
                emp.job_position = job_position_obj
                emp.rfc = rfc
                emp.imss = imss
                emp.curp = curp
                emp.gender = gender
                emp.vacation_balance = vacation_balance
                emp.phone_number = phone_number
                emp.address = address
                emp.termination_date = termination_date
                emp.termination_reason = termination_reason
                emp.rehire_eligible = rehire_eligible
                emp.is_active = is_active
                emp.save()

        return redirect('user_dashboard')

    return redirect('user_dashboard')