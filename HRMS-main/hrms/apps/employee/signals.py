from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from apps.employee.models import Employee

@receiver(post_save, sender=Employee)
def create_user_for_employee(sender, instance, created, **kwargs):
    if created and instance.user is None:
        # Obtener inicial, apellido y número de empleado
        first_initial = instance.first_name[0].upper() if instance.first_name else "X"
        last_name_clean = instance.last_name.capitalize() if instance.last_name else "Empleado"
        emp_number = instance.employee_number

        base_username = f"{first_initial}{last_name_clean}{emp_number}"

        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        # Crear usuario
        user = User.objects.create_user(
            username=username,
            email=instance.email or "",
            password="cambiame123",
            first_name=instance.first_name,
            last_name=instance.last_name
        )

        # Vincular usuario con el empleado
        instance.user = user
        instance.save()
