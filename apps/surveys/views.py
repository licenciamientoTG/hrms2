# surveys/views.py
import json
from django.db.models import Q
from apps.employee.models import Employee, JobPosition
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST, require_http_methods, require_GET
from django.http import JsonResponse, HttpResponseBadRequest
from django.template.loader import render_to_string
from django.db.models import Max
from .models import Survey, SurveySection, SurveyQuestion
from uuid import uuid4
from departments.models import Department
from apps.location.models import Location

@login_required
def survey_dashboard(request):
    return redirect('survey_dashboard_admin') if request.user.is_superuser else redirect('survey_dashboard_user')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def survey_dashboard_admin(request):
    return render(request, 'surveys/admin/survey_dashboard_admin.html')

@login_required
def survey_dashboard_user(request):
    return render(request, 'surveys/user/survey_dashboard_user.html')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def survey_new(request):
    draft_id = uuid4().hex  # id efímero para el localStorage / URL
    return render(request, 'surveys/admin/survey_new.html', {
        "draft_id": draft_id,
        # no pasamos survey ni sections
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