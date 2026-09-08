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
            ('configurar_incentivos', 'Puede configurar montos de incentivos'),
        ]


class ConfiguracionIncentivos(models.Model):
    """Singleton con los parámetros configurables de incentivos."""
    encargado_primer_dia = models.IntegerField(
        default=200,
        verbose_name='Encargado — primer día ($)',
        help_text='Monto del primer día de Encargado por semana.',
    )
    encargado_incremento = models.IntegerField(
        default=100,
        verbose_name='Encargado — incremento por día adicional ($)',
        help_text='Monto que se agrega por cada día adicional de Encargado.',
    )
    encargado_max_dias = models.IntegerField(
        default=6,
        verbose_name='Encargado — máximo de días por semana',
    )
    diesel_por_dia = models.IntegerField(
        default=50,
        verbose_name='Diesel — monto por día ($)',
    )
    diesel_max_dias = models.IntegerField(
        default=6,
        verbose_name='Diesel — máximo de días por semana',
    )
    venta_monto_bajio = models.IntegerField(
        default=240,
        verbose_name='Venta — monto Bajío ($)',
        help_text='Monto del bono de Venta para estaciones Bajío.',
    )
    venta_monto_antiguedad = models.IntegerField(
        default=230,
        verbose_name='Venta — monto antigüedad ≤ 2019 ($)',
        help_text='Monto del bono de Venta para empleados con antigüedad hasta 2019.',
    )
    venta_monto_regular = models.IntegerField(
        default=200,
        verbose_name='Venta — monto regular ($)',
        help_text='Monto del bono de Venta para el resto de empleados.',
    )
    mistery_monto = models.IntegerField(
        default=50,
        verbose_name='Mistery — monto general ($)',
        help_text='Monto para todos los empleados de la estación que ganó Mistery.',
    )
    mistery_monto_evaluado = models.IntegerField(
        default=500,
        verbose_name='Mistery — monto persona evaluada ($)',
        help_text='Monto para la persona que fue evaluada en el Mistery.',
    )
    actualizado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='configuraciones_incentivos',
        verbose_name='Actualizado por',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración de incentivos'
        verbose_name_plural = 'Configuración de incentivos'

    def __str__(self):
        return 'Configuración de incentivos'

    @classmethod
    def get(cls):
        """Devuelve la instancia singleton, creándola con defaults si no existe."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


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


class PresupuestoVentaSemanal(models.Model):
    """Override de presupuesto semanal por estación para eventos extraordinarios."""
    team_key   = models.CharField(max_length=50, verbose_name='Clave de estación')
    semana     = models.DateField(verbose_name='Semana (lunes)')
    gas        = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='Gas')
    diesel     = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='Diesel')
    subido_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='presupuestos_venta_semanal', verbose_name='Subido por',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('team_key', 'semana')]
        verbose_name = 'Presupuesto de venta semanal'
        verbose_name_plural = 'Presupuestos de venta semanales'

    @property
    def total(self):
        return (self.gas or 0) + (self.diesel or 0)

    def __str__(self):
        return f"{self.team_key} — semana {self.semana}"


class FaltaEmpleado(models.Model):
    """Faltas semanales por empleado, sincronizadas desde TRESS cada lunes."""
    employee_number = models.CharField(max_length=20, verbose_name='Número de empleado')
    semana          = models.DateField(verbose_name='Semana (lunes)')
    faltas          = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Faltas')
    equipo          = models.CharField(max_length=100, blank=True, verbose_name='Equipo')
    nombre          = models.CharField(max_length=200, blank=True, verbose_name='Nombre')

    class Meta:
        unique_together     = [('employee_number', 'semana')]
        verbose_name        = 'Falta de empleado'
        verbose_name_plural = 'Faltas de empleados'

    def __str__(self):
        return f"{self.employee_number} — semana {self.semana} — {self.faltas} falta(s)"


class CategoriaECV(models.Model):
    """Categoría del incentivo ECV (p. ej. A = sin diésel, B = con diésel)."""
    nombre = models.CharField(max_length=10, unique=True, verbose_name='Nombre')
    descripcion = models.CharField(max_length=200, blank=True, verbose_name='Descripción')

    class Meta:
        verbose_name = 'Categoría ECV'
        verbose_name_plural = 'Categorías ECV'
        ordering = ['nombre']

    def __str__(self):
        return f"Categoría {self.nombre}"


class IndicadorECV(models.Model):
    """Indicador (KPI) de una categoría ECV con su ponderación y umbrales."""

    NOMBRE_CHOICES = [
        ('venta_gas',    'Venta Gasolina'),
        ('venta_diesel', 'Venta Diésel'),
        ('mistery',      'Mistery Shopper'),
        ('faltante',     'Faltante'),
        ('incidencia',   'Incidencia en cortes'),
    ]
    UNIDAD_CHOICES = [
        ('porcentaje', 'Porcentaje (%)'),
        ('monto',      'Monto ($)'),
        ('conteo',     'Conteo'),
    ]
    DIRECCION_CHOICES = [
        ('mayor', 'Mayor es mejor'),
        ('menor', 'Menor es mejor'),
    ]

    categoria     = models.ForeignKey(
        CategoriaECV, on_delete=models.CASCADE,
        related_name='indicadores', verbose_name='Categoría',
    )
    nombre        = models.CharField(max_length=20, choices=NOMBRE_CHOICES, verbose_name='Indicador')
    ponderacion   = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Ponderación (%)')
    umbral_minimo = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Umbral mínimo (80%)')
    umbral_objetivo  = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Umbral objetivo (100%)')
    umbral_excelente = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Umbral excelente (120%)')
    unidad        = models.CharField(max_length=15, choices=UNIDAD_CHOICES, verbose_name='Unidad')
    direccion     = models.CharField(
        max_length=10, choices=DIRECCION_CHOICES, default='mayor',
        verbose_name='Dirección', help_text='Si el valor más alto o más bajo es mejor.',
    )
    orden         = models.PositiveSmallIntegerField(default=0, verbose_name='Orden')

    class Meta:
        unique_together     = [('categoria', 'nombre')]
        ordering            = ['orden']
        verbose_name        = 'Indicador ECV'
        verbose_name_plural = 'Indicadores ECV'

    def __str__(self):
        return f"{self.categoria} — {self.get_nombre_display()} ({self.ponderacion}%)"


class PrenominaUpload(models.Model):
    """Carga de prenómina semanal subida por staff/admin."""
    semana = models.DateField(verbose_name='Semana (lunes)')
    subido_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='prenominas_subidas', verbose_name='Subido por',
    )
    subido_el = models.DateTimeField(auto_now_add=True)
    total_registros = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Carga de prenómina'
        verbose_name_plural = 'Cargas de prenómina'
        ordering = ['-semana']

    def __str__(self):
        return f"Prenómina semana {self.semana} ({self.total_registros} registros)"


class PrenominaRegistro(models.Model):
    """Registro individual de un empleado dentro de una carga de prenómina."""
    upload = models.ForeignKey(
        PrenominaUpload, on_delete=models.CASCADE, related_name='registros',
    )
    numero = models.CharField(max_length=20, verbose_name='#')
    nombre = models.CharField(max_length=200, verbose_name='Nombre')
    horas_ordinarias = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    horas_dobles = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    horas_triples = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    dias_falta = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    dias_permiso_sg = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    dias_vacaciones = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    dias_incapacidad = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    horas_festivo = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    horas_descanso_trab = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    equipo = models.CharField(max_length=100, blank=True, verbose_name='Equipo')
    puesto = models.CharField(max_length=200, blank=True, verbose_name='Puesto')
    estatus = models.CharField(max_length=50, blank=True, verbose_name='Estatus')
    neto = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Neto')

    class Meta:
        verbose_name = 'Registro de prenómina'
        verbose_name_plural = 'Registros de prenómina'

    def __str__(self):
        return f"{self.numero} — {self.nombre}"


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
