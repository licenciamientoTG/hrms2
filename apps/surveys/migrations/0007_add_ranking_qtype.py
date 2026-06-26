# Generated manually on 2026-06-26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('surveys', '0006_alter_surveyanswer_question_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='surveyquestion',
            name='qtype',
            field=models.CharField(
                choices=[
                    ('text', 'Texto'),
                    ('integer', 'Número entero'),
                    ('decimal', 'Número decimal'),
                    ('single', 'Opciones (selección única)'),
                    ('multiple', 'Opciones (selección múltiple)'),
                    ('rating', 'Calificación'),
                    ('assessment', 'Evaluación'),
                    ('frecuency', 'Frecuencia'),
                    ('ranking', 'Ordenamiento (ranking)'),
                    ('none', 'Sin respuesta'),
                ],
                default='single',
                max_length=20,
            ),
        ),
    ]
