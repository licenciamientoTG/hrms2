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


class SemanaCerrada(models.Model):
    """Semana bloqueada para edición — solo admin/nóminas puede abrir/cerrar."""
    week_start = models.DateField(unique=True, verbose_name='Inicio de semana')
    cerrada_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='semanas_cerradas',
        verbose_name='Cerrada por',
    )
    cerrada_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Semana cerrada'
        verbose_name_plural = 'Semanas cerradas'

    def __str__(self):
        return f"Semana {self.week_start} (cerrada)"


class PresupuestoVenta(models.Model):
    """Presupuesto mensual de ventas por estación, cargado desde Excel."""
    team_key = models.CharField(max_length=50, verbose_name='Clave de estación')
    mes = models.DateField(verbose_name='Mes (primer día)')
    maxima = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='Máxima')
    gasolina_super = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='Super')
    diesel = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='Diesel')
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='Total')
    subido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='presupuestos_venta',
        verbose_name='Subido por',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('team_key', 'mes')]
        verbose_name = 'Presupuesto de venta'
        verbose_name_plural = 'Presupuestos de venta'

    def __str__(self):
        return f"{self.team_key} — {self.mes.strftime('%B %Y')}"


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
