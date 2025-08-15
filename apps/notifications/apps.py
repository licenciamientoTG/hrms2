from django.apps import AppConfig

class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    # ← IMPORTANTE: ruta completa del paquete
    name = 'apps.notifications'
    # (opcional) etiqueta corta usada en comandos
    label = 'notifications'
