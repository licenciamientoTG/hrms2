from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import News
from apps.notifications.models import Notification

@receiver(user_logged_in)
def generate_missed_news_notifications(sender, user, request, **kwargs):
    """
    Cuando el usuario hace Login, buscamos noticias recientes.
    EXCLUIMOS a Administradores y Staff.
    """
    
    # 1. FILTRO DE EXCLUSIÓN
    if user.is_superuser or user.is_staff:
        return

    # A) Definir límites de tiempo
    days_back_limit = timezone.now() - timedelta(days=7)
    user_join_date = user.date_joined
    start_date = max(days_back_limit, user_join_date)

    # 2. Buscamos noticias candidatas
    recent_news = News.objects.filter(
        published_at__gte=start_date,     
        published_at__lte=timezone.now(), 
        notify_push=True                  
    )

    notifications_to_create = []

    for news in recent_news:
        # --- CORRECCIÓN DE URL AQUÍ ---
        # Usamos la estructura exacta que me indicaste: /news/news/user/ID/
        news_url = f"/news/news/user/{news.id}/"

        # 3. Verificamos si YA tiene la notificación (buscando por esa URL exacta)
        already_exists = Notification.objects.filter(
            user=user,
            module="noticias",
            url=news_url
        ).exists()

        if not already_exists:
            notifications_to_create.append(
                Notification(
                    user=user,
                    title=f"Nueva Noticia: {news.title}",
                    body=f"Se ha publicado: {news.title}",
                    url=news_url,
                    module="noticias"
                )
            )

    # 4. Crear en bloque
    if notifications_to_create:
        Notification.objects.bulk_create(notifications_to_create)