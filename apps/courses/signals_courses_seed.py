import os
import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db.models.signals import post_migrate
from django.dispatch import receiver

from apps.courses.models import (
    CourseHeader,
    CourseConfig,
    CourseCategory,
    ModuleContent,
    Lesson
)

log = logging.getLogger(__name__)
VALORES_OLD_TITLE = "Valores"
VALORES_NEW_TITLE = "Inducción 1: Presencia y valores"


def _read_static_file_bytes(rel_path: str):
    """
    Lee un archivo desde /static/... y regresa (bytes, filename) o (None, None) si no existe.
    """
    static_path = os.path.join(settings.BASE_DIR, "static", rel_path)
    if not os.path.exists(static_path):
        return None, None
    with open(static_path, "rb") as f:
        return f.read(), os.path.basename(static_path)


@receiver(post_migrate)
def ensure_valores_course(sender, **kwargs):
    """
    Crea/actualiza el curso de inducción de valores automáticamente al migrar courses.
    - Crea CourseHeader + portrait
    - Crea CourseConfig
    - Crea 1 módulo "Introducción"
    - Crea 1 lección "Video de Valores" con resource MP4 desde static
    """
    # ✅ correr solo cuando migra el app courses
    if sender.name not in ("apps.courses", "courses"):
        return

    # 1) Usuario SYSTEM
    system_user, _ = User.objects.get_or_create(
        username="system",
        defaults={
            "first_name": "SYSTEM",
            "last_name": "BOT",
            "is_active": True,
            "is_staff": True,   # staff para que cumpla reglas si luego filtran
            "is_superuser": False,
            "email": "system@local",
        }
    )

    # 2) Categoría
    category, _ = CourseCategory.objects.get_or_create(
        title="Cultura TotalGas",
        defaults={
            "description": "Cursos internos de cultura y valores.",
            "user": system_user
        }
    )

    # 3) Buscar/crear curso de inducción (evita duplicar si existía con nombre viejo)
    course = CourseHeader.objects.filter(
        title__in=[VALORES_NEW_TITLE, VALORES_OLD_TITLE]
    ).first()

    if not course:
        # 3.1) portrait obligatorio desde static
        img_bytes, img_name = _read_static_file_bytes("template/img/logos/logo_sencillo.png")

        if not img_bytes:
            log.warning(
                "No se encontró static/template/img/logos/logo_sencillo.png para portrait del curso de inducción."
            )
            return

        course = CourseHeader.objects.create(
            title=VALORES_NEW_TITLE,
            description="Memorama interactivo de valores TotalGas.",
            duration=0.5,  # 30 min
            category=category,
            user=system_user
        )

        # Guardar portrait como archivo en media/
        course.portrait.save(img_name, ContentFile(img_bytes), save=True)
        log.info("✅ CourseHeader de inducción creado.")
    elif course.title != VALORES_NEW_TITLE:
        course.title = VALORES_NEW_TITLE
        course.save(update_fields=["title"])

    # 4) Asegurar config (aunque el curso ya existiera)
    config, _ = CourseConfig.objects.get_or_create(
        course=course,
        defaults={
            "course_type": "mandatory",
            "sequential": True,
            "deadline": 90,
            "audience": "all_users",
            "certification": True,
            "requires_signature": False,
            "is_archived": False,
        }
    )
    if not config.certification:
        config.certification = True
        config.save(update_fields=["certification"])

    # 5) Asegurar módulo "Introducción"
    module, _ = ModuleContent.objects.get_or_create(
        course_header=course,
        title="Introducción",
        defaults={"description": "Video introductorio de valores."}
    )

    # 6) Asegurar lección "Video de Valores" con resource MP4
    lesson = Lesson.objects.filter(
        module_content=module,
        title__iexact="Video de Valores"
    ).first()

    if lesson:
        # Si ya existe, no duplicamos
        log.info("ℹ️ La lección 'Video de Valores' ya existe. No se crea de nuevo.")
        return

    # ✅ Ajusta aquí la ruta donde pondrás el mp4
    mp4_bytes, mp4_name = _read_static_file_bytes("template/videos/valores_intro.mp4")

    if not mp4_bytes:
        log.warning("⚠️ No se encontró el MP4 en static/template/videos/valores_intro.mp4")
        log.warning("   Colócalo en: /static/template/videos/valores_intro.mp4")
        return

    lesson = Lesson.objects.create(
        module_content=module,
        title="Video de Valores",
        lesson_type="Video",
        description="Mira el video antes de continuar al memorama.",
        video_url=""  # vacío porque usaremos resource
    )

    # Guardar mp4 en media/ (FileField resource)
    lesson.resource.save(mp4_name, ContentFile(mp4_bytes), save=True)

    log.info("✅ Curso de inducción listo: config + módulo + lección con MP4 (resource).")
