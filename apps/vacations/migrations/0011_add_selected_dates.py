from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vacations', '0010_add_comentario_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='vacationrequest',
            name='selected_dates',
            field=models.TextField(blank=True, null=True),
        ),
    ]
