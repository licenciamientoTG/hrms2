# apps/notifications/utils.py
from django.apps import apps
import logging

log = logging.getLogger(__name__)

def notify(user, title, body="", url="", dedupe_key=None):
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
        )
    except Exception as e:
        log.exception("Error creando notificación: %s", e)
        return None
