from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employee', '0014_add_leader_fk'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='org_chart_order',
            field=models.IntegerField(
                default=0,
                help_text='Posición visual entre hermanos del mismo nivel en el organigrama',
                verbose_name='Orden en organigrama',
            ),
        ),
    ]
