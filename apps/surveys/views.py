import json
from django.db.models import Q
from apps.employee.models import Employee, JobPosition
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST, require_http_methods, require_GET
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.template.loader import render_to_string
from django.db.models import Max
from .models import Survey, SurveySection, SurveyQuestion, SurveyAudience, SurveyOption
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

    start_idx = (page_obj.number - 1) * paginator.per_page
    for i, s in enumerate(page_obj.object_list, start=1):
        s.responses_count = 0
        s.progress = 0.0
        s.position = start_idx + i

    ctx = {"page_obj": page_obj, "is_paginated": page_obj.has_other_pages(), "q": q, "sort": sort}
    return render(request, "surveys/admin/survey_dashboard_admin.html", ctx)

@login_required
def survey_dashboard_user(request):
    user = request.user

    # Encuestas activas visibles para el usuario:
    # - sin audiencia (por si alguna quedó sin crear)
    # - o audiencia en modo "all"
    # - o usuario en la M2M de audiencia.users
    visible_qs = (
        Survey.objects.filter(is_active=True)
        .filter(
            Q(audience__isnull=True) |
            Q(audience__mode=SurveyAudience.MODE_ALL) |           # 'all'
            Q(audience__mode__iexact='all') |                     # robusto por si hay mayúsculas
            Q(audience__users=user)
        )
        .select_related('audience')
        .order_by('title')
        .distinct()
    )

    available = [{
        "id": s.id,
        "title": s.title,
        "take_url": reverse("survey_view", args=[s.id]),
        "status": "available",
    } for s in visible_qs]

    context = {
        "available": available,
        "completed": [],  # cuando tengamos submissions, lo llenamos
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

@login_required
@user_passes_test(lambda u: u.is_superuser)
def survey_export_excel(request, pk: int):
    s = get_object_or_404(Survey, pk=pk)

    # Si no hay openpyxl instalado, devolvemos CSV como salida segura
    if Workbook is None:
        return survey_export_csv(request, pk)

    import io
    wb = Workbook()
    ws = wb.active
    ws.title = "Encuesta"

    ws.append(["Título", s.title])
    ws.append(["Activa", "Sí" if s.is_active else "No"])
    ws.append(["Anónima", "Sí" if s.is_anonymous else "No"])
    ws.append(["Creada en", s.created_at.strftime("%Y-%m-%d %H:%M")])
    ws.append(["Creador", s.creator.get_full_name() or s.creator.username])
    ws.append([])
    ws.append(["Sección", "Orden", "Pregunta", "Tipo", "Obligatoria", "Opción", "Correcta", "Salto a sección"])

    for sec in s.sections.all().order_by("order"):
        if sec.questions.exists():
            for q in sec.questions.all().order_by("order"):
                if q.options.exists():
                    for opt in q.options.all().order_by("order"):
                        ws.append([
                            sec.title or f"Sección {sec.order}",
                            sec.order,
                            q.title,
                            q.qtype,
                            "Sí" if q.required else "No",
                            opt.label,
                            "Sí" if opt.is_correct else "No",
                            (opt.branch_to_section.title if opt.branch_to_section else ""),
                        ])
                else:
                    ws.append([sec.title or f"Sección {sec.order}", sec.order, q.title, q.qtype,
                               "Sí" if q.required else "No", "", "", ""])
        else:
            ws.append([sec.title or f"Sección {sec.order}", sec.order, "", "", "", "", "", ""])

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    resp = HttpResponse(
        out.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    resp["Content-Disposition"] = f'attachment; filename="encuesta_{s.pk}.xlsx"'
    return resp

@login_required
@user_passes_test(lambda u: u.is_superuser)
def survey_export_csv(request, pk: int):
    s = get_object_or_404(Survey, pk=pk)
    import csv
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="encuesta_{s.pk}.csv"'
    w = csv.writer(resp)

    w.writerow(["Título", s.title])
    w.writerow(["Activa", "Sí" if s.is_active else "No"])
    w.writerow(["Anónima", "Sí" if s.is_anonymous else "No"])
    w.writerow(["Creada en", s.created_at.strftime("%Y-%m-%d %H:%M")])
    w.writerow(["Creador", s.creator.get_full_name() or s.creator.username])
    w.writerow([])

    w.writerow(["Sección", "Orden", "Pregunta", "Tipo", "Obligatoria", "Opción", "Correcta", "Salto a sección"])
    for sec in s.sections.all().order_by("order"):
        if sec.questions.exists():
            for q in sec.questions.all().order_by("order"):
                if q.options.exists():
                    for opt in q.options.all().order_by("order"):
                        w.writerow([
                            sec.title or f"Sección {sec.order}",
                            sec.order,
                            q.title,
                            q.qtype,
                            "Sí" if q.required else "No",
                            opt.label,
                            "Sí" if opt.is_correct else "No",
                            (opt.branch_to_section.title if opt.branch_to_section else ""),
                        ])
                else:
                    w.writerow([sec.title or f"Sección {sec.order}", sec.order, q.title, q.qtype,
                                "Sí" if q.required else "No", "", "", ""])
        else:
            w.writerow([sec.title or f"Sección {sec.order}", sec.order, "", "", "", "", "", ""])
    return resp

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
def surveys_panel(request):
    user = request.user

    # Encuestas activas visibles para el usuario:
    # - audiencia modo "Todos"
    # - o usuario incluido explícitamente en audience.users (M2M)
    visible = (
        Survey.objects.filter(is_active=True)
        .filter(Q(audience__mode='all') | Q(audience__users=user))
        .select_related('audience')
        .order_by('title')
        .distinct()
    )

    available = [{
        "id": s.id,
        "title": s.title,
        "status": "available",
        "take_url": reverse("surveys:take", args=[s.id]),
    } for s in visible]

    context = {
        "available": available,
        "completed": [],  # aún no distinguimos completadas (eso será con submissions)
    }
    return render(request, "surveys/panel.html", context)


@login_required
def survey_view(request, survey_id: int):
    survey = get_object_or_404(
        Survey.objects.select_related("audience"),
        pk=survey_id,
        is_active=True
    )

    # Acceso por audiencia: permite sin audiencia, o modo 'all', o si el usuario está incluido
    aud = getattr(survey, "audience", None)
    allowed = (
        aud is None
        or getattr(aud, "mode", "").lower() == "all"
        or aud.users.filter(pk=request.user.pk).exists()
    )
    if not allowed:
        return render(request, "surveys/not_allowed.html", {"survey": survey}, status=403)

    sections = _sections_for_template(survey)

    ctx = {
        "survey": {"id": survey.id, "title": survey.title},
        "sections": sections,
        "post_url": request.path,  
        "back_url": reverse("survey_dashboard_user"),
    }
    return render(request, "surveys/user/survey_view.html", ctx)


def _sections_for_template(survey) -> list[dict]:
    # Carga eficiente de relaciones
    q_qs = (SurveyQuestion.objects
            .order_by("order", "pk")
            .prefetch_related(
                Prefetch(
                    "options",
                    queryset=SurveyOption.objects
                        .select_related("branch_to_section")
                        .order_by("order", "pk")
                )
            ))

    sections_qs = (survey.sections
                   .select_related("go_to_section")
                   .prefetch_related(Prefetch("questions", queryset=q_qs))
                   .order_by("order", "pk"))

    out = []
    for s in sections_qs:
        sec = {
            "id":     f"s{s.pk}",
            "title":  s.title,
            "order":  s.order,
            "go_to":  ("submit" if s.submit_on_finish
                       else (f"s{s.go_to_section_id}" if s.go_to_section_id else None)),
            "questions": []
        }

        for q in s.questions.all():
            qd = {
                "id":       f"q{q.pk}",
                "title":    q.title,
                "type":     q.qtype,           # single | multiple | text | integer | decimal | rating | none
                "required": bool(q.required),
                "options":  [],
                "branch":   None,
            }

            if q.qtype in {"single", "multiple", "dropdown"}:
                opts = list(q.options.all())
                qd["options"] = [{"label": o.label} for o in opts]

                # Branching por opción (solo SINGLE)
                if q.qtype == "single" and q.branch_enabled:
                    by = {}
                    for idx, o in enumerate(opts):
                        if o.branch_to_section_id:
                            by[idx] = f"s{o.branch_to_section_id}"
                    if by:
                        qd["branch"] = {"enabled": True, "byOption": by}

            sec["questions"].append(qd)

        out.append(sec)

    return out
