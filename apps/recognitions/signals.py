from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import Recognition
from apps.notifications.models import Notification

@receiver(user_logged_in)
def generate_missed_recognition_notifications(sender, user, request, **kwargs):
    """
    Cuando el usuario hace Login, buscamos comunicados recientes 
    donde él sea uno de los destinatarios (recipients).
    """
    
    # 1. Límite de tiempo: Buscamos comunicados de los últimos 30 días.
    # (Los comunicados son más personales, vale la pena mostrarlos por más tiempo)
    days_back_limit = timezone.now() - timedelta(days=30)
    
    # 2. Fecha de corte: Lo más reciente entre "hace 30 días" y "fecha de registro del usuario"
    start_date = max(days_back_limit, user.date_joined)

    # 3. Buscar comunicados donde:
    #    - El usuario logueado está en la lista de 'recipients'
    #    - Ya están publicados
    #    - Son recientes
    recent_recognitions = Recognition.objects.filter(
        recipients=user,                  
        published_at__gte=start_date,     
        published_at__lte=timezone.now()
    )

    notifications_to_create = []

    for rec in recent_recognitions:
        # URL para ir a ver el comunicados. 
        # Asegúrate de que esta URL coincida con tu vista de usuario.
        # El parámetro '?highlight=' puede servirte para resaltar la tarjeta en el frontend.
        rec_url = f"/recognitions/?highlight={rec.id}"

        # 4. Verificar si ya existe para no duplicar
        already_exists = Notification.objects.filter(
            user=user,
            module="comunicados",
            url=rec_url
        ).exists()

        if not already_exists:
            notifications_to_create.append(
                Notification(
                    user=user,
                    title="¡Nuevo Comunicado!",
                    body=f"Has recibido un comunicado en la categoría: {rec.category.title}",
                    url=rec_url,
                    module="comunicados"
                )
            )

    # 5. Crear masivamente
    if notifications_to_create:
        Notification.objects.bulk_create(notifications_to_create)