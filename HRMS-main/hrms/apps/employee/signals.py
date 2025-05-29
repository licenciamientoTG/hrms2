from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from apps.employee.models import Employee

@receiver(post_save, sender=Employee)
def create_user_for_employee(sender, instance, created, **kwargs):
    if created and instance.user is None:
        # Usamos el correo como username, si no hay, combinamos nombre/apellido
        username = instance.email or f"{instance.first_name.lower()}.{instance.last_name.lower()}"

        # Asegurarse de que sea único
        base_username = username.split('@')[0]
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

        # Asociarlo al empleado
        instance.user = user
        instance.save()
