from django.db import transaction
from django.utils import timezone
from .emails import send_recognition_email
from apps.notifications.models import Notification
import logging

logger = logging.getLogger(__name__)

def publish_recognition_if_due(recognition):
    """
    Si publish_at es None o ya pasó:
      - Publica el reconocimiento.
      - Envía correo (fuera de la transacción para que un fallo SMTP no revierta la publicación).
      - CREA NOTIFICACIONES INTERNAS INMEDIATAMENTE.

    Retorna una tupla (published_now, email_sent):
      published_now: True si se acaba de publicar
      email_sent:    True = correo enviado OK, False = falló, None = no se intentó
    """
    now = timezone.now()

    # Si tiene fecha programada futura, no hacemos nada aún
    if recognition.publish_at and recognition.publish_at > now:
        return False, None

    email_needed = False
    email_channels = None
    just_published = False

    with transaction.atomic():
        # Bloqueo para concurrencia
        r = type(recognition).objects.select_for_update().get(pk=recognition.pk)

        # --- 1. PUBLICAR ---
        if r.published_at is None:
            r.published_at = now
            r.status = "published"
            r.save(update_fields=["published_at", "status"])
            just_published = True

        # --- 2. MARCAR QUE SE NECESITA CORREO (el envío va fuera del atomic) ---
        if getattr(r, "notify_email", False) and getattr(r, "emailed_at", None) is None:
            email_needed = True
            email_channels = r.email_channels or ["corpo"]

        # --- 3. CREAR NOTIFICACIONES INTERNAS (INMEDIATO) ---
        if just_published and getattr(r, "notify_push", True):
            from django.contrib.auth.models import User
            from django.db.models import Q

            # Determinar la audiencia
            if r.is_public:
                audience_users = User.objects.filter(is_active=True)
            else:
                # Miembros de los grupos seleccionados O destinatarios directos
                audience_users = User.objects.filter(
                    Q(groups__in=r.target_groups.all()) | Q(recognitions_received=r),
                    is_active=True
                ).distinct()

            # IDs de los que son mencionados para cambiar el texto
            recipient_ids = set(r.recipients.values_list('id', flat=True))

            notifs_to_create = []
            rec_url = f"/recognitions/?highlight={r.id}#recognition-{r.id}"

            for user in audience_users:
                is_protagonist = user.id in recipient_ids

                if is_protagonist:
                    title = "¡Te han mencionado!"
                    body = f"Has sido mencionado en un comunicado de: {r.category.title}"
                else:
                    title = "Nuevo Comunicado"
                    body = f"Se ha publicado un nuevo comunicado en: {r.category.title}"

                notifs_to_create.append(
                    Notification(
                        user=user,
                        title=title,
                        body=body,
                        url=rec_url,
                        module="comunicados"
                    )
                )

            if notifs_to_create:
                Notification.objects.bulk_create(notifs_to_create)

    # --- 4. ENVIAR CORREO FUERA DE LA TRANSACCIÓN ---
    # Si el SMTP falla, el comunicado ya quedó publicado y no se revierte.
    email_sent = None
    if just_published and email_needed:
        try:
            if send_recognition_email(r, email_channels=email_channels):
                type(recognition).objects.filter(pk=r.pk).update(emailed_at=timezone.now())
                email_sent = True
        except Exception as exc:
            logger.error(
                "Error enviando correo para comunicado id=%s: %s",
                r.pk, exc, exc_info=True
            )
            email_sent = False

    return just_published, email_sent
