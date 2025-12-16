from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

MODULE_CHOICES = [
    ('usuarios', 'Usuarios'),
    ('noticias', 'Noticias'),
    ('comunicados', 'Comunicados'),
    ('constancias', 'Solicitud de constancias'),
    ('encuestas', 'Encuestas'),
    ('cursos', 'Cursos'),
    ('organigrama', 'Organigrama'),
    ('vacaciones', 'Vacaciones y permisos'),
    ('evaluacion', 'Evaluación de desempeño'),
    ('objetivos', 'Objetivos'),
    ('archivo', 'Archivo'),
    ('onboarding', 'Onboarding'),
    ('mis_documentos', 'Mis documentos'),
    ('vacantes', 'Vacantes'),
    ('politicas', 'Políticas internas'),
    ('plan_carrera', 'Plan de carrera'),
    ('requisiciones', 'Requisición de personal'),
]

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    module = models.CharField(max_length=40, blank=True, choices=MODULE_CHOICES)
    title = models.CharField(max_length=140)
    body  = models.TextField(blank=True)
    url   = models.URLField(blank=True)  # opcional
    created_at = models.DateTimeField(auto_now_add=True)
    read_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [models.Index(fields=['user', 'read_at', '-created_at'])]

    @property
    def is_read(self):
        return self.read_at is not None
