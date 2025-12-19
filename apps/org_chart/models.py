from django.db import models

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
