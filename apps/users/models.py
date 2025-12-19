from django.db import models

class UserModuleAccess(models.Model):
    """
    Modelo 'fantasma' para registrar permisos del módulo de usuarios
    sin modificar el modelo User nativo de Django.
    """
    class Meta:
        managed = False  # <--- IMPORTANTE: No crea tabla en la BD
        default_permissions = () # Limpiamos los permisos por defecto
        permissions = [
            ("Modulo_usuarios", "Acceso al Módulo de Usuarios"),
        ]