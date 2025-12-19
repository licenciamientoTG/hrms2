from django.db import models
from django.conf import settings

class ObjectiveCycle(models.Model):
    name = models.CharField(max_length=200)
    start_date = models.DateField(null=True, blank=True)
    end_date   = models.DateField(null=True, blank=True)

    limit_enabled  = models.BooleanField(default=False)
    min_objectives = models.PositiveIntegerField(null=True, blank=True)
    max_objectives = models.PositiveIntegerField(null=True, blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [
            ("Modulo_objetivos", "Acceso al Módulo de Objetivos"),
        ]

    def __str__(self):
        return self.name
