from django.shortcuts import render, redirect
from apps.employee.models import Employee, JobPosition, Department
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from collections import defaultdict


# esta vista te redirige a las vistas de usuario y administrador
@login_required
def org_chart_view(request):
    if request.user.is_superuser:
        return redirect('org_chart_admin')
    else:
        return redirect('org_chart_user')


# vista admin
@login_required
@user_passes_test(lambda u: u.is_superuser)
def org_chart_admin(request):
    return render(request, 'org_chart/admin/org_chart_admin.html')


# vista usuario
@login_required
def org_chart_user(request):
    return render(request, 'org_chart/user/org_chart_user.html')


# ==== NUEVO: datos para jquery OrgChart (estructura en árbol) ====

@login_required
def org_chart_data_1(request):
    """
    Organigrama basado en Employee.responsible (texto):
    - Cada empleado es un nodo.
    - parent = empleado cuyo nombre coincide con 'responsible'.
    - 'Vacante', vacío o None = sin jefe (raíz).
    """

    employees = (
        Employee.objects
        .filter(is_active=True)
        .select_related("user", "job_position", "department")
    )

    if not employees.exists():
        return JsonResponse({"error": "No hay empleados activos"}, status=404)

    # Mapa nombre_normalizado -> Employee.id
    def normalize_name(emp: Employee) -> str:
        name = ""
        if emp.first_name or emp.last_name:
            name = f"{emp.first_name or ''} {emp.last_name or ''}"
        elif emp.user:
            name = emp.user.get_full_name() or emp.user.username
        return " ".join(name.split()).strip().lower()

    name_to_id = {}
    for emp in employees:
        key = normalize_name(emp)
        if key:  # evitar vacío
            # si hay duplicados se quedará con el último, pero al menos tendremos algo
            name_to_id[key] = emp.id

    nodes = {}
    for emp in employees:
        full_name = normalize_name(emp).title()  # para mostrar bonito

        # Foto
        if getattr(emp, "photo", None) and emp.photo.name:
            photo_url = emp.photo.url
        else:
            photo_url = "/static/template/img/logos/logo_sencillo.png"

        job_title = emp.job_position.title if getattr(emp, "job_position", None) else ""
        department = emp.department.name if getattr(emp, "department", None) else ""

        # --- calcular parent_id a partir de 'responsible' texto ---
        resp_raw = (emp.responsible or "").strip() if hasattr(emp, "responsible") else ""
        parent_id = None

        if resp_raw and resp_raw.lower() not in ("vacante", "vacant", "sin jefe", "-"):
            key = " ".join(resp_raw.split()).strip().lower()
            parent_id = name_to_id.get(key)  # puede ser None si no se encuentra

        nodes[emp.id] = {
            "id": emp.id,
            "name": full_name or "(Sin nombre)",
            "title": job_title,
            "department": department,
            "photo": photo_url,
            "is_vacant": False,
            "parent_id": parent_id,
            "team": getattr(emp, "team", "") or "",
            "responsible": getattr(emp, "responsible", "") or "",
        }

    # --- Construir árbol ---
    children_by_parent = defaultdict(list)

    for node in nodes.values():
        pid = node["parent_id"]
        if pid and pid in nodes:
            children_by_parent[pid].append(node)
        else:
            node["parent_id"] = None  # lo tratamos como raíz

    roots = [n for n in nodes.values() if n["parent_id"] is None]

    def attach_children(node):
        hijos = children_by_parent.get(node["id"], [])
        node["children"] = [attach_children(h) for h in hijos]
        return node

    if len(roots) == 1:
        tree = attach_children(roots[0])
    else:
        # raíz artificial para tener un solo root
        tree = {
            "id": "ORG_ROOT",
            "name": "Organigrama",
            "title": "",
            "department": "",
            "photo": "/static/template/img/logos/logo_sencillo.png",
            "is_vacant": False,
            "children": [attach_children(r) for r in roots],
        }

    return JsonResponse(tree, safe=False)


# ==== API para actualizar el jefe al hacer drag & drop ====

@require_POST
@login_required
@user_passes_test(lambda u: u.is_superuser)
def api_move_position(request):
    try:
        moved_id = request.POST.get('moved_position_id')
        new_parent_id = request.POST.get('new_parent_id')  # puede ser '' o None

        # Validar que sea un ID numérico
        if not moved_id or not str(moved_id).isdigit():
            return JsonResponse({'error': 'ID de empleado no enviado'}, status=400)

        moved_employee = Employee.objects.get(pk=int(moved_id))

        # Si el padre no es numérico (ej. ORG_ROOT), lo tratamos como sin jefe
        if new_parent_id and str(new_parent_id).isdigit():
            boss = Employee.objects.get(pk=int(new_parent_id))
            boss_name = f"{boss.first_name or ''} {boss.last_name or ''}".strip()
            if not boss_name and boss.user:
                boss_name = boss.user.get_full_name() or boss.user.username
            moved_employee.responsible = boss_name
        else:
            moved_employee.responsible = "Vacante"

        moved_employee.save(update_fields=['responsible'])

        return JsonResponse({'status': 'success', 'message': 'Jefe actualizado correctamente'})

    except Employee.DoesNotExist:
        return JsonResponse({'error': 'Empleado no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
