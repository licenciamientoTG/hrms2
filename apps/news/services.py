from django.db import transaction
from django.utils import timezone
from .emails import send_news_email

def publish_news_if_due(news):
    """
    Verifica si una noticia programada ya debe publicarse.
    Si es así, asigna published_at y envía el EMAIL si corresponde.
    """
    now = timezone.now()
    
    # Si tiene fecha programada y AÚN NO llega esa hora, no hacemos nada.
    if news.publish_at and news.publish_at > now:
        return False

    with transaction.atomic():
        # Bloqueamos el registro para evitar conflictos si hay concurrencia
        n = type(news).objects.select_for_update().get(pk=news.pk)

        just_published = False
        
        # 1. LÓGICA DE PUBLICACIÓN (Marcar como publicado en BD)
        if n.published_at is None:
            n.published_at = now
            n.save(update_fields=["published_at"])
            just_published = True

        # 2. LÓGICA DE EMAIL (Se envía inmediatamente)
        if getattr(n, "notify_email", False) and getattr(n, "emailed_at", None) is None:
            channels = n.email_channels or ["corpo"]
            if send_news_email(n, email_channels=channels):
                n.emailed_at = timezone.now()
                n.save(update_fields=["emailed_at"])
                
    return just_published