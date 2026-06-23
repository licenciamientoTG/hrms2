from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authapp', '0002_userprofile_accepted_terms'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='accepted_checador_policy',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='accepted_checador_policy_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
