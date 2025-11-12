from django.db import transaction
from django.utils import timezone
from .emails import send_news_email

def publish_news_if_due(news):
    now = timezone.now()
    if news.publish_at and news.publish_at > now:
        return False

    with transaction.atomic():
        n = type(news).objects.select_for_update().get(pk=news.pk)

        just_published = False
        if n.published_at is None:
            n.published_at = now
            n.save(update_fields=["published_at"])
            just_published = True

        if getattr(n, "notify_email", False) and getattr(n, "emailed_at", None) is None:
            channels = n.email_channels or ["corpo"]   # 👈 igual que Reconocimientos
            if send_news_email(n, email_channels=channels):
                n.emailed_at = timezone.now()
                n.save(update_fields=["emailed_at"])

    return just_published
