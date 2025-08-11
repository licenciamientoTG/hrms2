from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from datetime import date

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
    nacimiento_menor = models.DateField(
        verbose_name="Fecha de nacimiento del menor"
    )
    
    #archivo que sube el admin como respuesta
    pdf_respuesta = models.FileField(
        upload_to='guarderia_respuestas/',
        null=True, blank=True
    )
    respondido_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='guarderia_respuestas_hechas'
    )
    respondido_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        permissions = [
            ("puede_solicitar_guarderia", "Puede solicitar constancia de guardería"),
            ("puede_solicitar_personal", "Puede solicitar personal"),
        ]

    def __str__(self):
        return f"Constancia de {self.empleado.get_full_name()} - {self.fecha_solicitud.date()}"

    @property
    def estado(self):
        # Si manejas autorizaciones, conserva tu lógica. Si no, márcala como completada cuando haya PDF.
        try:
            autorizaciones = self.autorizaciones.all()
        except Exception:
            autorizaciones = []
        if autorizaciones:
            estados = [a.estado for a in autorizaciones]
            if any(est == 'rechazado' for est in estados):
                return 'rechazada'
            elif all(est == 'aprobado' for est in estados):
                return 'completada'
            else:
                return 'en progreso'
        return "completada" if self.pdf_respuesta else "en progreso"

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
