# apps/notifications/utils.py
from django.apps import apps
import logging
from django.db.models import Q

log = logging.getLogger(__name__)

def notify(user, title, body="", url="", module="", dedupe_key=None):
    Notification = apps.get_model("notifications", "Notification")
    try:
        if dedupe_key:
            # Evita duplicados si hay una igual sin leer
            if Notification.objects.filter(
                user=user,
                title=title,
                url=url,
                read_at__isnull=True
            ).exists():
                return None

        return Notification.objects.create(
            user=user,
            title=title,
            body=body,
            url=url,
            module=module or "",
        )
    except Exception as e:
        log.exception("Error creando notificación: %s", e)
        return None

def _audience_user_ids(aud) -> set[int]:
    """
    Devuelve el set de user_ids que pertenecen a la audiencia dada.
    """
    Employee = apps.get_model("employee", "Employee")
    SurveyAudience = apps.get_model("surveys", "SurveyAudience")

    # Sin audiencia o modo ALL => todos los usuarios activos con empleado activo
    if not aud or getattr(aud, "mode", "").lower() == SurveyAudience.MODE_ALL:
        return set(Employee.objects.filter(
            user__isnull=False, user__is_active=True, is_active=True
        ).values_list("user_id", flat=True))

    # Segmentado (OR entre filtros y usuarios explícitos)
    if aud.mode == "segmented":
        f = aud.filters or {}
        dep_ids = f.get("departments") or []
        pos_ids = f.get("positions") or []
        loc_ids = f.get("locations") or []
        explicit_ids = list(aud.users.values_list("id", flat=True))

        qs = Employee.objects.filter(
            user__isnull=False, user__is_active=True, is_active=True
        )
        cond = Q()
        if explicit_ids: cond |= Q(user_id__in=explicit_ids)
        if dep_ids:      cond |= Q(department_id__in=dep_ids)
        if pos_ids:      cond |= Q(job_position_id__in=pos_ids)
        if loc_ids:      cond |= Q(station_id__in=loc_ids)

        if cond:
            return set(qs.filter(cond).distinct().values_list("user_id", flat=True))
        return set()

    # Otros modos: solo usuarios explícitos
    return set(aud.users.filter(is_active=True).values_list("id", flat=True))


def send_survey_notifications(survey) -> int:
    """
    Crea notificaciones 'Tienes una nueva encuesta' para los usuarios de la audiencia,
    usando notify(). Evita duplicados por (user, title, url) no leídos.
    Devuelve cuántas notificaciones se intentaron crear.
    """
    SurveyAudience = apps.get_model("surveys", "SurveyAudience")

    try:
        aud = survey.audience
    except SurveyAudience.DoesNotExist:
        aud = None

    user_ids = _audience_user_ids(aud)
    if not user_ids:
        return 0

    # URL a donde llevará la notificación
    from django.urls import reverse
    url = reverse("survey_view_user", args=[survey.id])

    Notification = apps.get_model("notifications", "Notification")
    # Excluir los que YA tienen una noti no leída con misma URL
    existing = set(Notification.objects.filter(
        user_id__in=user_ids, url=url, read_at__isnull=True
    ).values_list("user_id", flat=True))

    to_create = [uid for uid in user_ids if uid not in existing]
    if not to_create:
        return 0

    title = survey.title or "Nueva encuesta"
    body = "Tienes una nueva encuesta para responder."

    # Usa notify() para cada usuario (respeta dedupe)
    created = 0
    for uid in to_create:
        user = apps.get_model("auth", "User").objects.filter(id=uid).first()
        if user:
            if notify(user, title, body=body, url=url, module="encuestas", dedupe_key=True):
                created += 1
    return created
