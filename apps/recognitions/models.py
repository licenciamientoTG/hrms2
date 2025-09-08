from django.db import models
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
from django.conf import settings

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

User = settings.AUTH_USER_MODEL

class Recognition(models.Model):
    author      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recognitions_sent')
    category    = models.ForeignKey('RecognitionCategory', on_delete=models.PROTECT)
    message     = models.TextField(blank=True)
    image       = models.ImageField(upload_to='recognitions/', blank=True, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    recipients  = models.ManyToManyField(User, related_name='recognitions_received', through='RecognitionRecipient')

    # 👍 NUEVO: M2M con through para controlar likes
    likes = models.ManyToManyField(
        User, through='RecognitionLike',
        related_name='recognitions_liked', blank=True
    )

    def __str__(self):
        return f'{self.author} → {self.category} ({self.created_at:%Y-%m-%d})'

class RecognitionLike(models.Model):
    recognition = models.ForeignKey(Recognition, on_delete=models.CASCADE, related_name='likes_rel')
    user        = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (('recognition', 'user'),)  # evita duplicados

class RecognitionRecipient(models.Model):
    recognition = models.ForeignKey(Recognition, on_delete=models.CASCADE)
    user        = models.ForeignKey(User, on_delete=models.CASCADE)

class RecognitionComment(models.Model):
    recognition = models.ForeignKey(
        'Recognition',
        on_delete=models.CASCADE,
        related_name='comments'
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Comment by {self.author} on {self.recognition_id}'

class RecognitionMedia(models.Model):
    recognition = models.ForeignKey(
        Recognition,
        on_delete=models.CASCADE,
        related_name='media'
    )
    file = models.ImageField(upload_to='recognitions/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Media #{self.pk} of Rec #{self.recognition_id}'
