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
    from collections import defaultdict
    employees = (
        Employee.objects
        .filter(is_active=True)
        .select_related("user", "job_position", "department")
    )

    if not employees.exists():
        return JsonResponse({"error": "No hay empleados activos"}, status=404)

    # --- helpers de nombres ---------------------------------
    def normalize_text(s: str) -> str:
        return " ".join((s or "").split()).strip().lower()

    def get_first_last(emp: Employee):
        first = (getattr(emp, "first_name", "") or "").strip()
        last = (getattr(emp, "last_name", "") or "").strip()
        if (not first and not last) and emp.user:
            full = emp.user.get_full_name() or emp.user.username
            parts = full.split()
            if len(parts) >= 2:
                first = " ".join(parts[:-1])
                last = parts[-1]
            else:
                first = full
        return first, last

    # --- mapa de nombres -> id (en varios formatos) ----------
    name_to_id = {}
    for emp in employees:
        first, last = get_first_last(emp)
        if not (first or last):
            continue

        key_fl = normalize_text(f"{first} {last}")            # Diana Cristina Cano Valle
        key_lf_comma = normalize_text(f"{last}, {first}")     # Cano Valle, Diana Cristina
        key_lf = normalize_text(f"{last} {first}")            # Cano Valle Diana Cristina

        for k in (key_fl, key_lf_comma, key_lf):
            if k:
                name_to_id[k] = emp.id

    nodes = {}
    for emp in employees:
        first, last = get_first_last(emp)
        full_name = " ".join([first, last]).strip() or "(Sin nombre)"

        if getattr(emp, "photo", None) and emp.photo.name:
            photo_url = emp.photo.url
        else:
            photo_url = "/static/template/img/logos/logo_sencillo.png"

        job_title = emp.job_position.title if getattr(emp, "job_position", None) else ""
        department = emp.department.name if getattr(emp, "department", None) else ""

        resp_raw = (getattr(emp, "responsible", "") or "").strip()
        parent_id = None

        if resp_raw and resp_raw.lower() not in ("vacante", "vacant", "sin jefe", "-"):
            key = normalize_text(resp_raw)
            if "," in resp_raw and key not in name_to_id:
                last_part, first_part = resp_raw.split(",", 1)
                flipped = f"{first_part.strip()} {last_part.strip()}"
                key = normalize_text(flipped)

            found_id = name_to_id.get(key)

            # 🔴 si el responsable soy yo mismo, lo tomamos como "sin jefe"
            if found_id and found_id != emp.id:
                parent_id = found_id
            else:
                parent_id = None

        nodes[emp.id] = {
            "id": emp.id,
            "name": full_name,
            "title": job_title,
            "department": department,
            "photo": photo_url,
            "is_vacant": False,
            "parent_id": parent_id,
            "team": getattr(emp, "team", "") or "",
            "responsible": resp_raw or "",
            "employee_number": emp.employee_number or "",
        }

    # --- construir árbol -------------------------------------
    children_by_parent = defaultdict(list)
    for node in nodes.values():
        pid = node["parent_id"]
        # 🔴 por seguridad: si el padre es el mismo, lo anulamos
        if pid and pid in nodes and pid != node["id"]:
            children_by_parent[pid].append(node)
        else:
            node["parent_id"] = None

    roots = [n for n in nodes.values() if n["parent_id"] is None]

    def attach_children(node):
        hijos = children_by_parent.get(node["id"], [])
        node["children"] = [attach_children(h) for h in hijos]
        return node

    if len(roots) == 1:
        tree = attach_children(roots[0])
    else:
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

            first = (boss.first_name or "").strip()
            last = (boss.last_name or "").strip()

            if (not first and not last) and boss.user:
                full = boss.user.get_full_name() or boss.user.username
                parts = full.split()
                if len(parts) >= 2:
                    first = " ".join(parts[:-1])
                    last = parts[-1]
                else:
                    first = full

            # Guardamos como "Apellido, Nombre" para ser consistente
            if first or last:
                boss_name = f"{last}, {first}".strip().strip(",")
            else:
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
