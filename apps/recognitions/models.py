from django.db import models
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

HEX_VALIDATOR = RegexValidator(
    regex=r"^#[0-9A-Fa-f]{6}$",
    message=_("Usa un color válido en formato #RRGGBB"),
)

class RecognitionCategory(models.Model):
    title = models.CharField(_("Título"), max_length=100, unique=True)
    points = models.PositiveIntegerField(_("Puntos"), default=0)

    # Color libre (el usuario lo elige)
    color_hex = models.CharField(
        _("Color"), max_length=7, validators=[HEX_VALIDATOR], default="#1E3361"
    )

    # Imagen de portada opcional
    cover_image = models.ImageField(
        _("Imagen de portada"), upload_to="recognitions/covers/", null=True, blank=True
    )

    # Switches para la portada
    confetti_enabled = models.BooleanField(_("Efecto confeti"), default=True)
    show_points = models.BooleanField(_("Mostrar puntaje"), default=False)

    # Organización
    is_active = models.BooleanField(_("Activo"), default=True)
    order = models.PositiveIntegerField(_("Orden"), default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "title"]

    def __str__(self):
        return self.title
