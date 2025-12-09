from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from datetime import date
from django.db.models import Q, UniqueConstraint

class FormRequest(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Request from {self.name}"

class ConstanciaGuarderia(models.Model):
    empleado = models.ForeignKey(User, on_delete=models.CASCADE)
    dias_laborales = models.CharField(max_length=255)
    hora_entrada = models.TimeField()
    hora_salida = models.TimeField()
    nombre_guarderia = models.CharField(max_length=255)
    direccion_guarderia = models.TextField()
    nombre_menor = models.CharField(max_length=255)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    nacimiento_menor = models.DateField(verbose_name="Fecha de nacimiento del menor")

    pdf_respuesta = models.FileField(
        upload_to='guarderia_respuestas/',
        null=True, blank=True
    )
    respondido_por = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='guarderia_respuestas_hechas'
    )
    respondido_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        permissions = [
            ("puede_solicitar_guarderia", "Puede solicitar constancia de guardería"),
            ("puede_solicitar_personal", "Puede solicitar personal"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['empleado'],
                condition=models.Q(pdf_respuesta__isnull=True),
                name='uniq_guarderia_pendiente_por_empleado',
            ),
        ]

    def __str__(self):
        return f"Constancia de {self.empleado.get_full_name()} - {self.fecha_solicitud.date()}"

    @property
    def estado(self):
        """
        Retorna 'completada' si fue aprobada,
        'rechazada' si la última decisión fue rechazada,
        o 'en progreso' si aún no hay decisión final.
        """
        # OPTIMIZACIÓN: Si la vista ya nos dio el dato, lo usamos.
        if hasattr(self, 'ultimo_estado_db'):
            st = self.ultimo_estado_db
            if st == 'rechazado':
                return 'rechazada'
            if st == 'aprobado':
                return 'completada'
            return 'en progreso'

        # --- Lógica original (fallback por si se llama desde otro lado) ---
        from .models import SolicitudAutorizacion
        ct = ContentType.objects.get_for_model(ConstanciaGuarderia)
        qs = (SolicitudAutorizacion.objects
            .filter(content_type=ct, object_id=self.id)
            .order_by('-fecha_revision', '-id'))

        if qs.exists():
            last = qs.first()
            if last.estado == 'rechazado':
                return 'rechazada'
            if last.estado == 'aprobado':
                return 'completada'
            return 'en progreso'
        return 'en progreso'

class SolicitudAutorizacion(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    solicitud = GenericForeignKey('content_type', 'object_id')

    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    estado = models.CharField(max_length=20, choices=[
        ('pendiente', 'Pendiente'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
    ], default='pendiente')
    comentario = models.TextField(blank=True, null=True)
    fecha_revision = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.usuario} - {self.estado}"
