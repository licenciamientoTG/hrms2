from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('incentives', '0007_faltaempleado'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PresupuestoVentaSemanal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('team_key', models.CharField(max_length=50, verbose_name='Clave de estación')),
                ('semana', models.DateField(verbose_name='Semana (lunes)')),
                ('gas', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Gas')),
                ('diesel', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Diesel')),
                ('subido_por', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='presupuestos_venta_semanal',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Subido por',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Presupuesto de venta semanal',
                'verbose_name_plural': 'Presupuestos de venta semanales',
                'unique_together': {('team_key', 'semana')},
            },
        ),
    ]
