from django.db import models
from django.utils import timezone
# Importamos el modelo Employee en lugar de User para tener acceso a Puestos, Departamentos, etc.
from apps.employee.models import Employee 

# --- MODELO 1: EL CICLO (La carpeta que agrupa todo) ---
class PerformanceReviewCycle(models.Model):
    """
    Define el periodo de evaluación (Ej: 'Evaluación Q1 2026').
    Aquí es donde se guarda si se creó por Excel, si es 360, etc.
    """
    STATUS_CHOICES = [
        ('setup', 'Configuración'),
        ('active', 'Activa / En Curso'),
        ('closed', 'Cerrada / Finalizada'),
    ]
    
    SCOPE_CHOICES = [
        ('excel', 'Carga Excel'),
        ('all', 'Toda la Organización'),
        ('manual', 'Selección Manual'),
    ]

    # Datos Generales
    name = models.CharField("Nombre del Ciclo", max_length=200)
    year = models.IntegerField("Año Fiscal")
    
    # Configuración
    review_type = models.CharField("Tipo", max_length=50) # 'cualitativa' o 'cuantitativa'
    is_360 = models.BooleanField("Es 360°", default=False)
    
    # Estado y Alcance
    status = models.CharField("Estado", max_length=20, choices=STATUS_CHOICES, default='setup')
    scope_type = models.CharField("Tipo de Selección", max_length=20, choices=SCOPE_CHOICES, default='excel')
    
    # Fechas
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField("Fecha de Cierre", null=True, blank=True)
    
    # Relación: Empleados que deben ser evaluados en este ciclo
    target_employees = models.ManyToManyField(
        Employee, 
        related_name='review_cycles_targeted', 
        blank=True,
        verbose_name="Empleados Objetivo"
    )

    def __str__(self):
        return f"{self.name} ({self.year})"

    class Meta:
        verbose_name = "Ciclo de Evaluación"
        verbose_name_plural = "Ciclos de Evaluación"


# --- MODELO 2: LA EVALUACIÓN INDIVIDUAL (Tu código integrado aquí) ---
class PerformanceReview(models.Model):
    """
    Representa la evaluación de UN empleado específico dentro de UN ciclo.
    Aquí guardamos la calificación y comentarios.
    """
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('pending_self', 'Pendiente Autoevaluación'),
        ('pending_manager', 'Pendiente Evaluación Jefe'),
        ('completed', 'Completada'),
    ]

    # Opciones de calificación (Lo que tú tenías)
    RATING_CHOICES = [
        (1, 'Pobre (Poor)'),
        (2, 'Regular (Fair)'),
        (3, 'Bueno (Good)'),
        (4, 'Muy Bueno (Very Good)'),
        (5, 'Excelente (Excellent)'),
    ]

    # Vínculos obligatorios
    cycle = models.ForeignKey(
        PerformanceReviewCycle, 
        on_delete=models.CASCADE, 
        related_name='reviews',
        verbose_name="Ciclo"
    )
    employee = models.ForeignKey(
        Employee, 
        on_delete=models.CASCADE, 
        related_name='my_performance_reviews',
        verbose_name="Empleado Evaluado"
    )

    # Quién lo evaluó (Opcional, usualmente es el Jefe Inmediato)
    reviewer = models.ForeignKey(
        Employee, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='reviews_given',
        verbose_name="Evaluador Principal"
    )
    
    # Estado del proceso
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Resultados (Tus campos originales)
    rating = models.IntegerField("Calificación Final", choices=RATING_CHOICES, null=True, blank=True)
    comments = models.TextField("Comentarios Generales", null=True, blank=True)
    
    # Fechas
    date_reviewed = models.DateTimeField("Fecha de Revisión", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee} - {self.cycle.name}"

    class Meta:
        # Regla: Un empleado solo puede tener UNA evaluación principal por ciclo
        unique_together = ['cycle', 'employee']
        verbose_name = "Evaluación de Desempeño"
        verbose_name_plural = "Evaluaciones de Desempeño"