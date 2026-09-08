from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('incentives', '0013_ecv_datos_iniciales'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PrenominaUpload',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('semana', models.DateField(verbose_name='Semana (lunes)')),
                ('subido_el', models.DateTimeField(auto_now_add=True)),
                ('total_registros', models.IntegerField(default=0)),
                ('subido_por', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='prenominas_subidas',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Subido por',
                )),
            ],
            options={
                'verbose_name': 'Carga de prenómina',
                'verbose_name_plural': 'Cargas de prenómina',
                'ordering': ['-semana'],
            },
        ),
        migrations.CreateModel(
            name='PrenominaRegistro',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.CharField(max_length=20, verbose_name='#')),
                ('nombre', models.CharField(max_length=200, verbose_name='Nombre')),
                ('horas_ordinarias', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('horas_dobles', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('horas_triples', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('dias_falta', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('dias_permiso_sg', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('dias_vacaciones', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('dias_incapacidad', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('horas_festivo', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('horas_descanso_trab', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('equipo', models.CharField(blank=True, max_length=100, verbose_name='Equipo')),
                ('puesto', models.CharField(blank=True, max_length=200, verbose_name='Puesto')),
                ('estatus', models.CharField(blank=True, max_length=50, verbose_name='Estatus')),
                ('neto', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Neto')),
                ('upload', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='registros',
                    to='incentives.PrenominaUpload',
                )),
            ],
            options={
                'verbose_name': 'Registro de prenómina',
                'verbose_name_plural': 'Registros de prenómina',
            },
        ),
    ]
