from django.db import migrations


def cargar_datos(apps, schema_editor):
    CategoriaECV = apps.get_model('incentives', 'CategoriaECV')
    IndicadorECV = apps.get_model('incentives', 'IndicadorECV')

    cat_a, _ = CategoriaECV.objects.get_or_create(
        nombre='A',
        defaults={'descripcion': 'Sin bomba de Diésel'},
    )
    cat_b, _ = CategoriaECV.objects.get_or_create(
        nombre='B',
        defaults={'descripcion': 'Con bomba de Diésel'},
    )

    indicadores_a = [
        # (nombre, ponderacion, minimo, objetivo, excelente, unidad, direccion, orden)
        ('venta_gas',  40, 97,    100,    103,   'porcentaje', 'mayor', 1),
        ('mistery',    25, 92,    100,    103,   'porcentaje', 'mayor', 2),
        ('faltante',   20, 500,   100,    0,     'monto',      'menor', 3),
        ('incidencia', 15, 3,     2,      0,     'conteo',     'menor', 4),
    ]
    indicadores_b = [
        ('venta_gas',    30, 97,  100,    103,   'porcentaje', 'mayor', 1),
        ('venta_diesel', 10, 97,  100,    103,   'porcentaje', 'mayor', 2),
        ('mistery',      25, 92,  100,    103,   'porcentaje', 'mayor', 3),
        ('faltante',     20, 500, 100,    0,     'monto',      'menor', 4),
        ('incidencia',   15, 3,   2,      0,     'conteo',     'menor', 5),
    ]

    for cat, indicadores in [(cat_a, indicadores_a), (cat_b, indicadores_b)]:
        for nombre, pond, mini, obj, exc, unidad, direccion, orden in indicadores:
            IndicadorECV.objects.get_or_create(
                categoria=cat,
                nombre=nombre,
                defaults={
                    'ponderacion':      pond,
                    'umbral_minimo':    mini,
                    'umbral_objetivo':  obj,
                    'umbral_excelente': exc,
                    'unidad':           unidad,
                    'direccion':        direccion,
                    'orden':            orden,
                },
            )


def revertir_datos(apps, schema_editor):
    CategoriaECV = apps.get_model('incentives', 'CategoriaECV')
    CategoriaECV.objects.filter(nombre__in=['A', 'B']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('incentives', '0012_categoria_indicador_ecv'),
    ]

    operations = [
        migrations.RunPython(cargar_datos, revertir_datos),
    ]
