from django.db import models
from apps.location.models import Location
from departments.models import Department
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
from django.contrib.auth.models import User


class Employee(models.Model):
    """
    Modelo para almacenar la información de los empleados.
    """
    
    # Información Básica
    employee_number = models.CharField(
        max_length=20,
        unique=True,
        verbose_name=_("Número de empleado"),
        help_text=_("Número único de identificación del empleado")
    )
    first_name = models.CharField(
        max_length=255,
        verbose_name=_("Nombres"),
        help_text=_("Nombre del empleado")
    )
    last_name = models.CharField(
        max_length=255,
        verbose_name=_("Apellidos"),
        help_text=_("Apellidos del empleado")
    )
    job_position = models.ForeignKey(
        'JobPosition', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name=_("Puesto"),
        help_text=_("Puesto que ocupa el empleado en la organización")
    )
    
    # Fechas y antigüedad
    start_date = models.DateField(
        verbose_name=_("Fecha de ingreso"),
        help_text=_("Fecha en que el empleado ingresó a la empresa")
    )

    # Información del empleado
    station = models.ForeignKey(
        'location.Location', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name=_("Estación"),
        help_text=_("Estación donde el empleado labora")
    )

    department = models.ForeignKey(
       'departments.Department',  # Correcto: 'departments.Department'
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Departamento"),
        help_text=_("Departamento al que pertenece el empleado")
    )

    rfc = models.CharField(
        max_length=13,
        verbose_name=_("RFC"),
        help_text=_("Registro Federal de Contribuyentes del empleado")
    )
    imss = models.CharField(
        max_length=11,
        verbose_name=_("IMSS"),
        help_text=_("Número de seguridad social del IMSS")
    )
    curp = models.CharField(
        max_length=18,
        verbose_name=_("CURP"),
        help_text=_("Clave Única de Registro de Población del empleado")
    )
    gender = models.CharField(
        max_length=10,
        choices=[('M', 'Masculino'), ('F', 'Femenino')],
        verbose_name=_("Sexo"),
        help_text=_("Sexo del empleado")
    )

    # Beneficios y saldo
    vacation_balance = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.0,
        verbose_name=_("Saldo de vacaciones"),
        help_text=_("Saldo de días de vacaciones disponibles del empleado")
    )
    
    # Información de contacto
    phone_number = models.CharField(
        max_length=10,
        verbose_name=_("Número de teléfono"),
        help_text=_("Número de teléfono del empleado"),
        validators=[RegexValidator(regex=r'^\d{10}$')] # 10 dígitos
    )
    address = models.TextField(
        verbose_name=_("Dirección"),
        help_text=_("Dirección completa del empleado")
    )

    # Campos de auditoría
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Fecha de creación"),
        help_text=_("Fecha y hora de creación del registro")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Fecha de actualización"),
        help_text=_("Fecha y hora de la última actualización")
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Activo"),
        help_text=_("Indica si el empleado está actualmente activo en la empresa")
    )

    email = models.EmailField(
        max_length=254,
        null=True,
        blank=True,
        verbose_name=_("Correo electrónico"),
        help_text=_("Correo de contacto del empleado")
    )

    photo = models.ImageField(
        upload_to='employees/photos/',
        null=True,
        blank=True,
        verbose_name=_("Fotografía"),
        help_text=_("Foto del empleado para su perfil")
    )

    birth_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Fecha de nacimiento"),
        help_text=_("Fecha de nacimiento del empleado")
    )

    termination_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Fecha de baja"),
        help_text=_("Fecha en que el empleado dejó de laborar")
    )

    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Usuario"),
        help_text=_("Cuenta de usuario vinculada al empleado")
    )

    education_level = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_("Nivel de estudios"),
        help_text=_("Nivel educativo alcanzado por el empleado (ej. Preparatoria, Licenciatura, etc.)")
    )

    notes = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Observaciones"),
        help_text=_("Notas internas o comentarios generales sobre el empleado")
    )

    class Meta:
        verbose_name = _("Empleado")
        verbose_name_plural = _("Empleados")
        ordering = ['last_name', 'first_name']
    
    def __str__(self):
        return f"{self.first_name} ({self.employee_number})" 
       
class JobPosition(models.Model):
    """
    Modelo para almacenar los puestos de trabajo dentro de la empresa.
    """

    # Información Básica
    title = models.CharField(
        max_length=100,
        verbose_name=_("Título"),
        help_text=_("Título oficial del puesto de trabajo")
    )

    department = models.ForeignKey(
        'departments.Department', 
        on_delete=models.PROTECT,
        verbose_name=_("Departamento"),
        help_text=_("Departamento al que pertenece este puesto")
    )

    # Descripción y Requisitos
    description = models.TextField(
        verbose_name=_("Descripción"),
        help_text=_("Descripción detallada de las funciones y responsabilidades del puesto")
    )

    requirements = models.TextField(
        verbose_name=_("Requisitos"),
        help_text=_("Requisitos necesarios para ocupar el puesto (educación, experiencia, habilidades)")
    )

    # Descripción y Requisitos
    skills = models.TextField(
        verbose_name=_("Habilidades"),
        help_text=_("Habilidades y competencias necesarias para desempeñar el puesto")
    )

    # Información Jerárquica
    reports_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subordinates',
        verbose_name=_("Reporta a"),
        help_text=_("Puesto de trabajo al que reporta directamente")
    )

    level = models.PositiveSmallIntegerField(
        verbose_name=_("Nivel jerárquico"),
        help_text=_("Nivel del puesto en la jerarquía organizacional (1 siendo el más alto)")
    )

    is_managerial = models.BooleanField(
        default=False,
        verbose_name=_("Puesto directivo"),
        help_text=_("Indica si el puesto tiene responsabilidades de gestión de personal")
    )

    job_category = models.ForeignKey(
        'JobCategory',
        on_delete=models.PROTECT,
        verbose_name=_("Categoría profesional"),
        help_text=_("Categoría o clasificación profesional del puesto")
    )

    remote_eligible = models.BooleanField(
        default=False,
        verbose_name=_("Elegible para trabajo remoto"),
        help_text=_("Indica si el puesto puede desempeñarse de forma remota")
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Activo"),
        help_text=_("Indica si el puesto está activo en la organización")
    )

    headcount = models.PositiveSmallIntegerField(
        default=1,
        verbose_name=_("Plazas disponibles"),
        help_text=_("Número de plazas aprobadas para este puesto")
    )

    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='job_positions_created',
        verbose_name=_("Creado por"),
        help_text=_("Usuario que creó este puesto")
    )
    
    updated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='job_positions_updated',
        verbose_name=_("Actualizado por"),
        help_text=_("Usuario que actualizó este puesto por última vez")
    )

    # Campos de Auditoría
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Fecha de creación"),
        help_text=_("Fecha y hora de creación del registro")
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Fecha de actualización"),
        help_text=_("Fecha y hora de la última actualización")
    )

    class Meta:
        verbose_name = _("Puesto de trabajo")
        verbose_name_plural = _("Puestos de trabajo")
        ordering = ['department', 'level', 'title']
        indexes = [
            models.Index(fields=['title']),
            models.Index(fields=['department', 'level']),
        ]

    def __str__(self):
        return f"{self.title} ({self.department})"

    def get_direct_reports_count(self):
        """
        Retorna el número de puestos que reportan directamente a este puesto.
        """
        return self.subordinates.count()
    
# En apps/employee/models.py
class JobCategory(models.Model):
    name = models.CharField(max_length=100, verbose_name=_("Nombre de la categoría"))
    description = models.TextField(verbose_name=_("Descripción"))

    class Meta:
        verbose_name = _("Categoría de puesto")
        verbose_name_plural = _("Categorías de puestos")

    def __str__(self):
        return self.name