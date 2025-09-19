# surveys/services.py
from __future__ import annotations
from typing import Dict, Any, Iterable

from django.contrib.auth import get_user_model
from django.db import transaction

from .models import (
    Survey, SurveySection, SurveyQuestion, SurveyOption, SurveyAudience
)
from apps.employee.models import JobPosition  # para expandir positionsTitles → IDs

User = get_user_model()


# ---------- helpers ----------
def _b(x) -> bool:
    if isinstance(x, bool): return x
    if isinstance(x, (int, float)): return bool(x)
    if isinstance(x, str): return x.strip().lower() in {'1','true','t','yes','y','on'}
    return False

def _i(v, default=1) -> int:
    try: return int(v)
    except Exception: return default

def _s(v, default="") -> str:
    if v is None: return default
    v = str(v).strip()
    return v or default

def _i_list(seq: Iterable) -> list[int]:
    out = []
    for v in (seq or []):
        try: out.append(int(v))
        except Exception: pass
    return out


@transaction.atomic
def persist_builder_state(survey: Survey, state: Dict[str, Any]) -> None:
    """
    Persiste secciones/preguntas/opciones/saltos y el estado activo de la encuesta.
    Espera el shape del localStorage (state.sections, state.active, etc).
    """
    state = state or {}

    # Reemplazo total del contenido
    SurveyOption.objects.filter(question__section__survey=survey).delete()
    SurveyQuestion.objects.filter(section__survey=survey).delete()
    SurveySection.objects.filter(survey=survey).delete()

    sections_in = state.get('sections') or []

    # 1) crear secciones (sin enlaces)
    sec_map: dict[str, SurveySection] = {}
    for s in sorted(sections_in, key=lambda x: _i(x.get('order'), 0)):
        local_id = _s(s.get('id')) or f"_tmp_{s.get('order') or ''}"
        sec = SurveySection.objects.create(
            survey=survey,
            title=_s(s.get('title')),
            order=_i(s.get('order'), 1),
        )
        sec_map[local_id] = sec

    # 2) go_to / submit_on_finish
    for s in sections_in:
        local_id = _s(s.get('id'))
        inst = sec_map.get(local_id)
        if not inst:
            continue
        dest = s.get('go_to')
        if dest in (None, ''):
            inst.go_to_section = None
            inst.submit_on_finish = False
        elif dest == 'submit':
            inst.go_to_section = None
            inst.submit_on_finish = True
        else:
            inst.go_to_section = sec_map.get(_s(dest))
            inst.submit_on_finish = False
        inst.save(update_fields=['go_to_section', 'submit_on_finish'])

    # 3) preguntas + opciones (+ branching por opción)
    for s in sections_in:
        sec = sec_map.get(_s(s.get('id')))
        if not sec:
            continue
        for q in sorted((s.get('questions') or []), key=lambda x: _i(x.get('order'), 0)):
            qtype = _s(q.get('type') or 'single')
            branch_enabled = bool((q.get('branch') or {}).get('enabled')) if qtype == 'single' else False

            question = SurveyQuestion.objects.create(
                section=sec,
                title=_s(q.get('title') or 'Pregunta'),
                qtype=qtype,
                required=_b(q.get('required')),
                order=_i(q.get('order'), 1),
                branch_enabled=branch_enabled,
            )

            # opciones para SINGLE/MULTIPLE
            if qtype in ('single', 'multiple'):
                opts = q.get('options') or []
                by_opt = (q.get('branch') or {}).get('byOption') or {}
                for idx, opt in enumerate(opts):
                    label = _s((opt or {}).get('label') if isinstance(opt, dict) else opt) or f'Opción {idx+1}'
                    is_correct = _b((opt or {}).get('correct')) if isinstance(opt, dict) else False
                    o = SurveyOption.objects.create(
                        question=question,
                        label=label,
                        order=idx + 1,
                        is_correct=is_correct,
                    )

                    # branching por opción (SINGLE)
                    if qtype == 'single' and branch_enabled:
                        # soporta claves 0 ó "0"
                        dest_local = by_opt.get(idx)
                        if dest_local is None:
                            dest_local = by_opt.get(str(idx))
                        if dest_local and dest_local != 'submit':
                            o.branch_to_section = sec_map.get(_s(dest_local))
                            o.save(update_fields=['branch_to_section'])

    # 4) activo / inactivo (pill del builder)
    if 'active' in state:
        survey.is_active = _b(state.get('active'))
        survey.save(update_fields=['is_active'])


def persist_settings(survey: Survey, settings_dict: Dict[str, Any]) -> None:
    """ Guarda autoMessage / isAnonymous (localStorage → Survey). """
    settings_dict = settings_dict or {}
    survey.auto_message = _s(settings_dict.get('autoMessage'))
    survey.is_anonymous = _b(settings_dict.get('isAnonymous'))
    survey.save(update_fields=['auto_message', 'is_anonymous'])


@transaction.atomic
def persist_audience(survey: Survey, audience_dict: Dict[str, Any]) -> None:
    """
    Guarda modo, filtros y usuarios explícitos. Si vienen titles en
    filters.positionsTitles y no hay positions, se expanden a IDs.
    """
    audience_dict = audience_dict or {}
    aud, _ = SurveyAudience.objects.get_or_create(survey=survey)

    # modo
    mode = audience_dict.get('mode')
    if mode not in ('all', 'segmented'):
        mode = 'all' if _b(audience_dict.get('allUsers')) else 'segmented'
    aud.mode = 'segmented' if mode == 'segmented' else 'all'

    f = (audience_dict.get('filters') or {})
    deps = _i_list(f.get('departments'))
    locs = _i_list(f.get('locations'))
    poss = _i_list(f.get('positions'))

    # expansión opcional de positionsTitles → IDs (si no enviaron positions)
    if not poss:
        titles = [t for t in (f.get('positionsTitles') or []) if _s(t)]
        if titles:
            ids = JobPosition.objects.filter(title__iexact=titles[0])
            for t in titles[1:]:
                ids = ids.union(JobPosition.objects.filter(title__iexact=t))
            poss = list(ids.values_list('id', flat=True))

    aud.filters = {'departments': deps, 'positions': poss, 'locations': locs}
    aud.save(update_fields=['mode', 'filters'])

    # usuarios explícitos
    user_ids = _i_list(audience_dict.get('users'))
    users = User.objects.filter(pk__in=user_ids)
    aud.users.set(users)
