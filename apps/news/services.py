# apps/news/services.py
from django.db import transaction
from django.utils import timezone
from .emails import send_news_email

def publish_news_if_due(news):
    """
    Si publish_at es None o ya pasó:
      - fija published_at (si aún no está)
      - envía correo UNA sola vez si notify_email=True
    """
    now = timezone.now()
    due = (news.publish_at is None) or (news.publish_at <= now)
    if not due:
        return False

    with transaction.atomic():
        n = type(news).objects.select_for_update().get(pk=news.pk)

        if n.published_at is None:
            n.published_at = now
            n.save(update_fields=["published_at"])

        if getattr(n, "notify_email", False) and n.emailed_at is None:
            send_news_email(n)

    return True
