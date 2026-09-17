from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vacations', '0015_alter_vacationrequest_tipo_solicitud'),
    ]

    operations = [
        migrations.AlterField(
            model_name='vacationrequest',
            name='tipo_solicitud',
            field=models.CharField(
                choices=[
                    ('Descanso médico', 'Descanso médico'),
                    ('Días de estudio', 'Días de estudio'),
                    ('Home Office', 'Home Office'),
                    ('Licencia por maternidad', 'Licencia por maternidad'),
                    ('Permiso sin Goce de Sueldo', 'Permiso sin Goce de Sueldo'),
                    ('Vacaciones', 'Vacaciones'),
                ],
                default='Vacaciones',
                max_length=50,
            ),
        ),
    ]
