from django.db import migrations
from datetime import date


DIAS = [
    (date(2026, 1, 1),  'Año nuevo'),
    (date(2026, 2, 2),  'Día de la Constitución'),
    (date(2026, 3, 16), 'Natalicio de Benito Juárez'),
    (date(2026, 5, 1),  'Día del trabajo'),
    (date(2026, 9, 16), 'Independencia de México'),
    (date(2026, 11, 16),'Revolución Mexicana'),
    (date(2026, 12, 25),'Navidad'),
    (date(2027, 1, 1),  'Año nuevo'),
    (date(2027, 2, 1),  'Día de la Constitución'),
    (date(2027, 3, 15), 'Natalicio de Benito Juárez'),
    (date(2027, 5, 1),  'Día del trabajo'),
]


def seed(apps, schema_editor):
    DiaInhabil = apps.get_model('vacations', 'DiaInhabil')
    for fecha, descripcion in DIAS:
        DiaInhabil.objects.get_or_create(fecha=fecha, defaults={'descripcion': descripcion})


def unseed(apps, schema_editor):
    DiaInhabil = apps.get_model('vacations', 'DiaInhabil')
    DiaInhabil.objects.filter(fecha__in=[f for f, _ in DIAS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('vacations', '0017_add_dia_inhabil'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
