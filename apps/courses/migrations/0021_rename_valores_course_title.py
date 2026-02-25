from django.db import migrations


OLD_TITLE = "Valores"
NEW_TITLE = "Inducción 1: Presencia y valores"


def rename_and_align_valores_course(apps, schema_editor):
    CourseHeader = apps.get_model("courses", "CourseHeader")
    CourseConfig = apps.get_model("courses", "CourseConfig")

    # Renombra cursos existentes con el título viejo.
    CourseHeader.objects.filter(title__iexact=OLD_TITLE).update(title=NEW_TITLE)

    # Mantiene certificación activa para el curso ya renombrado (o si ya existía con título nuevo).
    valores_ids = CourseHeader.objects.filter(title__iexact=NEW_TITLE).values_list(
        "id", flat=True
    )
    CourseConfig.objects.filter(course_id__in=valores_ids, certification=False).update(
        certification=True
    )


def rollback_title(apps, schema_editor):
    CourseHeader = apps.get_model("courses", "CourseHeader")
    CourseHeader.objects.filter(title__iexact=NEW_TITLE).update(title=OLD_TITLE)


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0020_enable_valores_certification"),
    ]

    operations = [
        migrations.RunPython(rename_and_align_valores_course, rollback_title),
    ]
