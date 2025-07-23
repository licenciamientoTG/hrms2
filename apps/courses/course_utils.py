from django.utils.timezone import now
from datetime import timedelta
from django.db.models import Q
from apps.courses.models import CourseHeader, CourseConfig, EnrolledCourse, QuizAttempt, Quiz
from django.contrib.auth.models import User


def check_and_archive_courses():
    cursos = CourseHeader.objects.filter(config__is_archived=True, archived_at__isnull=True)

    for curso in cursos:
        config = getattr(curso, 'config', None)
        if not config:
            continue

        # Condición 1: deadline vencido
        if config.deadline:
            deadline_date = curso.created_at + timedelta(days=config.deadline)
            if deadline_date.date() < now().date():
                curso.archived_at = now()
                curso.save()
                continue

        # Condición 2: todos los asignados agotaron sus intentos
        assigned_user_ids = set()

        if config.audience == "all_users":
            assigned_user_ids |= set(
                User.objects.filter(is_staff=False, is_superuser=False).values_list('id', flat=True)
            )

        assignments = curso.assignments.all()
        for assignment in assignments:
            if assignment.assignment_type == 'specific_users':
                assigned_user_ids |= set(assignment.users.values_list('id', flat=True))
            elif assignment.assignment_type == 'by_department':
                by_dept_users = User.objects.filter(
                    Q(employee__department__in=assignment.departments.all()) |
                    Q(employee__job_position__in=assignment.positions.all()) |
                    Q(employee__station__in=assignment.locations.all())
                ).values_list('id', flat=True)
                assigned_user_ids |= set(by_dept_users)

        enrolled_user_ids = set(
            EnrolledCourse.objects.filter(course=curso).values_list('user_id', flat=True)
        )
        assigned_user_ids |= enrolled_user_ids

        assigned_user_ids = set(
            User.objects.filter(
                id__in=assigned_user_ids,
                is_staff=False,
                is_superuser=False
            ).values_list('id', flat=True)
        )

        if not assigned_user_ids:
            continue

        # 🔁 Obtener max_attempts desde QuizConfig (relacionado con Quiz)
        quiz = Quiz.objects.filter(course_header=curso).first()
        if not quiz or not hasattr(quiz, 'config'):
            continue  # si no hay config no se puede evaluar intentos

        max_attempts = quiz.config.max_attempts or 1

        agotaron = 0
        for uid in assigned_user_ids:
            intentos = QuizAttempt.objects.filter(course=curso, user_id=uid).count()
            if intentos >= max_attempts:
                agotaron += 1

        if agotaron == len(assigned_user_ids):
            curso.archived_at = now()
            curso.save()