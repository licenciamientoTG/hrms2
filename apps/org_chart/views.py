from django.shortcuts import render, redirect
from apps.employee.models import Employee, JobPosition, Department
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.http import JsonResponse
from django.db.models import Q
from django.db import models


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
    Organigrama a partir de la BD:
    - Cada Employee es un nodo
    - responsible = jefe inmediato (padre en el árbol)
    """

    # Detectar tipo de campo 'responsible'
    field = Employee._meta.get_field("responsible")
    is_fk_responsible = (
        isinstance(field, models.ForeignKey)
        and field.remote_field
        and field.remote_field.model is Employee
    )

    # Base queryset
    qs = (
        Employee.objects
        .select_related("job_position", "department", "user")
        .filter(is_active=True, user__isnull=False, user__is_active=True)
    )

    # Solo hacemos select_related('responsible') si realmente es FK
    if is_fk_responsible:
        qs = qs.select_related("responsible")

    nodes = []

    for emp in qs:
        full_name = f"{emp.first_name} {emp.last_name}".strip() or emp.employee_number

        # jefe inmediato (boss) según el tipo de campo
        boss = None
        if is_fk_responsible:
            boss = getattr(emp, "responsible", None)
        else:
            # asumimos que 'responsible' guarda algún identificador (ej. employee_number)
            resp_val = getattr(emp, "responsible", None)
            if resp_val:
                boss = Employee.objects.filter(employee_number=str(resp_val)).first()

        # foto (si la usas)
        img = ""
        if getattr(emp, "photo", None):
            try:
                img = emp.photo.url
            except ValueError:
                img = ""

        nodes.append({
            "id": emp.id,                               # identificador único del nodo
            "pid": boss.id if boss else None,           # padre = responsable
            "name": full_name,                          # nombre
            "title": emp.job_position.title if emp.job_position else "",
            "email": emp.email or (emp.user.email if emp.user else ""),
            "department": emp.department.name if emp.department else "",
            "company": str(emp.company) if getattr(emp, "company", None) else "",
            "img": img,
        })

    return JsonResponse({"nodes": nodes})