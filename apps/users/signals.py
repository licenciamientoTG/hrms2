# apps/users/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.urls import reverse
from apps.notifications.utils import notify
from django.db.models import Q

@receiver(post_save, sender=User)
def notificar_nuevo_usuario(sender, instance, created, **kwargs):
    """
    Envía una notificación a todos los superusuarios cuando se registra un nuevo usuario.
    """
    if created:

        admins = User.objects.filter(
            Q(is_staff=True) | Q(is_superuser=True), 
            is_active=True
        )        
        nombre = instance.get_full_name() or instance.username
        email = instance.email or "sin email"
        
        # 2. Título personalizado (opcional, ayuda a distinguir visualmente)
        titulo = "Nuevo usuario registrado" 
        
        # 3. URL ÚNICA (SOLUCIÓN):
        try:
            base_url = reverse('user_dashboard')
            url = f"{base_url}?q={instance.username}"
        except Exception:
            url = ""

        cuerpo = f"El usuario {nombre} ({email}) se ha unido al sistema."

        # 4. Enviar notificación a cada admin
        for admin in admins:
            if admin.pk != instance.pk:
                notify(
                    user=admin,
                    title=titulo,
                    body=cuerpo,
                    url=url,
                    module="usuarios",
                    dedupe_key=f"new-user-{instance.pk}" 
                )