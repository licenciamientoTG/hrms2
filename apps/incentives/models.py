from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class IncentivosConfig(models.Model):
    """Modelo sin tabla, solo para definir el permiso del módulo."""
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ('Modulo_incentivos', 'Puede acceder al módulo de incentivos'),
        ]


class IncentivoRegistro(models.Model):
    """Registro de un bono otorgado a un empleado en una fecha."""
    employee = models.ForeignKey(
        'employee.Employee',
        on_delete=models.CASCADE,
        related_name='incentivo_registros',
        verbose_name='Empleado',
    )
    tipo = models.CharField(max_length=50, verbose_name='Tipo')
    fecha = models.DateField(verbose_name='Fecha')
    monto = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        verbose_name='Monto',
        help_text='Nulo si es solo palomita (ej. Diesel)',
    )
    registrado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='incentivos_registrados',
        verbose_name='Registrado por',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('employee', 'tipo', 'fecha')]
        verbose_name = 'Registro de incentivo'
        verbose_name_plural = 'Registros de incentivos'

    def __str__(self):
        return f"{self.employee} — {self.tipo} — {self.fecha}"


class ComentarioSemana(models.Model):
    """Comentario del gerente para un tipo de incentivo en una semana."""
    employee = models.ForeignKey(
        'employee.Employee',
        on_delete=models.CASCADE,
        related_name='comentarios_semana',
    )
    tipo = models.CharField(max_length=50)
    week_start = models.DateField()
    comentario = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        unique_together = [('employee', 'tipo', 'week_start')]
        verbose_name = 'Comentario de semana'
        verbose_name_plural = 'Comentarios de semana'

    def __str__(self):
        return f"{self.employee} — {self.tipo} — {self.week_start}"
