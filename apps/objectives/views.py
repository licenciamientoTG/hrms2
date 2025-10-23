from django.shortcuts import render
from django.contrib.auth.decorators import login_required,user_passes_test
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.dateparse import parse_date
from .models import ObjectiveCycle
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from apps.employee.models import Employee
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
    q = (request.GET.get('q') or '').strip()

    qs = ObjectiveCycle.objects.all().order_by('-created_at')
    if q:
        qs = qs.filter(Q(name__icontains=q))

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get('page') or 1)

    ctx = {
        "q": q,
        "cycles": page_obj.object_list,
        "page_obj": page_obj,
    }
    return render(request, "objectives/admin/objectives_dashboard_admin.html", ctx)

#esta vista solo nos manda a user_objective.html
@login_required
def user_objective(request):
    display_name = (request.user.get_full_name() or request.user.username).strip()
    ctx = {"user_name": display_name}
    return render(request, "objectives/user/objectives_dashboard_user.html", ctx)


def _team_candidates_for(user):
    """
    Devuelve empleados activos del mismo team del usuario.
    Si el usuario no tiene registro/ team, devuelve solo él mismo (si está activo).
    """
    me = Employee.objects.filter(user=user, is_active=True).first()
    if not me or not me.team:
        return Employee.objects.filter(user=user, is_active=True).select_related('user')

    return (Employee.objects
            .filter(is_active=True, team=me.team)
            .select_related('user')
            .order_by('first_name', 'last_name'))

@login_required
def create_objective(request):
    # --- ciclos vigentes ---
    today = timezone.localdate()
    cycles = (ObjectiveCycle.objects
              .filter(Q(end_date__isnull=True) | Q(end_date__gte=today))
              .filter(Q(start_date__isnull=True) | Q(start_date__lte=today))
              .order_by('end_date', 'name'))

    # --- candidatos (mismo team + activos) ---
    candidates = list(_team_candidates_for(request.user))
    allowed_user_ids = {e.user_id for e in candidates}

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()

        # Si usas <select multiple name="owners">:
        # owners_ids = [int(x) for x in request.POST.getlist("owners") if str(x).isdigit()]

        # Si sigues usando los chips con <input hidden name="owners" value="1,2,3">,
        # cambia la línea anterior por:
        owners_ids = [int(x) for x in (request.POST.get("owners") or "").split(',') if x.isdigit()]

        # Validaciones
        has_errors = False
        if not title:
            messages.error(request, "Indica un título para el objetivo.")
            has_errors = True

        if not owners_ids:
            # si no mandan responsables, nos aseguramos que al menos se asigne a sí mismo
            me_id = request.user.id
            if me_id in allowed_user_ids:
                owners_ids = [me_id]
            else:
                messages.error(request, "No hay responsables válidos para tu equipo.")
                has_errors = True

        # Seguridad: solo IDs dentro de los candidatos del team
        if not set(owners_ids).issubset(allowed_user_ids):
            messages.error(request, "Sólo puedes elegir responsables activos de tu mismo equipo.")
            has_errors = True

        if not has_errors:
            # TODO: Guarda el objetivo y relaciona owners_ids
            # Objective.objects.create(...); m2m a usuarios owners_ids
            return redirect("objective_view")

        # Con errores, re-render con lo que ya tenían
        return render(request, "objectives/user/create_objective.html", {
            "cycles": cycles,
            "candidates": candidates,
        })

    # GET
    return render(request, "objectives/user/create_objective.html", {
        "cycles": cycles,
        "candidates": candidates,
    })

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
        return redirect("admin_objective")

    # GET
    return render(request, "objectives/admin/cycle_form.html", {"formdata": {}})

@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_POST
def cycle_delete(request, pk):
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('ajax') == '1'
    try:
        cycle = ObjectiveCycle.objects.get(pk=pk)
    except ObjectiveCycle.DoesNotExist:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': 'not_found'}, status=404)
        messages.error(request, "El ciclo no existe.")
        return redirect('admin_objective')

    cycle.delete()
    if is_ajax:
        return JsonResponse({'ok': True})
    messages.success(request, "Ciclo eliminado.")
    return redirect('admin_objective')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def obj_cycle_edit(request, pk):
    cycle = get_object_or_404(ObjectiveCycle, pk=pk)

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        start_date = parse_date(request.POST.get("start_date") or "") or None
        end_date   = parse_date(request.POST.get("end_date") or "") or None
        limit_enabled = request.POST.get("limit_enabled") == "on"

        min_raw = request.POST.get("min_objectives")
        max_raw = request.POST.get("max_objectives")
        min_obj = int(min_raw) if min_raw not in ("", None) and str(min_raw).isdigit() else None
        max_obj = int(max_raw) if max_raw not in ("", None) and str(max_raw).isdigit() else None

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
            min_obj = None
            max_obj = None

        if not has_errors:
            cycle.name = name
            cycle.start_date = start_date
            cycle.end_date = end_date
            cycle.limit_enabled = limit_enabled
            cycle.min_objectives = min_obj
            cycle.max_objectives = max_obj
            cycle.save()
            return redirect("admin_objective")

        # repinta con lo que envió el usuario
        formdata = {
            "name": name,
            "start_date": request.POST.get("start_date") or "",
            "end_date": request.POST.get("end_date") or "",
            "limit_enabled": limit_enabled,
            "min_objectives": min_raw or "",
            "max_objectives": max_raw or "",
        }
        return render(request, "objectives/admin/cycle_form.html", {
            "formdata": formdata,
            "is_edit": True,
            "obj": cycle,
        })

    # GET → valores iniciales del ciclo
    formdata = {
        "name": cycle.name,
        "start_date": cycle.start_date.isoformat() if cycle.start_date else "",
        "end_date": cycle.end_date.isoformat() if cycle.end_date else "",
        "limit_enabled": cycle.limit_enabled,
        "min_objectives": "" if cycle.min_objectives is None else cycle.min_objectives,
        "max_objectives": "" if cycle.max_objectives is None else cycle.max_objectives,
    }
    return render(request, "objectives/admin/cycle_form.html", {
        "formdata": formdata,
        "is_edit": True,
        "obj": cycle,
    })