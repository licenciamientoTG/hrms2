from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('org_chart', '0003_orgchartviewstate'),
    ]

    operations = [
        migrations.AddField(
            model_name='orgchartviewstate',
            name='node_y_offsets',
            field=models.TextField(
                default='{}',
                help_text='JSON {employee_id: px_offset} para desplazamiento visual vertical de nodos',
            ),
        ),
    ]
