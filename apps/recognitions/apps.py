from django.apps import AppConfig


class RecognitionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.recognitions'

    # ESTO ES LO QUE FALTA: Importar las señales para que Django las escuche
    def ready(self):
            import apps.recognitions.signals