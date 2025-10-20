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

from django.db.models import Q

@login_required
def user_dashboard(request):
    q = (request.GET.get('q') or '').strip()

    empleados_qs = (
        Employee.objects
        .select_related('user')
        .filter(user__isnull=False)
        .order_by('-created_at')
    )

    if q:
        empleados_qs = empleados_qs.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(user__username__icontains=q)
        )

    # --- Paginación (sin límite cuando hay búsqueda) ---
    page_size   = int(request.GET.get('page_size', 10))
    page_number = request.GET.get('page', 1)

    if q:
        page_obj = None
        empleados_iter = empleados_qs            # todos los matches
    else:
        paginator   = Paginator(empleados_qs, page_size)
        page_obj    = paginator.get_page(page_number)
        empleados_iter = page_obj.object_list

    return render(request, 'users/user_dashboard.html', {
        'empleados': empleados_iter,            # <-- usa empleados_iter
        'permissions': Permission.objects.all(),
        'page_obj': page_obj,                   # será None cuando hay q
        'page_size': page_size,
        'q': q,
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