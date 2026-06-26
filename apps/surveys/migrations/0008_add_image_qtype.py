# Generated manually on 2026-06-26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('surveys', '0007_add_ranking_qtype'),
    ]

    operations = [
        migrations.AddField(
            model_name='surveyquestion',
            name='image_url',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
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
                    ('image', 'Imagen de apoyo'),
                    ('none', 'Sin respuesta'),
                ],
                default='single',
                max_length=20,
            ),
        ),
    ]
