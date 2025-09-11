# surveys/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST, require_http_methods, require_GET
from django.http import JsonResponse, HttpResponseBadRequest
from django.template.loader import render_to_string
from django.db.models import Max
from .models import Survey, SurveySection, SurveyQuestion
from uuid import uuid4


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
