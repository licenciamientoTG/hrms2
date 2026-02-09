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

    return just_published