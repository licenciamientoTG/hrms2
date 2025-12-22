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

    return render(request, 'users/manage_permissions.html', {
        'user_obj': user_obj,
        'groups': grupos,
        'permissions': permisos,
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