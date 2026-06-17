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
from django.db.models import Prefetch
from django.db.models import Q
from django.contrib.auth import get_user_model

@login_required
@user_passes_test(lambda u: u.is_staff)
def user_dashboard(request):
    q = (request.GET.get('q') or '').strip()
    users_qs = User.objects.filter(is_superuser=False).select_related('employee').order_by('-date_joined')

    # 2. Búsqueda Inteligente
    if q:
        # A. Creamos los filtros de texto básicos (lo que ya tenías)
        filtros = (
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(username__icontains=q) |
            Q(email__icontains=q)
        )

        # B. MAGIA: Si escribe "staff" o variaciones, agregamos la condición is_staff=True
        # Usamos lower() para que detecte Staff, STAFF, staff, etc.
        palabras_clave_staff = ['staff', 'staf', 'admin', 'administrador']
        
        if q.lower() in palabras_clave_staff:
            # El operador | significa "O" (OR).
            # "Busca por nombre... O si es staff verdadero"
            filtros = filtros | Q(is_staff=True)

        # C. Aplicamos todos los filtros juntos
        users_qs = users_qs.filter(filtros)

    # 3. Paginación (Sigue igual...)
    page_size = int(request.GET.get('page_size', 10))
    paginator = Paginator(users_qs, page_size)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'users/user_dashboard.html', {
        'users_list': page_obj.object_list,
        'permissions': Permission.objects.all(),
        'page_obj': page_obj,
        'page_size': page_size,
        'q': q,
    })


@login_required
@user_passes_test(lambda u: u.is_staff)
@require_POST
def upload_user_photo(request, user_id):
    import os
    import traceback
    from django.core.files.storage import default_storage
    from django.core.files.base import ContentFile

    try:
        user = get_object_or_404(User, id=user_id)
        employee = getattr(user, 'employee', None)
        if not employee:
            return JsonResponse({'status': 'error', 'message': 'El usuario no tiene empleado asociado'}, status=400)
        photo = request.FILES.get('photo')
        if not photo:
            return JsonResponse({'status': 'error', 'message': 'No se recibió ninguna foto'}, status=400)

        ext = os.path.splitext(photo.name)[1].lower()
        filename = f'collaborators/{user_id}{ext}'

        # Asegurar que la carpeta existe con permisos correctos
        folder = os.path.join(default_storage.location, 'collaborators')
        os.makedirs(folder, mode=0o775, exist_ok=True)

        if default_storage.exists(filename):
            default_storage.delete(filename)
        saved_path = default_storage.save(filename, ContentFile(photo.read()))
        employee.photo = saved_path
        employee.save(update_fields=['photo'])
        return JsonResponse({'status': 'ok', 'url': employee.photo.url})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': traceback.format_exc()}, status=500)


@user_passes_test(lambda u: u.is_staff)
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

@user_passes_test(lambda u: u.is_staff)
def manage_user_permissions(request, user_id):
    user_obj = get_object_or_404(User, id=user_id)
    grupos = Group.objects.prefetch_related('permissions').all()
    permisos = Permission.objects.all()

    if request.method == 'POST':
        # Guardar cambios del USUARIO
        selected_groups = request.POST.getlist('groups')
        selected_perms = request.POST.getlist('permissions')

        user_obj.groups.set(selected_groups)
        user_obj.user_permissions.set(selected_perms)

        messages.success(request, f"Permisos de {user_obj.username} actualizados correctamente.")
        return redirect('manage_user_permissions', user_id=user_id)

    permisos_efectivos = set(user_obj.user_permissions.values_list('id', flat=True)) | \
        set(Permission.objects.filter(group__user=user_obj).values_list('id', flat=True))

    return render(request, 'users/manage_permissions.html', {
        'user_obj': user_obj,
        'groups': grupos,
        'permissions': permisos,
        'permisos_efectivos': permisos_efectivos,
    })

@user_passes_test(lambda u: u.is_staff)
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

@user_passes_test(lambda u: u.is_staff)
@require_POST
def create_group(request):
    # Obtenemos los datos con los nombres EXACTOS del modal HTML
    nombre = request.POST.get('new_group_name')
    permisos_ids = request.POST.getlist('new_group_permissions')
    
    # Obtenemos la URL anterior para redirigir allí mismo
    referer = request.META.get('HTTP_REFERER', 'user_dashboard')

    if nombre:
        if not Group.objects.filter(name=nombre).exists():
            grupo = Group.objects.create(name=nombre)
            if permisos_ids:
                grupo.permissions.set(permisos_ids)
            messages.success(request, f"Grupo '{nombre}' creado con éxito.")
        else:
            messages.warning(request, f"El grupo '{nombre}' ya existe.")
    else:
        messages.error(request, "El nombre del grupo es obligatorio.")

    return redirect(referer)

@user_passes_test(lambda u: u.is_staff)
@require_POST
def delete_group(request, group_id):
    grupo = get_object_or_404(Group, id=group_id)
    nombre = grupo.name
    grupo.delete()
    messages.success(request, f"El grupo '{nombre}' ha sido eliminado.")
    
    # Redirigir a la misma página
    return redirect(request.META.get('HTTP_REFERER', 'user_dashboard'))

@user_passes_test(lambda u: u.is_staff)
def reset_password_to_default(request, user_id):
    # 1. Obtenemos el usuario
    target_user = get_object_or_404(User, pk=user_id)
    
    # 2. Intentamos obtener el empleado ligado
    try:
        employee = target_user.employee 
    except Exception:
        # Si falla el acceso directo, intentamos buscarlo manualmente
        employee = Employee.objects.filter(user=target_user).first()

    if not employee:
        messages.error(request, f"El usuario {target_user.username} no tiene un empleado asignado. No se puede calcular la contraseña default.")
        return redirect('admin_reset_password', user_id=user_id)

    # 3. Lógica matemática de la contraseña (ID + CURP)
    try:
        emp_number = str(employee.employee_number)
        
        # Validamos que tenga CURP para evitar errores
        curp_fragment = "000000"
        if employee.curp and len(employee.curp) >= 10:
            # Tomamos dígitos del 4 al 10 (YYMMDD)
            curp_fragment = employee.curp[4:10]
        
        default_password = f"{emp_number}{curp_fragment}"
        
        # 4. Establecemos la contraseña
        target_user.set_password(default_password)
        target_user.save()

        try:
            # Intentamos acceder al perfil (authapp_userprofile)
            if hasattr(target_user, 'userprofile'):
                target_user.userprofile.must_change_password = True
                target_user.userprofile.save()
            else:
                # Si por alguna razón el usuario no tenía perfil creado, lo creamos
                from authapp.models import UserProfile
                UserProfile.objects.create(user=target_user, must_change_password=True)
                
            messages.success(request, f"✅ Contraseña restablecida a: {default_password} (Se forzará el cambio al iniciar sesión).")
            
        except Exception as e:
            # Si falla actualizar el perfil, al menos avisamos, pero la contraseña ya se cambió
            print(f"Error actualizando perfil: {e}")
            messages.warning(request, f"Contraseña cambiada a {default_password}, pero hubo un error activando el cambio obligatorio.")

    except Exception as e:
        messages.error(request, f"Error al generar contraseña: {str(e)}")

    return redirect('admin_reset_password', user_id=user_id)

@login_required
@user_passes_test(lambda u: u.is_superuser)
def terms_audit_view(request):
    User = get_user_model()
    q = (request.GET.get('q') or '').strip()
    
    # 1. Base del Query con optimización de relaciones
    users_qs = User.objects.select_related('userprofile', 'employee__department').order_by('username')
    
    # 2. Lógica de Buscador (Filtra por nombre, apellido o nombre de usuario)
    if q:
        users_qs = users_qs.filter(
            Q(username__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(employee__employee_number__icontains=q)
        )
    
    # 3. Paginación (Carga de 15 en 15 como en tus otras vistas)
    paginator = Paginator(users_qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, "authapp/terms_audit.html", {
        "page_obj": page_obj,
        "q": q
    })


@login_required
@user_passes_test(lambda u: u.username.upper() in ('SUPERUSER', 'JOSE'))
def user_inconsistencias_view(request):
    # Empleados activos con username != employee_number (tienen sufijo)
    sufijo_cases = []
    for emp in Employee.objects.filter(is_active=True).select_related('user', 'department', 'job_position', 'station'):
        if emp.user and emp.user.username != str(emp.employee_number):
            clean_username = str(emp.employee_number)
            clean_user = User.objects.filter(username=clean_username).first()
            clean_emp = None
            if clean_user:
                try:
                    clean_emp = clean_user.employee
                except Exception:
                    clean_emp = None

            # Calcular diferencias entre el registro sufijado (nuevo) y el original (limpio)
            diferencias = []
            es_misma_persona = False
            if clean_emp and clean_emp.is_active:
                # Mismo apellido => misma persona
                es_misma_persona = clean_emp.last_name.strip().lower() == emp.last_name.strip().lower()

                campos = [
                    ('Razón Social',    emp.company,                                           clean_emp.company),
                    ('Nombre',          emp.first_name,                                        clean_emp.first_name),
                    ('Apellidos',       emp.last_name,                                         clean_emp.last_name),
                    ('Departamento',    str(emp.department or '—'),                            str(clean_emp.department or '—')),
                    ('Puesto',          emp.job_position.title if emp.job_position else '—',   clean_emp.job_position.title if clean_emp.job_position else '—'),
                    ('Estación',        str(emp.station or '—'),                               str(clean_emp.station or '—')),
                    ('RFC',             emp.rfc or '—',                                        clean_emp.rfc or '—'),
                    ('IMSS',            emp.imss or '—',                                       clean_emp.imss or '—'),
                    ('CURP',            emp.curp or '—',                                       clean_emp.curp or '—'),
                    ('Sexo',            emp.gender or '—',                                     clean_emp.gender or '—'),
                    ('Fecha de ingreso', str(emp.start_date or '—'),                           str(clean_emp.start_date or '—')),
                    ('Fecha de nacimiento', str(emp.birth_date or '—'),                        str(clean_emp.birth_date or '—')),
                    ('Antigüedad',      emp.seniority_raw or '—',                              clean_emp.seniority_raw or '—'),
                    ('Salario diario',  str(emp.daily_salary or '—'),                          str(clean_emp.daily_salary or '—')),
                    ('Fondo de ahorro', str(emp.saving_fund or '—'),                           str(clean_emp.saving_fund or '—')),
                    ('Responsable',     emp.responsible or '—',                                clean_emp.responsible or '—'),
                    ('Líder',           emp.leader or '—',                                     clean_emp.leader or '—'),
                    ('Equipo',          emp.team or '—',                                       clean_emp.team or '—'),
                    ('Teléfono',        emp.phone_number or '—',                               clean_emp.phone_number or '—'),
                    ('Email',           emp.email or '—',                                      clean_emp.email or '—'),
                    ('Dirección',       emp.address or '—',                                    clean_emp.address or '—'),
                ]
                for label, val_nuevo, val_viejo in campos:
                    if str(val_nuevo or '').strip().lower() != str(val_viejo or '').strip().lower():
                        diferencias.append({
                            'campo':    label,
                            'anterior': val_viejo or '—',
                            'nuevo':    val_nuevo or '—',
                        })

                # Si solo cambió razón social (y apellido coincide), también es misma persona
                if not es_misma_persona and diferencias:
                    solo_company = all(d['campo'] == 'Razón Social' for d in diferencias)
                    if solo_company:
                        es_misma_persona = True

            tiene_duplicado = clean_emp is not None and clean_emp.is_active

            # Omitir casos donde el duplicado es una persona diferente (no se toma acción)
            if tiene_duplicado and not es_misma_persona:
                continue

            # Preview completo para el modal: todos los campos, marcando los que cambian
            preview_rows = [{
                'campo':   'Username',
                'antes':   emp.user.username,
                'despues': clean_username,
                'cambio':  True,
            }]
            def _cv(emp_obj, attr, fallback='—'):
                val = getattr(emp_obj, attr, None)
                return str(val) if val else fallback

            def _antes(attr, fallback='—'):
                if not clean_emp:
                    return getattr(emp, attr, None) or fallback
                val = getattr(clean_emp, attr, None)
                return str(val) if val else fallback

            field_defs = [
                ('Nombre',              emp.first_name,                                         _antes('first_name', emp.first_name)),
                ('Apellidos',           emp.last_name,                                          _antes('last_name',  emp.last_name)),
                ('Razón Social',        emp.company or '—',                                     _antes('company')),
                ('Departamento',        str(emp.department or '—'),                             str(clean_emp.department or '—') if clean_emp else str(emp.department or '—')),
                ('Puesto',              emp.job_position.title if emp.job_position else '—',    (clean_emp.job_position.title if clean_emp.job_position else '—') if clean_emp else (emp.job_position.title if emp.job_position else '—')),
                ('Estación',            str(emp.station or '—'),                                str(clean_emp.station or '—') if clean_emp else str(emp.station or '—')),
                ('RFC',                 emp.rfc or '—',                                         _antes('rfc')),
                ('IMSS',                emp.imss or '—',                                        _antes('imss')),
                ('CURP',                emp.curp or '—',                                        _antes('curp')),
                ('Sexo',                emp.gender or '—',                                      _antes('gender')),
                ('Fecha de ingreso',    str(emp.start_date or '—'),                             _antes('start_date', str(emp.start_date or '—'))),
                ('Fecha de nacimiento', str(emp.birth_date or '—'),                             _antes('birth_date', str(emp.birth_date or '—'))),
                ('Antigüedad',          emp.seniority_raw or '—',                               _antes('seniority_raw')),
                ('Salario diario',      str(emp.daily_salary or '—'),                           _antes('daily_salary', str(emp.daily_salary or '—'))),
                ('Fondo de ahorro',    str(emp.saving_fund or '—'),                             _antes('saving_fund', str(emp.saving_fund or '—'))),
                ('Responsable',         emp.responsible or '—',                                 _antes('responsible')),
                ('Líder',               emp.leader or '—',                                      _antes('leader')),
                ('Equipo',              emp.team or '—',                                        _antes('team')),
                ('Teléfono',            emp.phone_number or '—',                                _antes('phone_number')),
                ('Email',               emp.email or '—',                                       _antes('email')),
                ('Dirección',           emp.address or '—',                                     _antes('address')),
            ]
            for label, val_despues, val_antes in field_defs:
                cambio = str(val_despues).strip().lower() != str(val_antes).strip().lower()
                preview_rows.append({
                    'campo':   label,
                    'antes':   val_antes,
                    'despues': val_despues,
                    'cambio':  cambio,
                })

            sufijo_cases.append({
                'emp': emp,
                'username_actual':   emp.user.username,
                'username_correcto': clean_username,
                'tiene_duplicado':   tiene_duplicado,
                'emp_duplicado':     clean_emp if tiene_duplicado else None,
                'es_misma_persona':  es_misma_persona,
                'diferencias':       diferencias,
                'preview':           preview_rows,
            })

    return render(request, "users/inconsistencias.html", {
        "sufijo_cases": sufijo_cases,
    })


@login_required
@user_passes_test(lambda u: u.username.upper() in ('SUPERUSER', 'JOSE'))
@require_POST
def corregir_inconsistencia_view(request, emp_id):
    from django.db import transaction

    emp_nuevo = get_object_or_404(Employee, id=emp_id, is_active=True)

    if not emp_nuevo.user:
        messages.error(request, f"El empleado {emp_nuevo.first_name} no tiene usuario asignado.")
        return redirect('user_inconsistencias')

    clean_username = str(emp_nuevo.employee_number)

    with transaction.atomic():
        clean_user = User.objects.filter(username=clean_username).first()

        if clean_user:
            # Caso CON duplicado: emp viejo tiene el username limpio
            try:
                emp_viejo = clean_user.employee
            except Exception:
                emp_viejo = None

            suffix_user = emp_nuevo.user

            # 1. Liberar clean_user del emp viejo primero (unique constraint)
            if emp_viejo:
                Employee.objects.filter(id=emp_viejo.id).update(is_active=False, user=None)

            # 2. Asignar clean_user al emp nuevo
            Employee.objects.filter(id=emp_nuevo.id).update(user=clean_user)

            # 3. Borrar usuario sufijado
            suffix_user.delete()

            messages.success(request, f"{emp_nuevo.first_name} {emp_nuevo.last_name}: username corregido a '{clean_username}', duplicado desactivado.")

        else:
            # Caso SIN duplicado: solo renombrar el username
            user = emp_nuevo.user
            old_username = user.username
            user.username = clean_username
            user.save(update_fields=['username'])

            messages.success(request, f"{emp_nuevo.first_name} {emp_nuevo.last_name}: username renombrado de '{old_username}' a '{clean_username}'.")

    return redirect('user_inconsistencias')