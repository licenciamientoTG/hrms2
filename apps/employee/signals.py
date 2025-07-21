from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Employee

@receiver(post_save, sender=Employee)
def create_user_for_employee(sender, instance, created, **kwargs):
    if created and instance.user is None:
        from apps.users.models import UserProfile  # 👈 IMPORT DENTRO DE LA FUNCIÓN

        emp_number = str(instance.employee_number)

        birth_date_part = ""
        if instance.curp and len(instance.curp) >= 11:
            birth_date_part = instance.curp[4:10]
        else:
            birth_date_part = "000000"

        username = emp_number
        password = f"{emp_number}{birth_date_part}"

        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        user = User.objects.create_user(
            username=username,
            email=instance.email or "",
            password=password,
            first_name=instance.first_name,
            last_name=instance.last_name
        )

        # Crear perfil de usuario (obligar a cambiar contraseña)
        UserProfile.objects.create(user=user)

        instance.user = user
        instance.save()

        print(f"✅ Usuario creado: {username} / Contraseña: {password}")
