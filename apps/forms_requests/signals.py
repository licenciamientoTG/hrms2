from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.urls import reverse, NoReverseMatch

from .models import SolicitudAutorizacion, ConstanciaGuarderia
from apps.notifications.utils import notify


def _url_constancia(obj: ConstanciaGuarderia) -> str:
    try:
        return reverse("forms_requests:constancia_pdf", args=[obj.id])
    except NoReverseMatch:
        pass
    try:
        return reverse("forms_requests:detalle_constancia", args=[obj.id])
    except NoReverseMatch:
        pass
    return "/forms_requests/solicitudes/"


def _notificar_completada(obj: ConstanciaGuarderia):
    """Crea la notificación al empleado si la constancia está 'completada'."""
    if obj.estado != "completada":
        return
    titulo = "Tu constancia de guardería está lista"
    fecha = timezone.localtime(obj.fecha_solicitud).strftime("%d/%m/%Y %H:%M")
    cuerpo = f"La solicitud realizada el {fecha} fue completada."
    url = _url_constancia(obj)
    notify(
        obj.empleado,
        titulo,
        cuerpo,
        url,
        dedupe_key=f"constancia-{obj.id}-completada",
    )


# 1) Cuando se guarda una autorización, revisa si la constancia quedó completada
@receiver(post_save, sender=SolicitudAutorizacion)
def solicitud_autorizacion_saved(sender, instance, **kwargs):
    solicitud = instance.solicitud  # GenericForeignKey
    if isinstance(solicitud, ConstanciaGuarderia):
        _notificar_completada(solicitud)