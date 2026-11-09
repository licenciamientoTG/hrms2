from django.db import models
from django.conf import settings


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
            ("auditoria_terminos", "Acceso a Auditoría de Términos"),
        ]


class LinkedAccount(models.Model):
    admin_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='linked_account',
    )
    employee_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='linked_from_admin',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
    )

    class Meta:
        verbose_name = 'Cuenta vinculada'
        verbose_name_plural = 'Cuentas vinculadas'

    def __str__(self):
        return f'{self.admin_user.username} → {self.employee_user.username}'