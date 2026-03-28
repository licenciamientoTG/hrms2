from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recognitions', '0010_recognition_is_priority_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='recognitionlike',
            name='reaction_type',
            field=models.CharField(
                choices=[
                    ('like', '👍'),
                    ('love', '❤️'),
                    ('haha', '😂'),
                    ('wow', '😮'),
                    ('sad', '😢'),
                    ('angry', '😡'),
                ],
                default='like',
                max_length=10,
            ),
        ),
    ]
