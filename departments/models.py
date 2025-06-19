from django.db import models
from django.utils.timezone import now

class Department(models.Model):
    id = models.AutoField(primary_key=True, verbose_name='ID')
    name = models.CharField(max_length=150, null=False, verbose_name='Nombre')
    abbreviated = models.CharField(max_length=4, null=False, verbose_name='Abreviatura')
    updated_at = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de Actualización')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')

    def save(self, *args, **kwargs):
        self.updated_at = now()
        super(Department, self).save(*args, **kwargs)

    class Meta:
        verbose_name = 'Departamento'
        verbose_name_plural = 'Departamentos'

    def __str__(self):
        return self.name