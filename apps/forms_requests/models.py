from django.db import models
from django.contrib.auth.models import User

class FormRequest(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Request from {self.name}"

class ConstanciaGuarderia(models.Model):
    empleado = models.ForeignKey(User, on_delete=models.CASCADE)
    dias_laborales = models.CharField(max_length=255)  # Guardado como string separado por comas
    hora_entrada = models.TimeField()
    hora_salida = models.TimeField()
    nombre_guarderia = models.CharField(max_length=255)
    direccion_guarderia = models.TextField()
    nombre_menor = models.CharField(max_length=255)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [
            ("puede_solicitar_guarderia", "Puede solicitar constancia de guardería"),
            ("puede_solicitar_personal", "Puede solicitar personal"),
        ]

    def __str__(self):
        return f"Constancia de {self.empleado.get_full_name()} - {self.fecha_solicitud.date()}"