from django.db import models
from django.conf import settings
from decimal import Decimal

class LoanRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Usuario")
    
    # --- Datos copiados del Empleado (Snapshot) ---
    # Guardamos esto por si el empleado cambia de puesto o empresa en el futuro, 
    # el registro histórico del préstamo quede intacto.
    employee_number = models.CharField(max_length=20, verbose_name="# Empleado", blank=True)
    full_name = models.CharField(max_length=255, verbose_name="Nombre Completo", blank=True)
    job_position = models.CharField(max_length=150, verbose_name="Puesto", blank=True)
    company = models.CharField(max_length=255, verbose_name="Patrón / Empresa", blank=True)
    
    # --- Datos financieros del momento ---
    saving_fund_snapshot = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Ahorro Total (al solicitar)")
    
    # --- Datos de la solicitud ---
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Préstamo Solicitado")
    weeks = models.PositiveIntegerField(verbose_name="Plazos (Semanas)")
    payment_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Pago Semanal")
    
    # --- Control ---
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
        ('paid', 'Pagado'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Estado")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha del préstamo")

    # Propiedades calculadas (no se guardan en BD, se calculan al vuelo)
    @property
    def fifty_percent_limit(self):
        """El 50% del ahorro al momento de la solicitud"""
        return self.saving_fund_snapshot * Decimal("0.5")

    @property
    def percentage_authorized(self):
        """Porcentaje del límite que se está solicitando """
        limit = self.saving_fund_snapshot
        if limit > 0:
            return (float(self.amount) / float(limit)) * 100
        return 0

    class Meta:
        verbose_name = "Solicitud de Préstamo"
        verbose_name_plural = "Solicitudes de Préstamo"
        ordering = ['-created_at']

        permissions = [
            ("Modulo_herramientas", "Acceso al Módulo de Herramientas"),
        ]

    def __str__(self):
        return f"Solicitud #{self.id} - {self.full_name}"