from django.db import models
from django.db import models
from django.core.validators import EmailValidator
from django.utils.translation import gettext_lazy as _

class Location(models.Model):
    """
    Modelo para almacenar la información de las ubicaciones o sucursales de la empresa.
    """
    name = models.CharField(
        max_length=150, 
        verbose_name=_("Nombre"), 
        help_text=_("Nombre completo de la ubicación o sucursal")
    )
    rfc = models.CharField(
        max_length=13, 
        verbose_name=_("RFC"), 
        help_text=_("Registro Federal de Contribuyentes de la ubicación")
    )
    denomination = models.CharField(
        max_length=100, 
        verbose_name=_("Denominación"), 
        help_text=_("Denominación o razón social de la ubicación")
    )
    address = models.TextField(
        verbose_name=_("Domicilio"), 
        help_text=_("Dirección completa de la ubicación")
    )
    city = models.CharField(
        max_length=100, 
        verbose_name=_("Ciudad"), 
        help_text=_("Ciudad donde se encuentra la ubicación")
    )
    state = models.CharField(
        max_length=100, 
        null=True,  # Permitir que sea nulo
        blank=True,  # Permitir que esté en blanco
        verbose_name=_("Estado"), 
        help_text=_("Estado o provincia donde se encuentra la ubicación")
    )
    country = models.CharField(
        max_length=100, 
        default="México", 
        verbose_name=_("País"), 
        help_text=_("País donde se encuentra la ubicación")
    )
    postal_code = models.CharField(
        max_length=10, 
        null=True,  # Permitir que sea nulo
        blank=True,  # Permitir que esté en blanco
        verbose_name=_("Código postal"), 
        help_text=_("Código postal de la ubicación")
    )
    email = models.EmailField(
        validators=[EmailValidator()],
        verbose_name=_("Correo electrónico"), 
        help_text=_("Correo electrónico principal de contacto de la ubicación")
    )
    phone = models.CharField(
        max_length=20, 
        blank=True, 
        null=True, 
        verbose_name=_("Teléfono"), 
        help_text=_("Número telefónico principal de la ubicación")
    )
    station = models.CharField(
        max_length=50, 
        verbose_name=_("Estación"), 
        help_text=_("Código o identificador de la estación")
    )
    server = models.CharField(
        max_length=100, 
        verbose_name=_("Servidor"), 
        help_text=_("Nombre o dirección IP del servidor asignado a esta ubicación")
    )
    structure = models.CharField(
        max_length=100, 
        null=True,  # Permitir que sea nulo
        blank=True,  # Permitir que esté en blanco
        verbose_name=_("Estructura"), 
        help_text=_("Estructura organizacional de la ubicación")
    )
    group = models.CharField(
        max_length=100, 
        null=True,  # Permitir que sea nulo
        blank=True,  # Permitir que esté en blanco
        verbose_name=_("Grupo"), 
        help_text=_("Grupo al que pertenece esta ubicación")
    )
    tax = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        verbose_name=_("IVA"), 
        help_text=_("Porcentaje de IVA aplicable a esta ubicación")
    )

    is_headquarters = models.BooleanField(
        default=False, 
        verbose_name=_("Casa matriz"), 
        help_text=_("Indica si esta ubicación es la casa matriz de la empresa")
    )

    cost_center = models.CharField(
        max_length=20, 
        blank=True, 
        null=True, 
        verbose_name=_("Centro de costos"), 
        help_text=_("Código del centro de costos asociado a esta ubicación")
    )
    is_active = models.BooleanField(
        default=True, 
        verbose_name=_("Activo"), 
        help_text=_("Indica si la ubicación está activa")
    )
    
    # Agregar los campos de auditoría como opcionales para hacer pruebas
    created_by = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='locations_created', 
        verbose_name=_("Creado por"), 
        help_text=_("Usuario que creó esta ubicación")
    )
    updated_by = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='locations_updated', 
        verbose_name=_("Actualizado por"), 
        help_text=_("Usuario que actualizó esta ubicación por última vez")
    )

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
        verbose_name = _("Ubicación")
        verbose_name_plural = _("Ubicaciones")
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.city})"

    def get_full_address(self):
        """
        Devuelve la dirección completa y formateada de la ubicación.
        """
        return f"{self.address}, {self.city}, {self.state}, {self.country}, CP: {self.postal_code}"
    
    def get_contact_info(self):
        """
        Devuelve la información de contacto de la ubicación.
        """
        return f"Tel: {self.phone} | Email: {self.email}"
    
    def get_tax_rate(self):
        """
        Devuelve el porcentaje de IVA aplicable a esta ubicación.
        """
        return f"{self.tax}%"