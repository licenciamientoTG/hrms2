from django.db import models


class OrgChartViewState(models.Model):
    """
    Singleton que guarda la posición visual del canvas del organigrama.
    El superadmin mueve/zoomea y esa posición se persiste para todos.
    """
    chart_left      = models.FloatField(default=0, help_text="Posición horizontal del canvas (px)")
    chart_top       = models.FloatField(default=0, help_text="Posición vertical del canvas (px)")
    scale           = models.FloatField(default=1.0, help_text="Nivel de zoom")
    node_y_offsets  = models.TextField(default='{}', help_text="JSON {employee_id: px_offset} para desplazamiento visual vertical de nodos")
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Estado de vista del organigrama'


class Department(models.Model):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subdepartments')

    class Meta:
        permissions = [
            ("Modulo_organigrama", "Acceso al Módulo de Organigrama"),
        ]

    def __str__(self):
        return self.name

class Employee(models.Model):
    name = models.CharField(max_length=255)
    position = models.CharField(max_length=255)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    supervisor = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.name} - {self.position}"
