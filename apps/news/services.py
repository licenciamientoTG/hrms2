# apps/news/services.py
from django.db import transaction
from django.utils import timezone
from .emails import send_news_email

def publish_news_if_due(news, *, email_channels=None):
    now = timezone.now()
    due = (news.publish_at is None) or (news.publish_at <= now)
    if not due:
        return False

    with transaction.atomic():
        n = type(news).objects.select_for_update().get(pk=news.pk)

        if n.published_at is None:
            n.published_at = now
            n.save(update_fields=["published_at"])

        if getattr(n, "notify_email", False) and getattr(n, "emailed_at", None) is None:
            # Enviar email a los canales solicitados
            ok = send_news_email(n, email_channels=email_channels)
            if ok:
                n.emailed_at = timezone.now()
                n.save(update_fields=["emailed_at"])

    return True
