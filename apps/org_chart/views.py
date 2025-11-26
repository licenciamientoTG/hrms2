from django.shortcuts import render, redirect
from apps.employee.models import Employee, JobPosition, Department
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.http import JsonResponse
from django.db.models import Q
from django.db import models
from django.views.decorators.http import require_POST
from django.db.models import Prefetch


# esta vista te redirige a las vistas de usuario y administrador
@login_required
def org_chart_view(request):
    if request.user.is_superuser:
        return redirect('org_chart_admin')
    else:
        return redirect('org_chart_user')

# esta vista es para el administrador
@login_required
@user_passes_test(lambda u: u.is_superuser)
def org_chart_admin(request):

    return render(request, 'org_chart/admin/org_chart_admin.html')

# esta vista es para el usuario
@login_required
def org_chart_user(request):

    return render(request, 'org_chart/user/org_chart_user.html')

MAX_NODES = 190  # margen por el límite de 200 en OrgChartJS


def _find_emp(emp_no=None, name_like=None):
    qs = (Employee.objects
          .select_related("user", "job_position", "department")
          .filter(is_active=True, user__isnull=False, user__is_active=True))
    if emp_no:
        emp = qs.filter(employee_number=str(emp_no)).first()
        if emp:
            return emp
    if name_like:
        return (qs.filter(Q(first_name__icontains=name_like) | Q(last_name__icontains=name_like))
                  .order_by("last_name", "first_name")
                  .first())
    return None

# vista de organigrama
@login_required
def org_chart_data_1(request):
    """
    Organigrama basado en JobPosition.reports_to:

    - Cada JobPosition es un nodo.
    - Si tiene empleado activo, se muestra el nombre del empleado.
    - Si no, se marca como VACANTE.
    """

    # Empleados activos (ajusta el filtro si necesitas algo más)
    active_employees_qs = (
        Employee.objects
        .filter(is_active=True)
        .select_related("department", "user", "job_position")
    )

    # Todas las posiciones, con sus empleados activos prefetchados
    job_positions = (
        JobPosition.objects
        .all()
        .prefetch_related(
            Prefetch(
                "employee_set",
                queryset=active_employees_qs,
                to_attr="current_employees",
            )
        )
    )

    nodes = []

    for position in job_positions:
        # Empleado asociado (si hay varios, tomamos el primero)
        employees = getattr(position, "current_employees", [])
        employee = employees[0] if employees else None

        # --- Datos de presentación ---
        if employee:
            full_name = f"{employee.first_name} {employee.last_name}".strip()
            name_display = full_name or "Sin nombre"
            is_vacant = False

            # Foto segura
            if getattr(employee, "photo", None) and employee.photo.name:
                photo_url = employee.photo.url
            else:
                photo_url = "/static/default_photo.png"
        else:
            name_display = "VACANTE"
            is_vacant = True
            photo_url = "/static/vacant_icon.png"

        title_display = getattr(position, "title", "") or ""

        # Departamento (si existe el FK)
        department_obj = getattr(position, "department", None)
        department_name = getattr(department_obj, "name", "") if department_obj else ""

        # Company (si el modelo tiene ese campo)
        company_val = getattr(position, "company", None)
        company_str = str(company_val) if company_val else ""

        # --- Jerarquía: padre = reports_to ---
        reports_to = getattr(position, "reports_to", None)
        parent_id = reports_to.pk if reports_to else None

        nodes.append({
            "id": position.pk,                          # ID del puesto
            "pid": parent_id,                           # ID del puesto padre
            "name": name_display,                       # nombre o “VACANTE”
            "title": title_display,                     # título del puesto
            "department": department_name,              # depto
            "company": company_str,                     # empresa (si aplica)
            "img": photo_url,                           # foto/icono
            "is_vacant": is_vacant,                     # bandera de vacante
            "employee_id": employee.pk if employee else None,
        })

    return JsonResponse({"nodes": nodes})

@require_POST
def api_move_position(request):
    # Asegúrate de validar que el usuario es administrador
    if not request.user.is_superuser:
        return JsonResponse({'error': 'No autorizado'}, status=403)

    # Lógica para mover la posición (JobPosition)
    try:
        moved_id = request.POST.get('moved_position_id')
        new_parent_id = request.POST.get('new_parent_id') # Puede ser None para el nodo raíz

        moved_position = JobPosition.objects.get(pk=moved_id)
        
        if new_parent_id:
            new_parent = JobPosition.objects.get(pk=new_parent_id)
            moved_position.reports_to = new_parent
        else:
            moved_position.reports_to = None # Es la nueva raíz del organigrama

        moved_position.save()
        return JsonResponse({'status': 'success', 'message': 'Posición movida exitosamente'})

    except JobPosition.DoesNotExist:
        return JsonResponse({'error': 'Posición no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)