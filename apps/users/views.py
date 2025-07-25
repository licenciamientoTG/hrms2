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
import chardet
from .utils import parse_fecha

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
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            print("❌ No se recibió archivo.")
            return redirect('user_dashboard')

        # Detectar codificación
        file_bytes = csv_file.read()
        detected = chardet.detect(file_bytes)
        encoding = detected.get('encoding') or 'latin1'
        print(f"📄 Codificación detectada: {encoding}")

        try:
            decoded_file = file_bytes.decode(encoding, errors='replace').splitlines()
        except Exception as e:
            print(f"❌ Error al decodificar archivo: {e}")
            return redirect('user_dashboard')

        reader = csv.DictReader(decoded_file)
        for i, row in enumerate(reader, start=1):
            print(f"➡️ Fila {i}: {row}")

            employee_number = (row.get('Número') or "").strip()
            if not employee_number:
                print(f"⚠️ Fila {i} omitida. Número vacío.")
                continue

            nombre = (row.get('Nombre') or "").strip()
            parts = nombre.split(',')
            if len(parts) == 2:
                last_name = parts[0].strip()
                first_name = parts[1].strip()
            else:
                last_name = nombre
                first_name = ""

            rfc = (row.get('RFC') or "").strip().upper()
            imss = (row.get('IMSS') or "").strip().upper()
            curp = (row.get('CURP') or "").strip().upper()

            genero_raw = (row.get('Género') or "").strip().lower()
            gender = "F" if genero_raw.startswith("fem") else "M"

            try:
                vacation_balance = float(row.get('Saldo de Vacaciones') or "0")
            except ValueError:
                vacation_balance = 0

            telefono = "".join(filter(str.isdigit, (row.get('Teléfono') or "")))
            direccion = (row.get('Dirección') or "").strip()

            fecha_ingreso = parse_fecha(row.get('Fecha de Ingreso'))
            fecha_baja = parse_fecha(row.get('Fecha de Baja'))

            activo_raw = (row.get('Activo') or "").strip().upper()
            activo = activo_raw == "SI"
            if not activo:
                print(f"🚫 Fila {i} omitida. Empleado inactivo.")
                continue

            recontratar = (row.get('Recontratar') or "").strip().upper() == "SI"
            motivo_baja = (row.get('Motivo de Baja') or "").strip()

            departamento_nombre = (row.get('Departamento') or "").strip()
            puesto_nombre = (row.get('Puesto') or "").strip()

            # Crear o recuperar departamento
            department = None
            if departamento_nombre:
                department, _ = Department.objects.get_or_create(
                    name=departamento_nombre[:Department._meta.get_field('name').max_length],
                    defaults={'abbreviated': departamento_nombre[:Department._meta.get_field('abbreviated').max_length]}
                )

            # Categoría por defecto
            default_category, _ = JobCategory.objects.get_or_create(
                name='Sin categoría',
                defaults={'description': 'Cargado desde CSV'}
            )

            # Crear o recuperar puesto
            job_position = None
            if puesto_nombre and department:
                job_position, _ = JobPosition.objects.get_or_create(
                    title=puesto_nombre[:JobPosition._meta.get_field('title').max_length],
                    department=department,
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

            # Crear o actualizar empleado
            emp, created = Employee.objects.get_or_create(
                employee_number=employee_number[:Employee._meta.get_field('employee_number').max_length],
                defaults={
                    'first_name': first_name[:Employee._meta.get_field('first_name').max_length],
                    'last_name': last_name[:Employee._meta.get_field('last_name').max_length],
                    'start_date': fecha_ingreso,
                    'department': department,
                    'job_position': job_position,
                    'rfc': rfc[:Employee._meta.get_field('rfc').max_length],
                    'imss': imss[:Employee._meta.get_field('imss').max_length],
                    'curp': curp[:Employee._meta.get_field('curp').max_length],
                    'gender': gender,
                    'vacation_balance': vacation_balance,
                    'phone_number': telefono[:Employee._meta.get_field('phone_number').max_length],
                    'address': direccion[:Employee._meta.get_field('address').max_length],
                    'termination_date': fecha_baja,
                    'termination_reason': motivo_baja[:Employee._meta.get_field('termination_reason').max_length],
                    'rehire_eligible': recontratar,
                    'is_active': activo,
                    'birth_date': None,
                    'education_level': '',
                    'email': '',
                    'station_id': None,
                    'notes': '',
                    'photo': None,
                }
            )

            if not created:
                emp.first_name = first_name
                emp.last_name = last_name
                emp.start_date = fecha_ingreso
                emp.department = department
                emp.job_position = job_position
                emp.rfc = rfc
                emp.imss = imss
                emp.curp = curp
                emp.gender = gender
                emp.vacation_balance = vacation_balance
                emp.phone_number = telefono
                emp.address = direccion
                emp.termination_date = fecha_baja
                emp.termination_reason = motivo_baja
                emp.rehire_eligible = recontratar
                emp.is_active = activo
                # opcionales no se actualizan aún
                emp.save()
                print(f"🔄 Empleado actualizado: {employee_number}")
            else:
                print(f"✅ Empleado creado: {employee_number}")

        print("🟢 Finalizado el proceso de importación.")
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