import json
from django.db.models import Q
from apps.employee.models import Employee, JobPosition
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST, require_http_methods, require_GET
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse, HttpResponseRedirect
from django.template.loader import render_to_string
from django.db.models import Max
from .models import Survey, SurveySection, SurveyQuestion, SurveyAudience, SurveyOption, SurveyResponse, SurveyAnswer
from uuid import uuid4
from departments.models import Department
from apps.location.models import Location
from django.views import View
from django.utils.decorators import method_decorator
from .services import persist_builder_state, persist_settings, persist_audience
from django.core.paginator import Paginator
from django.db.models import Case, When, Value, CharField, F
from django.contrib import messages
from django.urls import reverse
from django.db.models import Prefetch
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone
from django.db import DataError
from collections import defaultdict, Counter
import math  



try:
    from openpyxl import Workbook
except Exception:
    Workbook = None

@login_required
def survey_dashboard(request):
    return redirect('survey_dashboard_admin') if request.user.is_superuser else redirect('survey_dashboard_user')

# -------- dashboard (ya lo tenías; dejo el mismo con el fix de creator) --------
@login_required
@user_passes_test(lambda u: u.is_superuser)
def survey_dashboard_admin(request):
    q = (request.GET.get("q") or "").strip()
    sort = (request.GET.get("sort") or "-created_at").strip()

    qs = Survey.objects.select_related("creator")
    if q:
        qs = qs.filter(title__icontains=q)

    qs = qs.annotate(
        status=Case(
            When(is_active=True, then=Value("active")),
            default=Value("draft"),
            output_field=CharField(),
        )
    )

    sort_map = {"created_at": "created_at", "-created_at": "-created_at", "position": "-created_at"}
    qs = qs.order_by(sort_map.get(sort, "-created_at"), "id")

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    # Calcular métricas para cada encuesta
    start_idx = (page_obj.number - 1) * paginator.per_page
    
    # Obtener todos los IDs de encuestas en esta página
    survey_ids = [s.id for s in page_obj.object_list]
    
    # Contar respuestas enviadas por encuesta
    from django.db.models import Count
    responses_count = dict(
        SurveyResponse.objects.filter(
            survey_id__in=survey_ids,
            status='submitted'
        ).values('survey_id').annotate(
            count=Count('id')
        ).values_list('survey_id', 'count')
    )
    
    # Contar audiencia esperada por encuesta
    audience_counts = {}
    for survey in page_obj.object_list:
        try:
            aud = survey.audience
            if not aud or aud.mode == SurveyAudience.MODE_ALL:
                # Todos los usuarios activos
                total = Employee.objects.filter(
                    user__isnull=False,
                    user__is_active=True,
                    is_active=True
                ).count()
            elif aud.mode == 'segmented':
                # Calcular según filtros
                filters = aud.filters or {}
                dep_ids = filters.get('departments') or []
                pos_ids = filters.get('positions') or []
                loc_ids = filters.get('locations') or []
                user_ids = list(aud.users.values_list('id', flat=True))
                
                qs_emp = Employee.objects.filter(
                    user__isnull=False,
                    user__is_active=True,
                    is_active=True
                )
                
                # Lógica OR: usuarios específicos o cualquier filtro
                cond = Q()
                if user_ids:
                    cond |= Q(user_id__in=user_ids)
                if dep_ids:
                    cond |= Q(department_id__in=dep_ids)
                if pos_ids:
                    cond |= Q(job_position_id__in=pos_ids)
                if loc_ids:
                    cond |= Q(station_id__in=loc_ids)
                
                if cond:
                    total = qs_emp.filter(cond).distinct().count()
                else:
                    total = 0
            else:
                # Modo desconocido, contar solo usuarios explícitos
                total = aud.users.filter(is_active=True).count()
        except SurveyAudience.DoesNotExist:
            # Sin audiencia = todos los usuarios
            total = Employee.objects.filter(
                user__isnull=False,
                user__is_active=True,
                is_active=True
            ).count()
        
        audience_counts[survey.id] = total
    
    # Asignar métricas a cada encuesta
    for i, s in enumerate(page_obj.object_list, start=1):
        s.position = start_idx + i
        s.responses_count = responses_count.get(s.id, 0)
        s.expected_total  = audience_counts.get(s.id, 0)  
        
        expected = audience_counts.get(s.id, 0)
        if expected > 0:
            s.progress = round((s.responses_count / expected) * 100, 1)
        else:
            s.progress = 0.0

    ctx = {
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "q": q,
        "sort": sort
    }
    return render(request, "surveys/admin/survey_dashboard_admin.html", ctx)

@login_required
def survey_dashboard_user(request):
    user = request.user
    
    # Obtener el empleado asociado al usuario
    try:
        employee = Employee.objects.select_related(
            'department', 'job_position', 'station'
        ).get(user=user, is_active=True)
    except Employee.DoesNotExist:
        employee = None

    # Encuestas activas con prefetch de audience.users
    all_surveys = Survey.objects.filter(
        is_active=True
    ).select_related('audience').prefetch_related('audience__users')
    
    visible_surveys = []
    
    for survey in all_surveys:
        try:
            audience = survey.audience
        except SurveyAudience.DoesNotExist:
            audience = None
        
        matches = False
        
        # Sin audiencia: mostrar a todos
        if not audience:
            matches = True
        # Modo ALL: mostrar a todos
        elif audience.mode == SurveyAudience.MODE_ALL:
            matches = True
        # Modo SEGMENTED: evaluar filtros
        elif audience.mode == 'segmented':
            if employee:
                filters = audience.filters or {}
                dep_ids = filters.get('departments') or []
                pos_ids = filters.get('positions') or []
                loc_ids = filters.get('locations') or []
                
                # Verificar si el empleado cumple con algún filtro (OR)
                # Usar OR sin elif para que evalúe TODAS las condiciones
                if dep_ids and employee.department_id in dep_ids:
                    matches = True
                if pos_ids and employee.job_position_id in pos_ids:
                    matches = True
                if loc_ids and employee.station_id in loc_ids:
                    matches = True
            
            # También verificar usuarios específicos en modo segmented
            if not matches and audience.users.filter(pk=user.pk).exists():
                matches = True
        # Otros modos: verificar usuarios específicos
        else:
            if audience.users.filter(pk=user.pk).exists():
                matches = True
        
        if matches:
            visible_surveys.append(survey)

    # Obtener IDs de encuestas completadas por el usuario
    completed_survey_ids = set(
        SurveyResponse.objects.filter(
            user=user, 
            status='submitted'
        ).values_list('survey_id', flat=True)
    )

    # Separar encuestas disponibles y completadas
    # SOLO mostrar las que el usuario TODAVÍA tiene permiso de ver
    available = []
    completed = []
    
    for survey in visible_surveys:
        survey_data = {
            "id": survey.id,
            "title": survey.title,
            "take_url": reverse("survey_view_user", args=[survey.id]),
        }
        
        if survey.id in completed_survey_ids:
            survey_data["status"] = "completed"
            completed.append(survey_data)
        else:
            survey_data["status"] = "available"
            available.append(survey_data)

    context = {
        "available": available,
        "completed": completed,
    }
    return render(request, "surveys/user/survey_dashboard_user.html", context)

@login_required
@user_passes_test(lambda u: u.is_superuser)
def survey_new(request):
    return render(request, 'surveys/admin/survey_new.html', {
        "survey": None,
        "sections": [], 
    })

# ---------- AJAX ----------
def _is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'

@require_POST
@login_required
@user_passes_test(lambda u: u.is_superuser)
def section_create(request, survey_id):
    if not _is_ajax(request): return HttpResponseBadRequest("AJAX only")
    survey = get_object_or_404(Survey, pk=survey_id)
    order = (survey.sections.aggregate(m=Max('order'))['m'] or 0) + 1
    section = SurveySection.objects.create(survey=survey, order=order, title=f"Sección {order}")
    html = render_to_string('surveys/_section.html', {'section': section}, request=request)
    return JsonResponse({'ok': True, 'id': section.id, 'html': html})

@require_POST
@login_required
@user_passes_test(lambda u: u.is_superuser)
def section_rename(request, section_id):
    if not _is_ajax(request): return HttpResponseBadRequest("AJAX only")
    section = get_object_or_404(SurveySection, pk=section_id)
    title = (request.POST.get('title') or '').strip()
    if not title:
        return JsonResponse({'ok': False, 'error': 'empty'}, status=400)
    section.title = title
    section.save(update_fields=['title'])
    return JsonResponse({'ok': True})

@require_GET
@login_required
@user_passes_test(lambda u: u.is_superuser)
def section_options(request, survey_id):
    """Devuelve opciones para el select 'Después de la sección X' """
    if not _is_ajax(request): return HttpResponseBadRequest("AJAX only")
    survey = get_object_or_404(Survey, pk=survey_id)
    items = [{'id': s.id, 'label': f"Ir a la sección {s.order} ({s.title or 'Sección'})"} for s in survey.sections.all()]
    return JsonResponse({'ok': True, 'items': items})

@require_POST
@login_required
@user_passes_test(lambda u: u.is_superuser)
def question_create(request, section_id):
    if not _is_ajax(request): return HttpResponseBadRequest("AJAX only")
    section = get_object_or_404(SurveySection, pk=section_id)
    order = (section.questions.aggregate(m=Max('order'))['m'] or 0) + 1
    q = SurveyQuestion.objects.create(section=section, order=order, title=f"Pregunta {order}")
    html = render_to_string('surveys/_question.html', {'q': q}, request=request)
    return JsonResponse({'ok': True, 'id': q.id, 'html': html})

@require_POST
@login_required
@user_passes_test(lambda u: u.is_superuser)
def question_rename(request, question_id):
    if not _is_ajax(request): return HttpResponseBadRequest("AJAX only")
    q = get_object_or_404(SurveyQuestion, pk=question_id)
    title = (request.POST.get('title') or '').strip()
    if not title:
        return JsonResponse({'ok': False}, status=400)
    q.title = title
    q.save(update_fields=['title'])
    return JsonResponse({'ok': True})

@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_GET
def survey_audience_meta(request):
    deps = list(Department.objects.values('id', 'name').order_by('name'))
    pos  = list(JobPosition.objects.values('id', 'title').order_by('title'))
    locs = list(Location.objects.values('id', 'name').order_by('name'))
    return JsonResponse({'departments': deps, 'positions': pos, 'locations': locs})

@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_GET
def survey_audience_user_search(request):
    q = (request.GET.get('q') or '').strip()
    limit = int(request.GET.get('limit') or 25)

    qs = (Employee.objects
          .select_related('user', 'department', 'job_position', 'station')
          .filter(user__isnull=False, user__is_active=True, is_active=True))

    if q:
        qs = qs.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q)  |
            Q(email__icontains=q)      |
            Q(employee_number__icontains=q)
        )

    items = []
    for e in qs.order_by('first_name', 'last_name')[:limit]:
        items.append({
            'id': e.user_id,
            'label': f"{e.first_name} {e.last_name}",
            'email': e.email or (e.user.email if e.user else ''),
            'meta': ' · '.join(filter(None, [
                e.department.name if e.department else None,
                e.job_position.title if e.job_position else None,
                e.station.name if e.station else None
            ])),
            'department': e.department_id,
            'job_position': e.job_position_id,
            'station': e.station_id,
        })
    return JsonResponse(items, safe=False)

@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_POST
def survey_audience_preview(request):
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'count': 0, 'results': []})

    all_users = bool(data.get('allUsers'))
    user_ids  = list(map(int, data.get('users') or []))
    f         = data.get('filters') or {}
    dep_ids   = list(map(int, f.get('departments') or []))
    pos_ids   = list(map(int, f.get('positions')   or []))
    loc_ids   = list(map(int, f.get('locations')   or []))

    qs = (Employee.objects
          .select_related('user', 'department', 'job_position', 'station')
          .filter(user__isnull=False, user__is_active=True, is_active=True))

    if not all_users:
        # combinación por “OR”: usuarios específicos o por cualquiera de los filtros
        cond = Q()
        if user_ids: cond |= Q(user_id__in=user_ids)
        if dep_ids:  cond |= Q(department_id__in=dep_ids)
        if pos_ids:  cond |= Q(job_position_id__in=pos_ids)
        if loc_ids:  cond |= Q(station_id__in=loc_ids)

        if cond:
            qs = qs.filter(cond)
        else:
            qs = qs.none()

    qs = qs.distinct()
    total = qs.count()
    results = [{
        'name': f"{e.first_name} {e.last_name}",
        'email': e.email or (e.user.email if e.user else ''),
        'department': e.department.name if e.department else '',
        'position':   e.job_position.title if e.job_position else '',
        'location':   e.station.name if e.station else '',
    } for e in qs.order_by('first_name', 'last_name')[:50]]

    return JsonResponse({'count': total, 'results': results})


@method_decorator([login_required, user_passes_test(lambda u: u.is_superuser)], name='dispatch')
class SurveyImportView(View):
    def post(self, request, survey_id=None):
        if request.headers.get('x-requested-with') != 'XMLHttpRequest':
            return HttpResponseBadRequest("AJAX only")

        try:
            payload = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'invalid_json'}, status=400)

        title    = (payload.get('title') or 'Encuesta sin título').strip()
        builder  = payload.get('builder')  or {}
        settings = payload.get('settings') or {}
        audience = payload.get('audience') or {}

        if survey_id is None:
            # Crear
            survey = Survey.objects.create(title=title, creator=request.user)
        else:
            # Actualizar
            survey = get_object_or_404(Survey, pk=survey_id)
            if title:
                survey.title = title
                survey.save(update_fields=['title'])

        # Guardar todo
        persist_builder_state(survey, builder)
        persist_settings(survey, settings)
        persist_audience(survey, audience)

        return JsonResponse({'ok': True, 'id': survey.id})

# ---------------- Eliminar (AJAX/POST) ----------------
@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_POST
def survey_delete(request, pk: int):
    s = get_object_or_404(Survey, pk=pk)
    s.delete()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    messages.success(request, "Encuesta eliminada.")
    return redirect("survey_dashboard_admin")

# @login_required
# @user_passes_test(lambda u: u.is_superuser)
# def survey_export_csv(request, pk: int):
#     s = get_object_or_404(Survey, pk=pk)
#     import csv
#     resp = HttpResponse(content_type="text/csv; charset=utf-8")
#     resp["Content-Disposition"] = f'attachment; filename="encuesta_{s.pk}.csv"'
#     w = csv.writer(resp)

#     w.writerow(["Título", s.title])
#     w.writerow(["Activa", "Sí" if s.is_active else "No"])
#     w.writerow(["Anónima", "Sí" if s.is_anonymous else "No"])
#     w.writerow(["Creada en", s.created_at.strftime("%Y-%m-%d %H:%M")])
#     w.writerow(["Creador", s.creator.get_full_name() or s.creator.username])
#     w.writerow([])

#     w.writerow(["Sección", "Orden", "Pregunta", "Tipo", "Obligatoria", "Opción", "Correcta", "Salto a sección"])
#     for sec in s.sections.all().order_by("order"):
#         if sec.questions.exists():
#             for q in sec.questions.all().order_by("order"):
#                 if q.options.exists():
#                     for opt in q.options.all().order_by("order"):
#                         w.writerow([
#                             sec.title or f"Sección {sec.order}",
#                             sec.order,
#                             q.title,
#                             q.qtype,
#                             "Sí" if q.required else "No",
#                             opt.label,
#                             "Sí" if opt.is_correct else "No",
#                             (opt.branch_to_section.title if opt.branch_to_section else ""),
#                         ])
#                 else:
#                     w.writerow([sec.title or f"Sección {sec.order}", sec.order, q.title, q.qtype,
#                                 "Sí" if q.required else "No", "", "", ""])
#         else:
#             w.writerow([sec.title or f"Sección {sec.order}", sec.order, "", "", "", "", "", ""])
#     return resp

@login_required
@user_passes_test(lambda u: u.is_superuser)
def survey_edit(request, pk: int):
    s = (Survey.objects
         .prefetch_related(
             'sections__questions__options',
             'audience__users'
         )
         .get(pk=pk))

    # ---- Builder draft (misma forma que usa survey.js) ----
    sections_json = []
    sec_id_map = {}          # {sec_db_id: "sN"}
    qseq = 0

    # Asegura orden
    sections_qs = s.sections.all().order_by('order', 'id')

    for i, sec in enumerate(sections_qs, start=1):
        sid = f"s{i}"
        sec_id_map[sec.id] = sid

        # go_to: None | "submit" | "sX" (lo resolvemos luego)
        go_to = "submit" if sec.submit_on_finish else (sec.go_to_section_id or None)

        qs_json = []
        questions_qs = sec.questions.all().order_by('order', 'id')

        for j, q in enumerate(questions_qs, start=1):
            qseq += 1
            qj = {
                "id": f"q{qseq}",
                "title": q.title,
                "type": q.qtype,            # los nombres coinciden con tu builder
                "required": bool(q.required),
                "order": j,
            }

            if q.qtype in ("single", "multiple"):
                opts = []
                for k, op in enumerate(q.options.all().order_by('order', 'id'), start=1):
                    opts.append({
                        "label": op.label,
                        "correct": bool(op.is_correct),
                        # guardamos el id de sección para mapear luego si existe branching:
                        "_branch_to": op.branch_to_section_id,
                    })
                qj["options"] = opts or [{"label": "Opción 1", "correct": False}]

                if q.qtype == "single" and q.branch_enabled:
                    by = {}
                    for idx, op in enumerate(q.options.all().order_by('order', 'id')):
                        if op.branch_to_section_id:
                            by[idx] = op.branch_to_section_id   # temporal
                    if by:
                        qj["branch"] = {"enabled": True, "byOption": by}

            qs_json.append(qj)

        sections_json.append({
            "id": sid,
            "title": sec.title,
            "order": i,
            "go_to": go_to,   # mapeamos abajo
            "questions": qs_json
        })

    # Reemplaza ids reales por "sN"
    for sec in sections_json:
        v = sec["go_to"]
        if isinstance(v, int):
            sec["go_to"] = sec_id_map.get(v, None)

        for q in sec["questions"]:
            if q.get("branch"):
                q["branch"]["byOption"] = {
                    int(k): (sec_id_map.get(v) if isinstance(v, int) else v)
                    for k, v in q["branch"]["byOption"].items()
                }
            # limpia helper
            if "options" in q:
                for op in q["options"]:
                    op.pop("_branch_to", None)

    draft = {
        "version": 1,
        "active": bool(s.is_active),
        "lastSeq": {"section": len(sections_json), "question": qseq},
        "sections": sections_json,
    }

    # ---- Settings local ----
    settings_json = {
        "autoMessage": s.auto_message or "",
        "isAnonymous": bool(s.is_anonymous),
    }

    # ---- Audience local ----
    try:
        aud = s.audience
        audience_json = {
            "mode": aud.mode,
            "filters": aud.filters or {},
            "users": list(aud.users.values_list("id", flat=True)),
        }
    except SurveyAudience.DoesNotExist:
        audience_json = {"mode": "all", "filters": {}, "users": []}

    ctx = {
        "survey": s,
        "sections": sections_qs,
        "builder_json": json.dumps(draft, ensure_ascii=False).replace('</script>', '<\\/script>'),
        "settings_json": json.dumps(settings_json, ensure_ascii=False).replace('</script>', '<\\/script>'),
        "audience_json": json.dumps(audience_json, ensure_ascii=False).replace('</script>', '<\\/script>'),
    }
    return render(request, "surveys/admin/survey_new.html", ctx)


@login_required
def survey_view_user(request, survey_id: int):
    survey = get_object_or_404(
        Survey.objects.select_related("audience"),
        pk=survey_id,
        is_active=True
    )

    # Verificar si el usuario ya ha completado la encuesta
    if SurveyResponse.objects.filter(survey=survey, user=request.user, status='submitted').exists():
        return redirect('survey_thanks', survey_id=survey.id)

    # Verificar acceso
    aud = getattr(survey, "audience", None)
    allowed = False
    
    # Sin audiencia: permitir
    if aud is None:
        allowed = True
    # Modo ALL: permitir
    elif getattr(aud, "mode", "").lower() == "all":
        allowed = True
    # Modo SEGMENTED: evaluar filtros
    elif aud.mode == 'segmented':
        try:
            employee = Employee.objects.select_related(
                'department', 'job_position', 'station'
            ).get(user=request.user, is_active=True)
            
            filters = aud.filters or {}
            dep_ids = filters.get('departments') or []
            pos_ids = filters.get('positions') or []
            loc_ids = filters.get('locations') or []
            
            # Verificar si el empleado cumple con algún filtro (OR)
            # Usar IF sin elif para evaluar todas las condiciones
            if dep_ids and employee.department_id in dep_ids:
                allowed = True
            if pos_ids and employee.job_position_id in pos_ids:
                allowed = True
            if loc_ids and employee.station_id in loc_ids:
                allowed = True
            
            # También verificar usuarios específicos
            if not allowed and aud.users.filter(pk=request.user.pk).exists():
                allowed = True
        except Employee.DoesNotExist:
            pass
    # Usuario explícitamente incluido en otros modos
    elif aud.users.filter(pk=request.user.pk).exists():
        allowed = True
    
    if not allowed:
        return render(request, "surveys/not_allowed.html", {"survey": survey}, status=403)

    sections = _sections_for_template(survey)

    ctx = {
        "survey": {"id": survey.id, "title": survey.title},
        "sections": sections,
        "post_url": reverse("survey_take", args=[survey.id]),
        "back_url": reverse("survey_dashboard_user"),
    }
    return render(request, "surveys/user/survey_view_user.html", ctx)

def _sections_for_template(survey) -> list[dict]:
    q_qs = (
        SurveyQuestion.objects
        .order_by("order", "pk")
        .prefetch_related(
            Prefetch(
                "options",
                queryset=SurveyOption.objects
                    .select_related("branch_to_section")
                    .order_by("order", "pk")
            )
        )
    )

    sections_qs = (
        survey.sections
        .select_related("go_to_section")
        .prefetch_related(Prefetch("questions", queryset=q_qs))
        .order_by("order", "pk")
    )

    out = []
    for s in sections_qs:
        sec = {
            "id":     f"s{s.pk}",
            "title":  s.title,
            "order":  s.order,
            "go_to":  ("submit" if s.submit_on_finish
                       else (f"s{s.go_to_section_id}" if s.go_to_section_id else None)),
            "questions": [],
        }

        for q in s.questions.all():
            qd = {
                "id":       f"q{q.pk}",
                "title":    q.title,
                "type":     q.qtype,
                "required": bool(q.required),
                "options":  [],
                "branch":   None,
            }

            # Opciones para tipos con escala u opciones
            if q.qtype in {"single", "multiple", "assessment", "frecuency"}:
                opts = list(q.options.all())
                if opts:
                    qd["options"] = [{"label": o.label} for o in opts]
                else:
                    if q.qtype == "assessment":
                        qd["options"] = [{"label": x} for x in
                                         ["Muy positivo", "Positivo", "Neutral", "Negativo", "Muy Negativo"]]
                    elif q.qtype == "frecuency":
                        qd["options"] = [{"label": x} for x in
                                         ["Siempre", "Casi siempre", "Algunas veces", "Casi nunca", "Nunca"]]

                # Branching sólo para SINGLE
                if q.qtype == "single" and q.branch_enabled:
                    by = {}
                    for idx, o in enumerate(opts):
                        if o.branch_to_section_id:
                            by[idx] = f"s{o.branch_to_section_id}"
                    if by:
                        qd["branch"] = {"enabled": True, "byOption": by}

            # Para text/integer/decimal/rating no hay opciones, pero igual se agregan
            sec["questions"].append(qd)

        out.append(sec)

    return out

def _post_list(request, name_base):
    return (request.POST.getlist(f"{name_base}[]") or
            request.POST.getlist(name_base))

def _is_empty(v):
    return v is None or (isinstance(v, str) and v.strip() == "")

def _qid_to_int(qid):             # "q123" -> 123
    s = str(qid)
    return int(s[1:]) if s.startswith("q") else int(s)

def _as_int(s):
    try:
        return int(str(s).strip())
    except Exception:
        return None

def _as_decimal(s):
    if s is None:
        return None
    txt = str(s).strip().replace(",", ".")   # soporta coma decimal
    try:
        d = Decimal(txt)
    except (InvalidOperation, ValueError):
        return None
    # numeric(12,4): 8 enteros + 4 decimales
    d = d.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    # clamp simple para evitar overflow
    max_int = Decimal("99999999")  # 8 dígitos antes del punto
    if d.copy_abs() > max_int:
        return None
    return d

@login_required
@require_POST
@transaction.atomic
def take_survey(request, survey_id):
    survey = get_object_or_404(Survey, pk=survey_id, is_active=True)
    sections = _sections_for_template(survey)

    # Crear una nueva entrada de respuesta para la encuesta
    resp = SurveyResponse.objects.create(
        survey=survey,
        user=request.user,                      # SIEMPRE
        started_at=timezone.now(),
        status="draft",
        survey_title=survey.title or "",
        meta={
            "ua": request.META.get("HTTP_USER_AGENT", ""),
            "ip": request.META.get("REMOTE_ADDR", ""),
            "anonymous": bool(survey.is_anonymous),   # marca de anonimato
        },
    )

    errors = []
    answers = []

    # Guardar las respuestas de las preguntas
    for sec in sections:
        for q in sec["questions"]:
            qid_str = q["id"]
            qid = _qid_to_int(qid_str)  # Convertir ID de pregunta
            qtype = q["type"]
            name = f"q_{qid_str}"

            try:
                # Para cada tipo de pregunta, guardamos las respuestas correspondientes
                if qtype in ("single", "assessment", "frecuency"):
                    raw = request.POST.get(name, "")
                    if _is_empty(raw):
                        if q.get("required"):
                            errors.append(qid_str)
                        continue
                    idx = _as_int(raw)
                    if idx is None:
                        errors.append(qid_str)
                        continue

                    opts = q.get("options") or []
                    labels = [opts[idx]["label"]] if (0 <= idx < len(opts)) else []

                    answers.append(SurveyAnswer(
                        response=resp, question_id=qid, q_type=qtype,
                        q_title=q.get("title", ""), required=bool(q.get("required")),
                        order=_as_int(q.get("order")) or 0,
                        value_choice=idx,
                        snapshot={"options": [o["label"] for o in opts],
                                  "selected_labels": labels}
                    ))
                
                elif qtype == "multiple":
                    # checkboxes: name="q_qid[]"
                    raw_list = request.POST.getlist(name + "[]")
                    if not raw_list:
                        if q.get("required"):
                            errors.append(qid_str)
                        continue
                    # indices elegidos (ints válidos)
                    idxs = []
                    for r in raw_list:
                        ii = _as_int(r)
                        if ii is not None:
                            idxs.append(ii)
                    if not idxs and q.get("required"):
                        errors.append(qid_str)
                        continue

                    opts = q.get("options") or []
                    labels = [opts[i]["label"] for i in idxs if 0 <= i < len(opts)]

                    answers.append(SurveyAnswer(
                        response=resp, question_id=qid, q_type=qtype,
                        q_title=q.get("title",""), required=bool(q.get("required")),
                        order=_as_int(q.get("order")) or 0,
                        # si tu modelo tiene JSONField para esto:
                        value_multi=idxs,
                        snapshot={
                            "options": [o["label"] for o in opts],
                            "selected_indices": idxs,
                            "selected_labels": labels,
                        }
                    ))

                elif qtype == "text":
                    val = (request.POST.get(name) or "").strip()
                    if not val and q.get("required"):
                        errors.append(qid_str); continue
                    if val:
                        answers.append(SurveyAnswer(
                            response=resp, question_id=qid, q_type=qtype,
                            q_title=q.get("title",""), required=bool(q.get("required")),
                            order=_as_int(q.get("order")) or 0,
                            value_text=val
                        ))

                elif qtype in ("integer", "decimal"):
                    raw = request.POST.get(name)
                    val = _as_int(raw) if qtype == "integer" else _as_decimal(raw)
                    if val is None:
                        if q.get("required"):
                            errors.append(qid_str)
                        continue
                    kw = {"value_int": val} if qtype == "integer" else {"value_decimal": val}
                    answers.append(SurveyAnswer(
                        response=resp, question_id=qid, q_type=qtype,
                        q_title=q.get("title",""), required=bool(q.get("required")),
                        order=_as_int(q.get("order")) or 0,
                        **kw
                    ))

                elif qtype == "rating":
                    v = _as_int(request.POST.get(name))
                    if v is None or not (1 <= v <= 5):
                        if q.get("required"):
                            errors.append(qid_str)
                        continue
                    answers.append(SurveyAnswer(
                        response=resp, question_id=qid, q_type=qtype,
                        q_title=q.get("title",""), required=bool(q.get("required")),
                        order=_as_int(q.get("order")) or 0,
                        value_int=v
                    ))
            except DataError as e:
                transaction.set_rollback(True)
                return HttpResponseBadRequest(
                    f"Fila inválida -> qid={qid_str} qtype={qtype} "
                    f"value_text={request.POST.get(name)} value_decimal={_as_decimal(request.POST.get(name))} "
                    f"error={str(e)}"
                )

    if errors:
        transaction.set_rollback(True)
        return HttpResponseBadRequest("Faltan preguntas obligatorias.")

    if answers:
        try:
            SurveyAnswer.objects.bulk_create(answers, batch_size=200)
        except DataError as e:
            # Si bulk_create falla, seguimos diagnosticando y guardando 1x1
            for a in answers:
                try:
                    a.save(force_insert=True)
                except Exception as inner_error:
                    transaction.set_rollback(True)
                    return HttpResponseBadRequest(
                        f"Error al guardar pregunta -> qid={a.question_id} qtype={a.q_type} "
                        f"error={str(inner_error)}"
                    )
            raise

    resp.submitted_at = timezone.now()
    resp.duration_ms = int((resp.submitted_at - resp.started_at).total_seconds() * 1000)
    resp.status = "submitted"
    resp.save(update_fields=["submitted_at", "duration_ms", "status"])

    return redirect(reverse("survey_thanks", args=[survey.id]))

@login_required
def survey_thanks(request, survey_id):
    survey = get_object_or_404(Survey, pk=survey_id)
    return render(request, 'surveys/user/thanks.html', {'survey': survey})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def survey_detail_admin(request, pk: int):
    # evita import circular
    from .models import Survey, SurveySection, SurveyQuestion, SurveyAudience, SurveyOption, SurveyResponse, SurveyAnswer
    from apps.employee.models import Employee

    # ---------- helpers solo para esta vista ----------
    def _nice_step(raw_step: float) -> float:
        """Redondea el tamaño de bin a {1,2,5,10} * 10^k para ejes más 'bonitos'."""
        if not raw_step or raw_step <= 0:
            return 1.0
        exp = math.floor(math.log10(raw_step))
        f = raw_step / (10 ** exp)
        if f <= 1: nf = 1
        elif f <= 2: nf = 2
        elif f <= 5: nf = 5
        else: nf = 10
        return nf * (10 ** exp)

    def _fmt_num(x: float) -> str:
        """Formato compacto para etiquetas de eje."""
        return f"{x:.6g}"

    survey = get_object_or_404(
        Survey.objects.prefetch_related(
            Prefetch(
                'sections__questions__options',
                queryset=SurveyOption.objects.order_by('order', 'id')
            ),
        ),
        pk=pk
    )

    # ====== Métricas generales ======
    responses_count = SurveyResponse.objects.filter(
        survey=survey, status='submitted'
    ).count()

    # Audiencia esperada (igual que dashboard)
    try:
        aud = survey.audience
    except SurveyAudience.DoesNotExist:
        aud = None

    if not aud or aud.mode == SurveyAudience.MODE_ALL:
        expected = Employee.objects.filter(
            user__isnull=False, user__is_active=True, is_active=True
        ).count()
    elif aud.mode == 'segmented':
        f = aud.filters or {}
        cond = Q()
        if f.get('departments'):
            cond |= Q(department_id__in=f['departments'])
        if f.get('positions'):
            cond |= Q(job_position_id__in=f['positions'])
        if f.get('locations'):
            cond |= Q(station_id__in=f['locations'])
        uids = list(aud.users.values_list('id', flat=True))
        if uids:
            cond |= Q(user_id__in=uids)

        if cond:
            expected = (Employee.objects
                        .filter(user__isnull=False, user__is_active=True, is_active=True)
                        .filter(cond).distinct().count())
        else:
            expected = 0
    else:
        expected = aud.users.filter(is_active=True).count()

    progress = (responses_count / expected * 100) if expected else 0

    # ====== Stats por pregunta ======
    questions = (SurveyQuestion.objects
                 .filter(section__survey=survey)
                 .order_by('section__order', 'order', 'id')
                 .prefetch_related('options'))

    resp_ids = list(SurveyResponse.objects
                    .filter(survey=survey, status='submitted')
                    .values_list('id', flat=True))

    ans_by_q: dict[int, list[SurveyAnswer]] = defaultdict(list)
    if resp_ids:
        for a in SurveyAnswer.objects.filter(response_id__in=resp_ids).iterator():
            ans_by_q[a.question_id].append(a)

    question_stats = []

    for q in questions:
        rows = ans_by_q.get(q.id, [])
        opt_qs = q.options.all().order_by('order', 'id')
        opt_labels = [o.label for o in opt_qs]
        correct_idx = {i for i, o in enumerate(opt_qs) if getattr(o, "is_correct", False)}

        q_stats = {
            "qid": q.id,
            "title": q.title,
            "type": q.qtype,
            "chart": None,   # None | "bar"
            "labels": [],
            "data": [],
            "extra": {},     # notas, promedios, etc.
        }

        # ---- Tipos de opción única / escala semántica ----
        if q.qtype in ("single", "assessment", "frecuency"):
            if not opt_labels and q.qtype == "assessment":
                opt_labels = ["Muy positivo", "Positivo", "Neutral", "Negativo", "Muy Negativo"]
            if not opt_labels and q.qtype == "frecuency":
                opt_labels = ["Siempre", "Casi siempre", "Algunas veces", "Casi nunca", "Nunca"]

            c = Counter()
            correct_hits = 0
            for a in rows:
                idx = a.value_choice
                if idx is None:
                    continue
                c[idx] += 1
                if correct_idx and idx in correct_idx:
                    correct_hits += 1

            counts = [c.get(i, 0) for i in range(len(opt_labels))]
            q_stats.update({"chart": "bar", "labels": opt_labels, "data": counts})
            if correct_idx:
                total = sum(counts) or 1
                q_stats["extra"]["accuracy_pct"] = round(correct_hits * 100 / total, 1)

        # ---- Rating (1..5) ----
        elif q.qtype == "rating":
            dist = Counter()
            for a in rows:
                try:
                    v = int(a.value_int or 0)  # campo correcto para rating
                except Exception:
                    v = 0
                if 1 <= v <= 5:
                    dist[v] += 1

            labels = ["1", "2", "3", "4", "5"]
            data = [dist.get(i, 0) for i in range(1, 6)]
            total = sum(data) or 1
            avg = round(sum(i * dist.get(i, 0) for i in range(1, 6)) / total, 2)

            q_stats.update({"chart": "bar", "labels": labels, "data": data})
            q_stats["extra"]["avg"] = avg

        # ---- Numéricos: integer / decimal ----
        elif q.qtype in ("integer", "decimal"):
            vals = []
            for a in rows:
                v = a.value_decimal if q.qtype == "decimal" else a.value_int  # nombres reales
                if v is not None:
                    try:
                        vals.append(float(v))
                    except Exception:
                        pass

            if not vals:
                q_stats["extra"]["note"] = "Sin datos numéricos."
            else:
                vmin, vmax = min(vals), max(vals)
                q_stats["extra"]["min"] = round(vmin, 2)
                q_stats["extra"]["max"] = round(vmax, 2)
                q_stats["extra"]["avg"] = round(sum(vals) / len(vals), 2)

                if vmin == vmax:
                    q_stats["chart"] = "bar"
                    q_stats["labels"] = [_fmt_num(vmin)]
                    q_stats["data"] = [len(vals)]
                else:
                    # ENTEROS: conteo por valor si el rango es pequeño
                    if (q.qtype == "integer"
                        and float(vmin).is_integer() and float(vmax).is_integer()
                        and (vmax - vmin) <= 20):
                        start = int(vmin)
                        end   = int(vmax)
                        labels = [str(i) for i in range(start, end + 1)]
                        counts = [0] * len(labels)
                        for v in vals:
                            i = int(round(v))
                            if start <= i <= end:
                                counts[i - start] += 1
                        q_stats.update({"chart": "bar", "labels": labels, "data": counts})
                    else:
                        # DECIMALES o rango grande -> bins con paso “lindo”
                        n = len(vals)
                        target_bins = max(4, min(12, int(math.sqrt(n)) + 1))
                        raw_step = (vmax - vmin) / target_bins
                        step = _nice_step(raw_step)

                        start = math.floor(vmin / step) * step
                        end   = math.ceil(vmax / step) * step
                        bins  = max(1, int(round((end - start) / step)))

                        labels = [f"{_fmt_num(start + i*step)}–{_fmt_num(start + (i+1)*step)}"
                                  for i in range(bins)]
                        counts = [0] * bins
                        for v in vals:
                            idx = int((v - start) // step)
                            if idx < 0: idx = 0
                            if idx >= bins: idx = bins - 1
                            counts[idx] += 1

                        q_stats.update({"chart": "bar", "labels": labels, "data": counts})

        # ---- Multiple (selección múltiple) ----
        elif q.qtype == "multiple":
            cnt = Counter()
            for a in rows:
                snap = a.snapshot or {}
                labels = snap.get("selected_labels")
                if labels:
                    for lbl in labels:
                        cnt[lbl] += 1
                else:
                    indices = snap.get("selected_indices") or []
                    for i, lbl in ((i, opt_labels[i]) for i in indices if 0 <= i < len(opt_labels)):
                        cnt[lbl] += 1

            if cnt:
                items = sorted(cnt.items(), key=lambda x: (-x[1], x[0]))
                labels, data = zip(*items)
                q_stats.update({"chart": "bar", "labels": list(labels), "data": list(data)})
            else:
                q_stats["extra"]["note"] = "Sin datos o no se están guardando las selecciones."

        # ---- Texto libre ----
        elif q.qtype == "text":
            top = Counter([
                (a.value_text or "").strip()
                for a in rows
                if (a.value_text or "").strip()
            ]).most_common(10)
            if top:
                q_stats["extra"]["top_text"] = top  # lista de [texto, veces]
            else:
                q_stats["extra"]["note"] = "Sin respuestas abiertas."

        else:
            q_stats["extra"]["note"] = "Tipo no graficado aún."

        question_stats.append(q_stats)

    qs_json = json.dumps(question_stats, ensure_ascii=False)

    context = {
        "survey": survey,
        "responses_count": responses_count,
        "expected": expected,
        "progress": progress,
        "question_stats_json": qs_json,
        "question_stats": question_stats,
        "latest_responses": (SurveyResponse.objects
                             .filter(survey=survey, status='submitted')
                             .order_by('-submitted_at')[:5]),
    }
    return render(request, "surveys/admin/survey_detail.html", context)
