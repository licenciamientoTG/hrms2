from django.db import models


class IncentivosConfig(models.Model):
    """Modelo sin tabla, solo para definir el permiso del módulo."""
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ('Modulo_incentivos', 'Puede acceder al módulo de incentivos'),
        ]
