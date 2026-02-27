from django.db import migrations


def enable_valores_certification(apps, schema_editor):
    CourseHeader = apps.get_model("courses", "CourseHeader")
    CourseConfig = apps.get_model("courses", "CourseConfig")

    valores_ids = CourseHeader.objects.filter(title__iexact="Valores").values_list(
        "id", flat=True
    )
    CourseConfig.objects.filter(
        course_id__in=valores_ids,
        certification=False,
    ).update(certification=True)


def noop(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0019_alter_courseheader_options"),
    ]

    operations = [
        migrations.RunPython(enable_valores_certification, noop),
    ]
