from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('org_chart', '0002_alter_department_options'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrgChartViewState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chart_left', models.FloatField(default=0, help_text='Posición horizontal del canvas (px)')),
                ('chart_top', models.FloatField(default=0, help_text='Posición vertical del canvas (px)')),
                ('scale', models.FloatField(default=1.0, help_text='Nivel de zoom')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Estado de vista del organigrama',
            },
        ),
    ]
