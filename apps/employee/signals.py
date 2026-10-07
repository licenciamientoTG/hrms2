from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Employee

@receiver(post_save, sender=Employee)
def create_user_for_employee(sender, instance, created, **kwargs):
    from authapp.models import UserProfile

    emp_number = str(instance.employee_number)

    # 🚫 Si el empleado NO está activo y tiene usuario → eliminarlo
    if not instance.is_active and instance.user:
        user = instance.user
        username = user.username
        instance.user = None  # Quitar relación antes de eliminar
        instance.save()
        user.delete()
        print(f"❌ Usuario {username} eliminado porque el empleado fue desactivado")
        return

    # ✅ Si es nuevo y activo → crear usuario
    if created and instance.user is None and instance.is_active:
        # Copiar foto de un registro inactivo con el mismo nombre si existe
        if not instance.photo:
            duplicado = Employee.objects.filter(
                is_active=False,
                first_name__iexact=instance.first_name,
                last_name__iexact=instance.last_name,
            ).exclude(photo='').exclude(photo__isnull=True).first()
            if duplicado:
                instance.photo = duplicado.photo

        birth_date_part = instance.curp[4:10] if instance.curp and len(instance.curp) >= 11 else "000000"
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
            last_name=instance.last_name,
            is_active=True
        )

        UserProfile.objects.create(user=user)
        instance.user = user
        instance.save()

        print(f"✅ Usuario creado: {username} / Contraseña: {password}")

    # 🔄 Si el empleado ya tenía usuario y sigue activo, solo sincroniza el estado
    elif instance.user and instance.is_active:
        user = instance.user
        user.is_active = True
        user.save()
        print(f"🔄 Usuario {user.username} actualizado - Activo: {user.is_active}")
