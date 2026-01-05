from django.db import transaction
from django.utils import timezone
from .emails import send_recognition_email
# 1. Importar Notification
from apps.notifications.models import Notification 

def publish_recognition_if_due(recognition):
    """
    Si publish_at es None o ya pasó:
      - Publica el reconocimiento.
      - Envía correo.
      - CREA NOTIFICACIONES INTERNAS INMEDIATAMENTE.
    """
    now = timezone.now()
    
    # Si tiene fecha programada futura, no hacemos nada aún
    if recognition.publish_at and recognition.publish_at > now:
        return False

    with transaction.atomic():
        # Bloqueo para concurrencia
        r = type(recognition).objects.select_for_update().get(pk=recognition.pk)

        just_published = False
        
        # --- 1. PUBLICAR ---
        if r.published_at is None:
            r.published_at = now
            r.status = "published"
            r.save(update_fields=["published_at", "status"])
            just_published = True

        # --- 2. ENVIAR CORREO ---
        if getattr(r, "notify_email", False) and getattr(r, "emailed_at", None) is None:
            channels = r.email_channels or ["corpo"]
            if send_recognition_email(r, email_channels=channels):
                r.emailed_at = timezone.now()
                r.save(update_fields=["emailed_at"])
        
        # --- 3. CREAR NOTIFICACIONES INTERNAS (INMEDIATO) ---
        # Al hacerlo aquí, el usuario activo verá la notificación en su próxima recarga.
        if just_published and getattr(r, "notify_push", True):
            # Obtenemos los destinatarios
            recipients = r.recipients.filter(is_active=True)
            
            notifs_to_create = []
            for user in recipients:
                # Url para ver el reconocimiento
                rec_url = f"/recognitions/?highlight={r.id}#recognition-{r.id}"
                
                notifs_to_create.append(
                    Notification(
                        user=user,
                        title="¡Te han mencionado!",
                        body=f"Has sido mencionado en un comunicado de: {r.category.title}",
                        url=rec_url,
                        module="comunicados"
                    )
                )
            
            # Insertar en bloque (Eficiente para 30 usuarios)
            if notifs_to_create:
                Notification.objects.bulk_create(notifs_to_create)

    return just_published