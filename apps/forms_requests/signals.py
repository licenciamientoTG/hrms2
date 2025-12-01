# apps/forms_requests/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.urls import reverse, NoReverseMatch
from django.contrib.contenttypes.models import ContentType

from .models import SolicitudAutorizacion, ConstanciaGuarderia
from apps.notifications.utils import notify


def _url_usuario_default():
    # Ajusta si tu named URL es otra
    try:
        return reverse("forms_requests:user_forms")
    except Exception:
        return "/forms_requests/solicitud/usuario"

def _url_detalle_guarderia(obj: ConstanciaGuarderia):
    try:
        return reverse("forms_requests:guarderia_detalle", args=[obj.id])
    except NoReverseMatch:
        return _url_usuario_default()


def _notificar_decision_final(solicitud):
    """
    Envía UNA notificación cuando la decisión final es 'aprobado' o 'rechazado'.
    Evita duplicados con dedupe_key.
    """
    if not isinstance(solicitud, ConstanciaGuarderia):
        return

    ct = ContentType.objects.get_for_model(ConstanciaGuarderia)
    qs = (SolicitudAutorizacion.objects
          .filter(content_type=ct, object_id=solicitud.id)
          .order_by('-fecha_revision', '-id'))

    if not qs.exists():
        return

    last = qs.first()
    estado = last.estado  # 'aprobado' | 'rechazado' | 'pendiente'

    if estado not in ("aprobado", "rechazado"):
        return

    fecha = (
        timezone.localtime(solicitud.fecha_solicitud).strftime("%d/%m/%Y %H:%M")
        if solicitud.fecha_solicitud else ""
    )
    url = _url_detalle_guarderia(solicitud)

    if estado == "aprobado":
        titulo  = "Tu constancia de guardería está lista"
        cuerpo  = f"La solicitud realizada el {fecha} fue completada."
        dedupe  = f"constancia-{solicitud.id}-aprobada"
    else:
        titulo  = "Tu solicitud de guardería fue rechazada"
        cuerpo  = (last.comentario or f"La solicitud realizada el {fecha} fue rechazada.")
        dedupe  = f"constancia-{solicitud.id}-rechazada"

    notify(
        user=solicitud.empleado,
        title=titulo,
        body=cuerpo,
        url=url,
        dedupe_key=dedupe,
    )


@receiver(post_save, sender=SolicitudAutorizacion)
def solicitud_autorizacion_saved(sender, instance, **kwargs):
    _notificar_decision_final(instance.solicitud)


@receiver(post_save, sender=ConstanciaGuarderia)
def constancia_guarderia_saved(sender, instance, created, **kwargs):
    # Por si suben el PDF antes/después, revisa si ya hay decisión final
    _notificar_decision_final(instance)
