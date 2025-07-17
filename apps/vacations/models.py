from django.db import models
from django.contrib.auth.models import User

class VacationRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    SOLICITUD_CHOICES = [
        ('Descanso médico', 'Descanso médico'),
        ('Días de estudio', 'Días de estudio'),
        ('Licencia por maternidad', 'Licencia por maternidad'),
        ('Vacaciones', 'Vacaciones'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tipo_solicitud = models.CharField(
        max_length=50,
        choices=SOLICITUD_CHOICES,
        default='Vacaciones'  # <-- este valor se aplicará a los registros existentes
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True)
    documento = models.FileField(upload_to='documentos/', blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tipo_solicitud} - {self.user.username} ({self.status})"
