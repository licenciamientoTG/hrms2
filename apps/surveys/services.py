# surveys/services.py
from __future__ import annotations
from typing import Dict, Any

from django.contrib.auth import get_user_model
from django.db import transaction

from .models import (
    Survey, SurveySection, SurveyQuestion, SurveyOption, SurveyAudience
)

User = get_user_model()


@transaction.atomic
def persist_builder_state(survey: Survey, state: Dict[str, Any]) -> None:
    """
    Persiste el draft del builder (sections/questions/options/branching).
    Espera el shape que guardas en localStorage: state['sections']...
    """

    # Limpieza (reemplazo total del contenido del builder)
    SurveyOption.objects.filter(question__section__survey=survey).delete()
    SurveyQuestion.objects.filter(section__survey=survey).delete()
    SurveySection.objects.filter(survey=survey).delete()

    # 1) Crear secciones (primero sin enlaces)
    sec_map = {}  # idLocal -> instancia
    for s in sorted(state.get('sections', []), key=lambda x: x.get('order', 0)):
        sec = SurveySection.objects.create(
            survey=survey,
            title=(s.get('title') or '').strip(),
            order=int(s.get('order') or 1),
        )
        sec_map[str(s.get('id'))] = sec

    # 2) Actualizar go_to / submit_on_finish
    for s in state.get('sections', []):
        inst = sec_map[str(s.get('id'))]
        dest = s.get('go_to')
        if dest in (None, '',):
            inst.go_to_section = None
            inst.submit_on_finish = False
        elif dest == 'submit':
            inst.go_to_section = None
            inst.submit_on_finish = True
        else:
            inst.go_to_section = sec_map.get(str(dest))
            inst.submit_on_finish = False
        inst.save(update_fields=['go_to_section', 'submit_on_finish'])

    # 3) Preguntas y opciones
    for s in state.get('sections', []):
        sec = sec_map[str(s.get('id'))]
        for q in sorted((s.get('questions') or []), key=lambda x: x.get('order', 0)):
            qtype = q.get('type') or 'single'
            question = SurveyQuestion.objects.create(
                section=sec,
                title=(q.get('title') or 'Pregunta').strip(),
                qtype=qtype,
                required=bool(q.get('required')),
                order=int(q.get('order') or 1),
                branch_enabled=bool(q.get('branch', {}).get('enabled')) if qtype == 'single' else False,
            )

            # Opciones para SINGLE/MULTIPLE
            if qtype in ('single', 'multiple'):
                opts = q.get('options') or []
                by_opt = (q.get('branch', {}) or {}).get('byOption', {}) if (qtype == 'single' and question.branch_enabled) else {}

                for idx, opt in enumerate(opts):
                    o = SurveyOption.objects.create(
                        question=question,
                        label=(opt.get('label') or '').strip() or f'Opción {idx+1}',
                        order=idx + 1,
                        is_correct=bool(opt.get('correct')),
                    )
                    # Branch por opción (SINGLE)
                    if qtype == 'single' and question.branch_enabled:
                        dest_local = by_opt.get(idx) if isinstance(by_opt, dict) else by_opt.get(str(idx))
                        if dest_local:
                            o.branch_to_section = sec_map.get(str(dest_local))
                            o.save(update_fields=['branch_to_section'])


def persist_settings(survey: Survey, settings_dict: Dict[str, Any]) -> None:
    """
    Guarda autoMessage / isAnonymous que también tienes en localStorage.
    """
    survey.auto_message = (settings_dict.get('autoMessage') or '').strip()
    survey.is_anonymous = bool(settings_dict.get('isAnonymous'))
    survey.save(update_fields=['auto_message', 'is_anonymous'])


@transaction.atomic
def persist_audience(survey: Survey, audience_dict: Dict[str, Any]) -> None:
    """
    Guarda la audiencia (modo, filtros y usuarios explícitos).
    audience_dict = {
      "mode": "all" | "segmented",
      "users": [ids...],
      "filters": {"departments":[...], "positions":[...], "locations":[...]}
    }
    """
    aud, _ = SurveyAudience.objects.get_or_create(survey=survey)

    aud.mode = 'segmented' if audience_dict.get('mode') == 'segmented' else 'all'
    f = audience_dict.get('filters') or {}
    aud.filters = {
        'departments': f.get('departments') or [],
        'positions':   f.get('positions') or [],
        'locations':   f.get('locations') or [],
    }
    aud.save(update_fields=['mode', 'filters'])

    user_ids = audience_dict.get('users') or []
    users = User.objects.filter(pk__in=user_ids)
    aud.users.set(users)  # reemplaza el conjunto completo
