from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import Recognition
from apps.notifications.models import Notification

@receiver(user_logged_in)
def generate_missed_recognition_notifications(sender, user, request, **kwargs):

    if user.is_staff:
        return

    if not user.has_perm('recognitions.Modulo_comunicados'):
        return

    print(f"--- SIGNAL DISPARADO: Usuario {user.username} ha entrado ---") # DEBUG
    
    start_date = timezone.now() - timedelta(days=30)
    from django.db.models import Q
    
    # Filtramos por audiencia: Público, Grupos del usuario o si es destinatario
    user_groups = user.groups.all()
    
    recent_recognitions = Recognition.objects.filter(
        published_at__gte=start_date,     
        published_at__lte=timezone.now(),
        status='published'
    ).filter(
        Q(is_public=True) | 
        Q(target_groups__in=user_groups) | 
        Q(recipients=user) |
        Q(target_groups__isnull=True, is_public=False) # Antiguos
    ).distinct().prefetch_related('recipients', 'category')
    
    print(f"--- Encontrados {recent_recognitions.count()} comunicados recientes para este usuario ---") # DEBUG

    notifications_to_create = []

    for rec in recent_recognitions:
        rec_url = f"/recognitions/?highlight={rec.id}#recognition-{rec.id}"

        already_exists = Notification.objects.filter(
            user=user,
            module="comunicados",
            url=rec_url
        ).exists()

        if not already_exists:
            print(f"   -> Creando notificación para {rec.id}") # DEBUG
            
            is_protagonist = user in rec.recipients.all()

            if is_protagonist:
                title = "¡Te han mencionado!"
                body = f"Has sido mencionado en un comunicado de: {rec.category.title}"
            else:
                title = "Nuevo Comunicado"
                body = f"Se ha publicado un nuevo comunicado en: {rec.category.title}"

            notifications_to_create.append(
                Notification(
                    user=user,
                    title=title,
                    body=body,
                    url=rec_url,
                    module="comunicados"
                )
            )
        else:
            print(f"   -> Ya existe notificación para {rec.id}, saltando.") # DEBUG

    if notifications_to_create:
        Notification.objects.bulk_create(notifications_to_create)
        print(f"--- Se crearon {len(notifications_to_create)} notificaciones ---") # DEBUG