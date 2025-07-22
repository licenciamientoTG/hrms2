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
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from .forms import AdminPasswordResetForm
import csv
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash

@login_required
def user_dashboard(request):
    empleados = Employee.objects.select_related('user')
    permisos = Permission.objects.all() 

    return render(request, 'users/user_dashboard.html', {
        'empleados': empleados,
        'permissions': permisos,
    })



@user_passes_test(lambda u: u.is_superuser)
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
    user_obj = get_object_or_404(User, id=user_id)
    grupos = Group.objects.all()
    permisos = Permission.objects.all()

    if request.method == 'POST':
        if 'nombre' in request.POST:
            # Si viene del modal de crear grupo
            nombre = request.POST.get('nombre')
            permisos_ids = request.POST.getlist('group_permissions')
            if not Group.objects.filter(name=nombre).exists():
                grupo = Group.objects.create(name=nombre)
                grupo.permissions.set(permisos_ids)
                messages.success(request, "Grupo creado con éxito.")
            else:
                messages.warning(request, "Ese grupo ya existe.")
            return redirect(request.path_info)

        # Si viene del formulario de grupos y permisos del usuario
        selected_groups = request.POST.getlist('groups')
        selected_perms = request.POST.getlist('permissions')

        user_obj.groups.set(selected_groups)
        user_obj.user_permissions.set(selected_perms)

        messages.success(request, "Permisos actualizados correctamente.")
        return redirect(request.path_info)

    return render(request, 'users/manage_permissions.html', {
        'user_obj': user_obj,
        'groups': grupos,
        'permissions': permisos,
        'permisos': permisos,  # para el modal
    })

@login_required
def upload_employees_csv(request):
    if request.method == 'POST':
        # ✅ Usa .get() para evitar MultiValueDictKeyError
        csv_file = request.FILES.get('csv_file')

        if not csv_file:
            return redirect('user_dashboard')

        decoded_file = csv_file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(decoded_file)

        for row in reader:
            # 🔑 Separar nombre
            raw_name = (row.get('Nombre') or "").strip()
            parts = raw_name.split(',')
            if len(parts) == 2:
                last_name = parts[0].strip()
                first_name = parts[1].strip()
            else:
                last_name = raw_name.strip()
                first_name = ""

            # Recortar según modelo Employee
            first_name = first_name[:Employee._meta.get_field('first_name').max_length]
            last_name = last_name[:Employee._meta.get_field('last_name').max_length]

            emp_number = (row.get('N�mero') or "").strip()
            emp_number = emp_number[:Employee._meta.get_field('employee_number').max_length]

            department_name = (row.get('Departamento') or "").strip()
            job_position_name = (row.get('Puesto') or "").strip()

            start_date_raw = row.get('Fecha de Ingreso')
            activo_raw = (row.get('Activo') or "").strip().upper()
            termination_date_raw = row.get('Fecha de Baja')
            rehire_raw = (row.get('Recontratar') or "").strip().upper()
            termination_reason = (row.get('Motivo de Baja') or "").strip()
            termination_reason = termination_reason[:Employee._meta.get_field('termination_reason').max_length]

            rfc = (row.get('RFC') or "").strip().upper()
            rfc = rfc[:Employee._meta.get_field('rfc').max_length]

            imss_raw = (row.get('IMSS') or "").strip().upper()
            imss = imss_raw.replace("IMSS", "").strip()
            imss = imss[:Employee._meta.get_field('imss').max_length]

            curp = (row.get('CURP') or "").strip().upper()
            curp = curp[:Employee._meta.get_field('curp').max_length]

            gender_raw = (row.get('G�nero') or "").strip().lower()
            if gender_raw.startswith("masc"):
                gender = "M"
            elif gender_raw.startswith("fem"):
                gender = "F"
            else:
                gender = "M"

            vacation_balance = float(row.get('SaldodeVacaciones') or "0")

            phone_number = "".join(filter(str.isdigit, (row.get('Tel�fono') or "")))
            phone_number = phone_number[:Employee._meta.get_field('phone_number').max_length]

            address = (row.get('Direcci�n') or "").strip()
            address = address[:Employee._meta.get_field('address').max_length]

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

            is_active = True if activo_raw == "SI" else False
            rehire_eligible = True if rehire_raw == "SI" else False

            # ✅ FK: Department
            department_obj = None
            if department_name:
                dep_name_max = Department._meta.get_field('name').max_length
                dep_abbr_max = Department._meta.get_field('abbreviated').max_length

                department_name = department_name[:dep_name_max]
                department_abbr = department_name[:dep_abbr_max]

                department_obj, _ = Department.objects.get_or_create(
                    name=department_name,
                    defaults={'abbreviated': department_abbr}
                )

            # ✅ FK: JobCategory
            default_category, _ = JobCategory.objects.get_or_create(
                name='Sin categoría',
                defaults={'description': 'Cargado desde CSV'}
            )

            # ✅ FK: JobPosition
            job_position_obj = None
            if job_position_name and department_obj:
                job_title_max = JobPosition._meta.get_field('title').max_length
                job_position_name = job_position_name[:job_title_max]

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
                    'last_name': last_name,
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
                emp.last_name = last_name
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

@user_passes_test(lambda u: u.is_superuser)
def admin_reset_password(request, user_id):
    user_obj = get_object_or_404(User, pk=user_id)
    form = AdminPasswordResetForm(request.POST or None)
    if form.is_valid():
        user_obj.set_password(form.cleaned_data['new_password1'])
        user_obj.save()
        messages.success(request, f"✔️ Contraseña de {user_obj.username} restablecida.")
        return redirect('user_dashboard')  # Ajusta este name al de tu lista de usuarios
    return render(request, 'users/admin_reset_password.html', {
        'form': form,
        'target_user': user_obj
    })

@user_passes_test(lambda u: u.is_superuser)  # Solo superusuarios
def crear_grupo(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        permisos_ids = request.POST.getlist('group_permissions')  # <-- importante

        if nombre:
            if not Group.objects.filter(name=nombre).exists():
                grupo = Group.objects.create(name=nombre)

                # Asignar permisos al grupo
                if permisos_ids:
                    grupo.permissions.set(permisos_ids)

                messages.success(request, f"Grupo '{nombre}' creado correctamente.")
            else:
                messages.warning(request, f"El grupo '{nombre}' ya existe.")
        else:
            messages.error(request, "Debes escribir un nombre para el grupo.")

        return redirect('user_dashboard')  # Ajustado correctamente

@login_required
def force_password_change(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            # Desactivamos el flag
            request.user.userprofile.must_change_password = False
            request.user.userprofile.save()
            return redirect('home')  # O a donde quieras enviarlo después
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'courses/user/force_password_change.html', {'form': form})