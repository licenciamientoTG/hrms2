from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.text import Truncator
import logging

from apps.courses.models import EnrolledCourse
from apps.notifications.utils import notify

def _resolve_user_from_enrollment(enrollment):
    # 1) si tu modelo tiene campo directo user
    if hasattr(enrollment, "user") and enrollment.user:
        return enrollment.user
    # 2) si tiene employee.user
    if hasattr(enrollment, "employee") and enrollment.employee and hasattr(enrollment.employee, "user"):
        return enrollment.employee.user
    # 3) intentos comunes
    for attr in ("assigned_to", "owner", "participant", "student"):
        obj = getattr(enrollment, attr, None)
        if obj and hasattr(obj, "user") and obj.user:
            return obj.user
    return None

log = logging.getLogger(__name__)

@receiver(post_save, sender=EnrolledCourse)
def notify_on_enrollment(sender, instance, created, **kwargs):
    """
    Cuando se crea una asignación de curso (EnrolledCourse), notifica al usuario.
    """
    if not created:
        return

    user = instance.user
    course = instance.course
    if not user or not course:
        return

    title = f"Nuevo curso asignado: {Truncator(course.title).chars(80)}"

    # Tu URL real para ver contenido es: name='view_course_content', path 'my-courses/<int:course_id>/'
    try:
        url = reverse("view_course_content", args=[course.id])
    except Exception:
        url = ""  # si fallara el reverse por algún motivo

    body = "Ya puedes acceder al curso y comenzar cuando gustes."
    # dedupe_key evita duplicados triviales si se reintenta
    notify(user, title, body=body, url=url, dedupe_key=f"enrollment:{instance.pk}")
