from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from apps.employee.models import Employee

@receiver(post_save, sender=Employee)
def create_user_for_employee(sender, instance, created, **kwargs):
    if created and instance.user is None:
        emp_number = str(instance.employee_number)

        # Obtener fecha de nacimiento desde la CURP: posiciones 5 a 10 (6 dígitos)
        # Ejemplo: SDAE980603JSJOWQ01 → '980603'
        birth_date_part = ""
        if instance.curp and len(instance.curp) >= 11:
            birth_date_part = instance.curp[4:10]  # 5 a 10 (index base 0)

            # Invertir orden: '980603' → '030698'
            birth_date_part = birth_date_part[::-1]
        else:
            birth_date_part = "000000"  # Valor por defecto si no hay CURP

        # Construir username y contraseña
        username = emp_number
        password = f"{emp_number}{birth_date_part}"

        # Evitar duplicados de username
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        # Crear usuario
        user = User.objects.create_user(
            username=username,
            email=instance.email or "",
            password=password,
            first_name=instance.first_name,
            last_name=instance.last_name
        )

        # Vincular usuario con el empleado
        instance.user = user
        instance.save()

        print(f"✅ Usuario creado: {username} / Contraseña: {password}")
