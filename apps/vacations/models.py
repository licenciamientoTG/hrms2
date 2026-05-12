from django.db import models
from django.contrib.auth.models import User

class VacationRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pendiente de Responsable'), 
        ('authorized', 'Pendiente de RH'),       
        ('approved', 'Aprobada / Finalizada'),   
        ('rejected', 'Rechazada'),              
    ]

    SOLICITUD_CHOICES = [
        ('Descanso médico', 'Descanso médico'),
        ('Días de estudio', 'Días de estudio'),
        ('Licencia por maternidad', 'Licencia por maternidad'),
        ('Vacaciones', 'Vacaciones'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    manager_approver = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='vacations_authorized'
    )

    tipo_solicitud = models.CharField(
        max_length=50,
        choices=SOLICITUD_CHOICES,
        default='Vacaciones' 
    )
    start_date = models.DateField()
    end_date = models.DateField()
    selected_dates = models.TextField(blank=True, null=True)  # CSV de fechas YYYY-MM-DD
    reason = models.TextField(blank=True)
    comentario_lider = models.TextField(blank=True, null=True)
    comentario_rh = models.TextField(blank=True, null=True)
    documento = models.FileField(upload_to='vacaciones/', blank=True, null=True)
    documento_lider = models.FileField(upload_to='vacaciones/lider/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tipo_solicitud} - {self.user.username} ({self.status})"

    @property
    def total_days(self):
        if self.selected_dates:
            return len([d for d in self.selected_dates.split(',') if d.strip()])
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return None

    @property
    def selected_dates_list(self):
        """Retorna lista de objetos date de los días seleccionados."""
        if not self.selected_dates:
            return []
        from datetime import datetime
        return sorted([
            datetime.strptime(d.strip(), '%Y-%m-%d').date()
            for d in self.selected_dates.split(',') if d.strip()
        ])

    @property
    def dates_display(self):
        """Texto legible de las fechas para mostrar en templates."""
        dates = self.selected_dates_list
        if dates:
            if len(dates) == 1:
                return dates[0].strftime('%d/%m/%Y')
            if len(dates) <= 6:
                return ', '.join(d.strftime('%d/%m/%Y') for d in dates)
            return f"{dates[0].strftime('%d/%m/%Y')} … {dates[-1].strftime('%d/%m/%Y')} ({len(dates)} días)"
        if self.start_date and self.end_date:
            return f"{self.start_date.strftime('%d/%m/%Y')} — {self.end_date.strftime('%d/%m/%Y')}"
        return '—'

        
    class Meta:
        permissions = [
            ("Modulo_vacaciones", "Acceso al Módulo de Vacaciones"),
            ("can_request_vacation", "Puede solicitar vacaciones"),
            ("can_approve_vacation", "Puede aprobar o rechazar solicitudes"),
            ("can_view_all_requests", "Puede ver todas las solicitudes"),
        ]
