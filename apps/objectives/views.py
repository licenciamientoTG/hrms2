from django.shortcuts import render
from django.contrib.auth.decorators import login_required,user_passes_test
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.dateparse import parse_date
from .models import ObjectiveCycle

#esta vista solo nos separa la vista del usuario y del administrador por medio de su url
@login_required
def objective_view(request):
    if request.user.is_superuser:
        return redirect('admin_objective')
    else:
        return redirect('user_objective')

#esta vista solo nos manda a admin_staff_requisitions.html
@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_objective(request):
    return render(request, 'objectives/admin/objectives_dashboard_admin.html')

#esta vista solo nos manda a user_objective.html
@login_required
def user_objective(request):
    display_name = (request.user.get_full_name() or request.user.username).strip()
    ctx = {"user_name": display_name}
    return render(request, "objectives/user/objectives_dashboard_user.html", ctx)


@login_required
def create_objective(request):
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        if not title:
            messages.error(request, "Indica un título para el objetivo.")
        else:
            return redirect("objective_view")
    return render(request, "objectives/user/create_objective.html")

# --- ADMIN: lista de ciclos (pantalla principal de admin de objetivos)
@login_required
@user_passes_test(lambda u: u.is_superuser)
def obj_cycles_admin(request):
    q = request.GET.get('q', '').strip()
    ctx = {
        "q": q,
        "cycles": [],   # por ahora vacío (solo plantilla)
        "page_obj": None,
    }
    return render(request, "objectives/admin/objectives_dashboard_admin.html", ctx)

# --- ADMIN: formulario de creación de ciclo (solo plantilla)

@login_required
@user_passes_test(lambda u: u.is_superuser)
def obj_cycle_create(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        start_date = parse_date(request.POST.get("start_date") or "") or None
        end_date   = parse_date(request.POST.get("end_date") or "") or None

        # Checkbox con name="limit_enabled"
        limit_enabled = request.POST.get("limit_enabled") == "on"

        # Cast de números
        min_raw = request.POST.get("min_objectives")
        max_raw = request.POST.get("max_objectives")
        min_obj = int(min_raw) if min_raw not in ("", None) and min_raw.isdigit() else None
        max_obj = int(max_raw) if max_raw not in ("", None) and max_raw.isdigit() else None

        has_errors = False
        if not name:
            messages.error(request, "El nombre es obligatorio.")
            has_errors = True

        if start_date and end_date and end_date < start_date:
            messages.error(request, "La fecha de fin debe ser posterior a la de inicio.")
            has_errors = True

        if limit_enabled:
            if min_obj is None or max_obj is None:
                messages.error(request, "Indica mínimo y máximo de objetivos.")
                has_errors = True
            elif min_obj > max_obj:
                messages.error(request, "El mínimo no puede ser mayor al máximo.")
                has_errors = True
        else:
            # si no hay límite, no guardes números
            min_obj = None
            max_obj = None

        if has_errors:
            # repinta con lo que el usuario escribió
            formdata = {
                "name": name,
                "start_date": request.POST.get("start_date") or "",
                "end_date": request.POST.get("end_date") or "",
                "limit_enabled": limit_enabled,
                "min_objectives": min_raw or "",
                "max_objectives": max_raw or "",
            }
            return render(request, "objectives/admin/cycle_form.html", {"formdata": formdata})

        # ✅ crear registro
        ObjectiveCycle.objects.create(
            name=name,
            start_date=start_date,
            end_date=end_date,
            limit_enabled=limit_enabled,
            min_objectives=min_obj,
            max_objectives=max_obj,
            created_by=request.user,
        )
        return redirect("obj_cycles_admin")

    # GET
    return render(request, "objectives/admin/cycle_form.html", {"formdata": {}})