from django.shortcuts import render, redirect
from apps.employee.models import Employee, JobPosition, Department
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.http import JsonResponse
from django.db.models import Q


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

@login_required
def org_chart_data_1(request):
    # Organigrama #1 exactamente como la imagen

    people = {
        "ROOT":      {"emp_no": None, "name_like": "Enrique López", "title": "Dirección General"},
        # Staff (al costado del root, en este orden)
        "EDITH":     {"emp_no": None, "name_like": "Edith Gallegos",    "title": "Asistente Dirección",                  "assistant": True, "order": 1},
        "DAVID":     {"emp_no": None, "name_like": "David Castro",      "title": "Supervisor Proyectos Comerciales",     "assistant": True, "order": 2},
        "ANTONIO":   {"emp_no": None, "name_like": "Antonio Meléndez",  "title": "Supervisor Proyectos Comerciales",     "assistant": True, "order": 3},
        "GUADALUPE": {"emp_no": None, "name_like": "Guadalupe Ordóñez", "title": "Psicóloga",                            "assistant": True, "order": 99},
        # Fila inferior izquierda → derecha
        "MARIBEL":   {"emp_no": None, "name_like": "Maribel García",    "title": "Dirección Administración y Finanzas",  "order": 10},
        "HECTOR":    {"emp_no": None, "name_like": "Héctor Larrinaga",  "title": "Director Comercial y Operaciones",     "order": 20},
        "DIANA":     {"emp_no": None, "name_like": "Diana Cano",        "title": "Gerente Capital Humano",               "order": 30},
        "ALFREDO":   {"emp_no": None, "name_like": "Alfredo Escalera",  "title": "Gerente Proyectos",                    "order": 40},
        "JOEL":      {"emp_no": None, "name_like": "Joel Valenciano",   "title": "Jefe Jurídico",                        "order": 50},
        "HEBER":     {"emp_no": None, "name_like": "Heber Alarcón",     "title": "Gerente Auditoría",                    "order": 60},
        "TERESA":    {"emp_no": None, "name_like": "Teresa Cervantes",  "title": "Jefe Administración y Finanzas",       "order": 70},
    }

    def node_from(key, pid):
        cfg = people[key]
        emp = _find_emp(emp_no=cfg.get("emp_no"), name_like=cfg.get("name_like"))
        name  = "—"
        title = cfg.get("title", "")
        email = ""
        if emp:
            name = f"{emp.first_name} {emp.last_name}".strip() or emp.employee_number
            if not title:
                title = getattr(getattr(emp, "job_position", None), "title", "") or ""
            email = emp.email or ""
        node = {
            "id": f"N_{key}",
            "pid": pid,
            "name": name,
            "title": title,
            "type": "employee",
            "img": "",
            "email": email,
            "order": cfg.get("order", 0),
        }
        if cfg.get("assistant"):
            node["assistant"] = True
        return node

    nodes = []
    nodes.append(node_from("ROOT", None))
    for key in ["EDITH", "DAVID", "ANTONIO", "GUADALUPE",
                "MARIBEL", "HECTOR", "DIANA", "ALFREDO", "JOEL", "HEBER", "TERESA"]:
        nodes.append(node_from(key, "N_ROOT"))

    # Ordenamos: primero assistants (por order), luego hijos normales (por order)
    root_id = "N_ROOT"
    assistants = sorted([n for n in nodes if n.get("assistant") and n["pid"] == root_id], key=lambda x: x["order"])
    children   = sorted([n for n in nodes if not n.get("assistant") and n["pid"] == root_id], key=lambda x: x["order"])
    others     = [n for n in nodes if n["id"] not in {root_id, *[a["id"] for a in assistants], *[c["id"] for c in children]}]
    ordered    = [nodes[0], *assistants, *children, *others]

    return JsonResponse({"nodes": ordered})