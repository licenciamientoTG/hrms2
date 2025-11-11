from django.db import transaction
from django.utils import timezone
from .emails import send_recognition_email

def publish_recognition_if_due(recognition):
    """
    Si publish_at es None o ya pasó:
      - fija published_at si aún no está
      - pone status='published'
      - envía correo una sola vez si notify_email y emailed_at is None
    Devuelve True si se publicó en esta llamada.
    """
    now = timezone.now()
    if recognition.publish_at and recognition.publish_at > now:
        return False

    with transaction.atomic():
        r = type(recognition).objects.select_for_update().get(pk=recognition.pk)

        just_published = False
        if r.published_at is None:
            r.published_at = now
            r.status = "published"
            r.save(update_fields=["published_at", "status"])
            just_published = True

        if getattr(r, "notify_email", False) and getattr(r, "emailed_at", None) is None:
            channels = r.email_channels or ["corpo"]
            if send_recognition_email(r, email_channels=channels):
                r.emailed_at = timezone.now()
                r.save(update_fields=["emailed_at"])

    return just_published
