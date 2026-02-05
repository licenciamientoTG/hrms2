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
    Crea notificaciones 'Tienes una nueva encuesta' para los usuarios de la audiencia.
    Optimizado con bulk_create para manejar grandes audiencias eficientemente.
    """
    SurveyAudience = apps.get_model("surveys", "SurveyAudience")
    Notification = apps.get_model("notifications", "Notification")
    User = apps.get_model("auth", "User")
    from django.urls import reverse

    try:
        aud = survey.audience
    except SurveyAudience.DoesNotExist:
        aud = None

    user_ids = _audience_user_ids(aud)
    if not user_ids:
        return 0

    url = reverse("survey_view_user", args=[survey.id])

    # Filtrar usuarios que YA tienen una notificación no leída para esta misma encuesta
    existing_uids = set(Notification.objects.filter(
        user_id__in=user_ids, 
        url=url, 
        read_at__isnull=True
    ).values_list("user_id", flat=True))

    to_create_uids = [uid for uid in user_ids if uid not in existing_uids]
    if not to_create_uids:
        return 0

    title = survey.title or "Nueva encuesta"
    body = "Tienes una nueva encuesta para responder."

    # Crear objetos de notificación sin guardarlos todavía
    notifications = [
        Notification(
            user_id=uid,
            title=title,
            body=body,
            url=url,
            module="encuestas"
        )
        for uid in to_create_uids
    ]

    # Insertar todas las notificaciones en una sola consulta (o bloques de 500)
    try:
        created_objs = Notification.objects.bulk_create(notifications, batch_size=500)
        return len(created_objs)
    except Exception as e:
        log.exception("Error en bulk_create de notificaciones: %s", e)
        return 0
