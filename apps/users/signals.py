# apps/users/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User, Permission
from django.urls import reverse
from apps.notifications.utils import notify
from apps.notifications.models import Notification # Importamos el modelo
from django.db.models import Q

@receiver(post_save, sender=User)
def notificar_nuevo_usuario(sender, instance, created, **kwargs):
    if not created:
        return

    unique_key = f"new-user-{instance.pk}"
    ya_notificado = Notification.objects.filter(
        module="usuarios", 
        title="Nuevo usuario registrado",
        body__icontains=instance.username # O busca por dedupe_key si tu tabla la tiene
    ).exists()

    if ya_notificado:
        print(f"⏭️ Notificación omitida: {instance.username} ya fue anunciado antes.")
        return
    # ---------------------------------

    perm = Permission.objects.filter(
        content_type__app_label="users",
        codename="Modulo_usuarios"
    ).first()

    if not perm:
        return

    admins = User.objects.filter(
        is_active=True
    ).filter(
        Q(is_superuser=True)
        | Q(user_permissions=perm)
        | Q(groups__permissions=perm)
    ).distinct()

    nombre = instance.get_full_name() or instance.username
    email = instance.email or "sin email"
    titulo = "Nuevo usuario registrado"

    try:
        base_url = reverse('user_dashboard')
        url = f"{base_url}?q={instance.username}"
    except Exception:
        url = ""

    cuerpo = f"El usuario {nombre} ({email}) se ha unido al sistema."

    for admin in admins:
        if admin.pk != instance.pk:
            notify(
                user=admin,
                title=titulo,
                body=cuerpo,
                url=url,
                module="usuarios",
                dedupe_key=unique_key
            )