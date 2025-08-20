from django.forms import formset_factory
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404, render, redirect
from django.core.files.storage import DefaultStorage
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_protect
from django.core.exceptions import ObjectDoesNotExist
from pyexpat.errors import messages
from formtools.wizard.views import SessionWizardView
from django.views.decorators.http import require_POST
from apps.employee.models import Employee, JobCategory, JobPosition
from apps.location.models import Location
from .forms import CourseHeaderForm, CourseConfigForm, ModuleContentForm, LessonForm, QuizForm
from .models import CourseAssignment, CourseHeader, CourseConfig, EnrolledCourse, ModuleContent, Lesson, CourseCategory,  LessonAttachment, Quiz, Question, Answer, QuizAttempt, QuizConfig, CourseSubCategoryRelation
import json
from datetime import timedelta, datetime, timezone, date
from departments.models import Department
from django.contrib.auth.models import User
from django.contrib.admin.views.decorators import staff_member_required
from django.forms import modelformset_factory
from django.shortcuts import redirect
from django.utils import timezone
from django.db.models import Prefetch, Count, Avg, Q, Max
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import letter
from django.conf import settings
from io import BytesIO
from django.core.files.base import ContentFile
from .models import CourseCertificate
from django.core.files import File
from django.utils.text import slugify
from reportlab.lib.utils import ImageReader
from PyPDF2 import PdfReader, PdfWriter
from apps.courses.course_utils import check_and_archive_courses
import os
import csv
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from apps.notifications.models import Notification

LessonFormSet = formset_factory(LessonForm, extra=1)  # Permite agregar varias lecciones

@login_required
def get_employees_with_user(request):
    employees = Employee.objects.filter(user__isnull=False, user__is_active=True)
    data = [{
        'id': emp.user.id,
        'name': f"{emp.first_name} {emp.last_name}",
        'department': emp.department.id if emp.department else None,
        'job_position': emp.job_position.id if emp.job_position else None,
        'station': emp.station.id if emp.station else None,
    } for emp in employees]
    return JsonResponse({'employees': data})

@login_required
def course_wizard(request):
    if not request.user.is_superuser:
        return redirect('user_courses')
 
    check_and_archive_courses()

    employees = []
 
    departments = Department.objects.all()
    job_positions = JobPosition.objects.all()
    locations = Location.objects.all()
    template_name = "courses/admin/admin_courses.html"

    if request.method == "POST":
        course_form = CourseHeaderForm(request.POST, request.FILES)
        config_form = CourseConfigForm(request.POST)
        module_formset = formset_factory(ModuleContentForm, extra=1)(request.POST)
        lesson_formset = LessonFormSet(request.POST, request.FILES)

        if course_form.is_valid():
            course = course_form.save(commit=False)
            course.user = request.user
            course.save()
            request.session['course_id'] = course.id
            return redirect('course_wizard')

        elif config_form.is_valid():
            config = config_form.save(commit=False)
            config.course = course  # ✅
            config.save()
            return redirect('course_wizard')

        elif module_formset.is_valid():
            for form in module_formset:
                if form.cleaned_data:
                    module = form.save(commit=False)
                    module.course_header_id = request.session.get('course_id')
                    module.save()
            return redirect('course_wizard')

        elif lesson_formset.is_valid():
            for form in lesson_formset:
                if form.cleaned_data:
                    form.save()
            return redirect('course_wizard')

    else:
        course_form = CourseHeaderForm()
        config_form = CourseConfigForm()
        module_formset = formset_factory(ModuleContentForm, extra=1)()
        lesson_formset = LessonFormSet()

    today = datetime.now().date()

    estado = request.GET.get("estado")
    if estado == "archivado":
        courses = CourseHeader.objects.filter(archived_at__isnull=False)
    else:
        courses = CourseHeader.objects.all()

    totalcursos = courses.count()
    archived_courses_count = CourseHeader.objects.filter(archived_at__isnull=False).count()
    inactive_courses_count = 0
    in_progress_courses_count = 0
    completed_courses = []

    for course in courses:
        config = getattr(course, 'config', None)

        if config and config.deadline:
            deadline_date = course.created_at + timedelta(days=config.deadline)
            course.deadline_date = deadline_date.date()
            if course.deadline_date < today:
                inactive_courses_count += 1
            else:
                in_progress_courses_count += 1
        else:
            course.deadline_date = None
            in_progress_courses_count += 1

        # ✅ Calcular usuarios asignados correctamente
        assigned_user_ids = set()

        if config and config.audience == "all_users":
            assigned_user_ids |= set(
                User.objects.filter(is_staff=False, is_superuser=False).values_list('id', flat=True)
            )

        assignments = CourseAssignment.objects.filter(course=course)
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

        # Siempre suma inscritos manuales
        enrolled_user_ids = set(
            EnrolledCourse.objects.filter(course=course).values_list('user_id', flat=True)
        )

        assigned_user_ids |= enrolled_user_ids

        # Filtra usuarios reales
        assigned_user_ids = set(
            User.objects.filter(
                id__in=assigned_user_ids,
                is_staff=False,
                is_superuser=False
            ).values_list('id', flat=True)
        )

        total_users = len(assigned_user_ids)
        course.assigned_count = total_users  


        if total_users > 0:
            quiz = Quiz.objects.filter(course_header=course).first()
            if quiz:
                passed_count = QuizAttempt.objects.filter(
                    course=course, passed=True, user_id__in=assigned_user_ids
                ).values('user').distinct().count()
                if passed_count == total_users:
                    completed_courses.append(course)
            else:
                all_completed = True
                for uid in assigned_user_ids:
                    enrolled = EnrolledCourse.objects.filter(course=course, user_id=uid).first()
                    if not enrolled or enrolled.progress < 100:
                        all_completed = False
                        break
                if all_completed:
                    completed_courses.append(course)

    completed_course_ids_admin = [c.id for c in completed_courses]
    completed_courses_count = len(completed_course_ids_admin)

    return render(request, template_name, {
        'course_form': course_form,
        'config_form': config_form,
        'module_formset': module_formset,
        'lesson_formset': lesson_formset,
        'quiz_form': QuizForm(),
        'totalcursos': totalcursos,
        'courses': courses,
        'courses_config': CourseConfig.objects.all(),
        'today': today,
        'inactive_courses_count': inactive_courses_count,
        'in_progress_courses_count': in_progress_courses_count,
        'completed_courses_count': completed_courses_count,
        'employees': employees,
        'departments': departments,
        'job_positions': job_positions,
        'locations': locations,
        'assigned_courses_count': 0,
        'assigned_course_ids': [],
        'completed_course_ids_admin': completed_course_ids_admin,
        'archived_courses_count': archived_courses_count,
    })


@login_required
def visual_course_wizard(request):
    check_and_archive_courses()
    course_form = CourseHeaderForm()
    config_form = CourseConfigForm()
    module_formset = formset_factory(ModuleContentForm, extra=1)()
    lesson_formset = LessonFormSet()

    totalcursos = CourseHeader.objects.all().count()
    courses = CourseHeader.objects.filter(archived_at__isnull=True)

    courses_config = CourseConfig.objects.all()
    today = datetime.now().date()

    inactive_courses_count = 0
    in_progress_courses_count = 0
    course = None

    for course in courses:
        if hasattr(course, 'config'):
            deadline_date = course.created_at + timedelta(days=course.config.deadline)
            deadline_date = deadline_date.date()
            course.deadline_date = deadline_date

            if deadline_date <= today:
                inactive_courses_count += 1
            elif deadline_date >= today:
                in_progress_courses_count += 1
        else:
            course.deadline_date = None

    employees = Employee.objects.filter(is_active=True, user__isnull=False)
    departments = Department.objects.all()
    job_positions = JobPosition.objects.all()
    locations = Location.objects.all()

    return render(request, 'courses/admin/wizard_form.html', {
        'course_form': course_form,
        'config_form': config_form,
        'module_formset': module_formset,
        'lesson_formset': lesson_formset,
        'quiz_form': QuizForm(),
        'totalcursos': totalcursos,
        'courses': courses,
        'courses_config': courses_config,
        'today': today,
        'inactive_courses_count': inactive_courses_count,
        'in_progress_courses_count': in_progress_courses_count,
        'employees': employees,
        'departments': departments,
        'job_positions': job_positions,
        'locations': locations,
        "course": course,
    })

@login_required
def save_course(request):
    if request.method == 'POST':
        try:
            # Obtener los datos del formulario
            local_storage_data = request.POST.get("localStorageData", "{}")
            data = json.loads(local_storage_data)

            step1 = data.get("step1", {})
            step2 = data.get("step2", {})
            modules = data.get("modules", [])


            return JsonResponse({"status": "success", "message": "Curso guardado correctamente.", "data": data})

        except json.JSONDecodeError:
            return JsonResponse({"status": "error", "message": "Error al procesar los datos."}, status=400)

    return JsonResponse({"status": "error", "message": "Método no permitido."}, status=405)




@user_passes_test(lambda u: u.is_superuser)
def save_course_ajax(request):
    if request.method == 'POST':
        try:
            # 🔹 1. Obtener los datos desde `request.POST` y `request.FILES`
            step1_raw = request.POST.get("step1", "{}")
            step2_raw = request.POST.get("step2", "{}")
            modules_raw = request.POST.get("modules", "[]")
            portrait_file = request.FILES.get("portrait")
            quiz_questions_raw = request.POST.get("quiz_questions", "[]")

            step1_data = json.loads(step1_raw)
            step2_data = json.loads(step2_raw)
            modules_data = json.loads(modules_raw)

            ALLOWED_EXTENSIONS = [".pdf", ".mp4", ".jpg", ".jpeg", ".png", ".gif", ".webp"]

            
            # 🔹 2. Validaciones básicas
            required_fields_step1 = ["title", "description", "duration", "category"]
            missing_fields_step1 = [field for field in required_fields_step1 if not step1_data.get(field)]
            if missing_fields_step1:
                return JsonResponse({"status": "error", "message": f"Faltan campos en step1: {missing_fields_step1}"}, status=400)

            required_fields_step2 = ["course_type", "deadline", "audience", "certification", "requires_signature"]
            missing_fields_step2 = [field for field in required_fields_step2 if not step2_data.get(field)]
            if missing_fields_step2:
                return JsonResponse({"status": "error", "message": f"Faltan campos en step2: {missing_fields_step2}"}, status=400)

            try:
                deadline = int(step2_data.get("deadline", 0))
                if deadline < 0:
                    return JsonResponse({"status": "error", "message": "El plazo debe ser mayor o igual a 0."}, status=400)
            except ValueError:
                return JsonResponse({"status": "error", "message": "El plazo debe ser un número válido."}, status=400)

            # 🔹 3. Validar categoría
            category_id = step1_data.get("category")
            try:
                category = CourseCategory.objects.get(id=category_id)
            except ObjectDoesNotExist:
                return JsonResponse({"status": "error", "message": "La categoría no existe."}, status=400)

            # 🔒 Validar tipo MIME real
            if portrait_file:
                allowed_mime = ["image/jpeg", "image/png", "image/webp", "image/gif"]
                if portrait_file.content_type not in allowed_mime:
                    return JsonResponse({
                        "status": "error",
                        "message": "Solo se permiten imágenes (JPG, PNG, WEBP, GIF) como portada."
                }, status=400)


            # 🔹 4. Guardar CourseHeader (con imagen)
            course = CourseHeader.objects.create(
                title=step1_data.get("title"),
                description=step1_data.get("description"),
                duration=step1_data.get("duration"),
                user=request.user,
                category=category,
                portrait=portrait_file  # <<✅ Aquí se guarda la imagen
            )

            subcats = json.loads(request.POST.get("sub_categories","[]"))
            for subcat_id in subcats:
                CourseSubCategoryRelation.objects.create(
                    course=course,
                    subcategory_id=subcat_id
                )

            is_archived = step2_data.get("is_archived") in ["true", "on", True, "1"]

            # 🔹 5. Guardar CourseConfig
            CourseConfig.objects.create(
                course=course,
                course_type=step2_data.get("course_type"),
                sequential=step2_data.get("sequential") == "on",
                deadline=deadline,
                audience=step2_data.get("audience"),
                certification=step2_data.get("certification") == "on",
                requires_signature=step2_data.get("requires_signature") == "on",
                is_archived=is_archived 
            )

            # 🔹 5.1 Crear Quiz para el curso
            quiz = Quiz.objects.create(
                course_header=course,
                title="Cuestionario del curso",
                description="Generado automáticamente"
            )

            passing_score = int(request.POST.get("min_score", 60))
            max_attempts = request.POST.get("max_attempts") or None
            time_limit_minutes = request.POST.get("time_limit") or None
            show_correct = request.POST.get("show_correct_answers") in ["true", "on", True]


            QuizConfig.objects.update_or_create(
                quiz=quiz,
                defaults={
                    "passing_score": passing_score,
                    "max_attempts": int(max_attempts) if max_attempts else None,
                    "time_limit_minutes": int(time_limit_minutes) if time_limit_minutes else None,
                    "show_correct_answers": show_correct
                }
            )

            # 🔹 5.2 Guardar preguntas del cuestionario desde localStorage
            try:
                quiz_questions = json.loads(quiz_questions_raw)
            except json.JSONDecodeError:
                quiz_questions = []

            for q in quiz_questions:
                question = Question.objects.create(
                    quiz=quiz,
                    question_type=q.get("question_type"),
                    question_text=q.get("question_text"),
                    explanation=q.get("explanation", ""),
                    score=q.get("score", 1),
                    single_answer=q.get("single_answer", "") if q.get("question_type") == "Texto" else None
                )

                for answer in q.get("answers", []):
                    Answer.objects.create(
                        question=question,
                        answer_text=answer.get("text"),
                        is_correct=answer.get("is_correct", False)
                    )


            # 🔹 6. Guardar módulos y lecciones
            if not isinstance(modules_data, list):
                return JsonResponse({"status": "error", "message": "Los módulos deben estar en una lista."}, status=400)

            for module in modules_data:
                if not module.get("title") or not module.get("description"):
                    return JsonResponse({"status": "error", "message": "Cada módulo debe tener título y descripción."}, status=400)

                new_module = ModuleContent.objects.create(
                    course_header=course,
                    title=module.get("title"),
                    description=module.get("description")
                )

                # 🔁 Guardar las lecciones del módulo actual aquí dentro
                for lesson in module.get("lessons", []):
                    if not lesson.get("title") or not lesson.get("type") or not lesson.get("description"):
                        return JsonResponse({"status": "error", "message": "Cada lección debe tener título, tipo y descripción."}, status=400)

                    resource_index = lesson.get("resource_index")
                    resource_file = request.FILES.get(f"lesson_resource_{resource_index}")

                    # ✅ Validación del tipo de archivo
                    if resource_file:
                        ext = os.path.splitext(resource_file.name)[1].lower()
                        if ext not in ALLOWED_EXTENSIONS:
                            return JsonResponse({
                                "status": "error",
                                "message": f"El archivo '{resource_file.name}' no está permitido. Solo se aceptan PDF, MP4 e imágenes (JPG, PNG, etc.)."
                            }, status=400)

                        
                    Lesson.objects.create(
                        module_content=new_module,
                        title=lesson.get("title"),
                        lesson_type=lesson.get("type"),
                        description=lesson.get("description"),
                        video_url=lesson.get("video_url"),
                        resource=resource_file  # ✅ Esto guardará el archivo en media/lessons/
                    )

            return JsonResponse({
                "status": "success",
                "message": "Curso guardado correctamente.",
                "course_id": course.id  # 👈 Agrega esto
            })


        except json.JSONDecodeError:
            return JsonResponse({"status": "error", "message": "Error al procesar los datos JSON."}, status=400)

    return JsonResponse({"status": "error", "message": "Método no permitido."}, status=405)

@csrf_protect
@login_required
def process_assignments(request):
    # Si la peticion es de tipo POST
    if request.method == 'POST':
        return HttpResponse("Procesar asignaciones")
    return HttpResponseBadRequest("Método no permitido")


#en esta vista estamos mandando los datos a segment_users.html
@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def user_segmentation_view(request, course_id):
    course = get_object_or_404(CourseHeader, id=course_id)
    employees = [] 
    departments = Department.objects.all()
    job_positions = JobPosition.objects.all()
    locations = Location.objects.all()


    return render(request, 'courses/admin/segment_users.html', {
        'course': course,
        'employees': employees,
        'departments': departments,
        'job_positions': job_positions,
        'locations': locations,
    })

@csrf_exempt
@user_passes_test(lambda u: u.is_superuser)
def run_assignments(request, course_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            course = get_object_or_404(CourseHeader, id=course_id)

            all_users = data.get('allUsers', False)
            selected_users = data.get('users', [])
            selected_departments = data.get('departments', [])
            selected_positions = data.get('positions', [])
            selected_locations = data.get('locations', [])

            if all_users:
                assignment_type = 'all_users'
            else:
                assignment_type = 'specific_users'

            assignment = CourseAssignment.objects.create(
                course=course,
                assignment_type=assignment_type,
                assigned_by=request.user
            )

            if selected_users:
                users = User.objects.filter(id__in=selected_users)
                assignment.users.set(users)
                for user in users:
                    EnrolledCourse.objects.get_or_create(
                        user=user,
                        course=course,
                        defaults={'status': 'pending', 'progress': 0.0}
                    )

            if selected_departments:
                departments = Department.objects.filter(id__in=selected_departments)
                assignment.departments.set(departments)

            if selected_positions:
                positions = JobPosition.objects.filter(id__in=selected_positions)
                assignment.positions.set(positions)

            if selected_locations:
                locations = Location.objects.filter(id__in=selected_locations)
                assignment.locations.set(locations)

            return JsonResponse({
                'success': True,
                'message': 'Asignación guardada correctamente.',
                'redirect_url': '/courses/course_wizard/',
                'has_users': True
            })

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

@login_required
def view_course_content(request, course_id):
    course = get_object_or_404(CourseHeader, id=course_id)
    enrolled = EnrolledCourse.objects.filter(course=course, user=request.user).first()
    course_quiz = Quiz.objects.filter(course_header=course).first()
    modules = ModuleContent.objects.filter(course_header=course).order_by("created_at")

    # Lógica para calcular los intentos restantes
    attempts_left = None
    is_passed = False

    if course_quiz and hasattr(course_quiz, 'config') and course_quiz.config.max_attempts is not None:
        total_attempts = QuizAttempt.objects.filter(user=request.user, quiz=course_quiz).count()
        attempts_left = max(0, course_quiz.config.max_attempts - total_attempts)
        is_passed = QuizAttempt.objects.filter(user=request.user, quiz=course_quiz, passed=True).exists()
    
    viewed_lessons = []
    if enrolled and enrolled.notes:
        viewed_lessons = enrolled.notes.split(",")

    cert = CourseCertificate.objects.filter(user=request.user, course=course).first()

    return render(request, 'courses/user/view_course.html', {
        'course': course,
        'modules': modules,
        'enrolled': enrolled,
        'course_quiz': course_quiz,
        'attempts_left': attempts_left,
        'is_passed': is_passed,
        'request': request,
        'viewed_lessons': viewed_lessons,
        'cert': cert,
    })

@user_passes_test(lambda u: u.is_superuser)
def admin_course_stats(request, course_id):
    course = get_object_or_404(CourseHeader, id=course_id)
    config = CourseConfig.objects.filter(course=course).first()
    assignments = CourseAssignment.objects.filter(course=course)

    # 🛡️ Por defecto: ningún usuario
    users = User.objects.none()

  # Evaluar si el curso aplica para todos los usuarios desde config o assignment
    is_all_users = (
        (config and config.audience == "all_users") or
        assignments.filter(assignment_type='all_users').exists()
    )

    if is_all_users:
        # Incluir a todos los usuarios normales
        users = User.objects.filter(is_staff=False, is_superuser=False)

    else:
        # Acumular usuarios segmentados
        user_ids = set()

        for assignment in assignments:
            if assignment.assignment_type == "specific_users":
                user_ids.update(assignment.users.values_list('id', flat=True))

            elif assignment.assignment_type == "by_department":
                user_ids.update(User.objects.filter(
                    employee__department__in=assignment.departments.all()
                ).values_list('id', flat=True))

                user_ids.update(User.objects.filter(
                    employee__job_position__in=assignment.positions.all()
                ).values_list('id', flat=True))

                user_ids.update(User.objects.filter(
                    employee__station__in=assignment.locations.all()
                ).values_list('id', flat=True))

        users = User.objects.filter(id__in=user_ids, is_staff=False, is_superuser=False)

    total_users = users.count()

    # Obtener intentos de cuestionario
    quiz = Quiz.objects.filter(course_header=course).first()
    quiz_attempts = QuizAttempt.objects.filter(course=course) if quiz else QuizAttempt.objects.none()

    # Mapa de intentos por usuario
    attempt_map = {}
    if quiz:
        for a in quiz_attempts.values('user_id').annotate(count=Count('id'), last_score=Max('percentage')):
            uid = a['user_id']
            attempt_map[uid] = {
                'count': a['count'],
                'last_score': a['last_score'],
                'passed': quiz_attempts.filter(user_id=uid, passed=True).exists()
            }

    approved_users = quiz_attempts.filter(passed=True).values('user').distinct().count()
    avg_attempts = quiz_attempts.values('user').annotate(n=Count('id')).aggregate(avg=Avg('n'))['avg'] or 0

    user_progress = []
    for user in users:
        data = attempt_map.get(user.id, {})
        user_progress.append({
            'user': user,
            'employee_name': user.get_full_name(),
            'progress': 0,
            'attempts': data.get('count', 0),
            'last_score': round(data.get('last_score', 0), 1),
            'passed': data.get('passed', False),
        })

    return render(request, 'courses/admin/admin_course_stats.html', {
        'course': course,
        'total_users': total_users,
        'completed_users': quiz_attempts.values('user').distinct().count(),
        'approved_users': approved_users,
        'avg_attempts': round(avg_attempts, 1),
        'user_progress': user_progress,
    })
    
@user_passes_test(lambda u: u.is_superuser)
def admin_course_edit(request, course_id):
    course = get_object_or_404(CourseHeader, id=course_id)
    config = get_object_or_404(CourseConfig, course=course)
    modules = ModuleContent.objects.filter(course_header=course).order_by("created_at")
    ModuleFormSet = modelformset_factory(ModuleContent, form=ModuleContentForm, extra=0)

    # Obtener quiz y config si existen
    quiz = Quiz.objects.filter(course_header=course).first()
    quiz_config = QuizConfig.objects.filter(quiz=quiz).first() if quiz else None

    if request.method == "POST":
        course_form = CourseHeaderForm(request.POST, request.FILES, instance=course)
        config_form = CourseConfigForm(request.POST, instance=config)
        module_formset = ModuleFormSet(request.POST, queryset=modules)

        if course_form.is_valid() and config_form.is_valid() and module_formset.is_valid():
            course = course_form.save(commit=False)
            if not request.FILES.get('portrait'):
                course.portrait = course_form.instance.portrait
            course.save()

            # Guardar subcategorías
            subcats = course_form.cleaned_data.get('sub_categories')
            CourseSubCategoryRelation.objects.filter(course=course).delete()
            for subcat in subcats:
                CourseSubCategoryRelation.objects.create(course=course, subcategory=subcat)

            # ✅ Fix: asignar el curso manualmente antes de guardar
            config = config_form.save(commit=False)
            config.course = course
            config.save()

            modules_saved = module_formset.save(commit=False)
            for module in modules_saved:
                module.course_header = course
                module.save()

            if quiz and quiz_config:
                quiz_config.passing_score = request.POST.get("passing_score") or 0
                quiz_config.max_attempts = request.POST.get("max_attempts") or None
                quiz_config.time_limit_minutes = request.POST.get("time_limit_minutes") or None
                quiz_config.show_correct_answers = bool(request.POST.get("show_correct_answers"))
                quiz_config.save()

            return redirect('course_wizard')

        else:
            print("Errores en course_form:", course_form.errors)
            print("Errores en config_form:", config_form.errors)
            print("Errores en module_formset:", module_formset.errors)

    else:
        course_form = CourseHeaderForm(instance=course)
        config_form = CourseConfigForm(instance=config)
        module_formset = ModuleFormSet(queryset=modules)

    return render(request, 'courses/admin/admin_course_edit.html', {
        'course_form': course_form,
        'config_form': config_form,
        'module_formset': module_formset,
        'course': course,
        'modules': modules,
        'quiz_config': quiz_config,
    })

@login_required
def user_courses(request):
    check_and_archive_courses()
    today = timezone.now().date()

    # 1) Cursos asignados directamente al usuario
    enrolled_qs = (
        EnrolledCourse.objects
        .filter(user=request.user, course__archived_at__isnull=True)
        .select_related('course', 'course__config')
    )
    assigned_courses = [e.course for e in enrolled_qs]

    # 2) Cursos públicos (audience="all_users")
    public_courses = CourseHeader.objects.filter(
        config__audience="all_users",
        archived_at__isnull=True 
    )

    # 3) Cursos por tipo de asignación all_users
    assigned_by_type = CourseAssignment.objects.filter(
        assignment_type="all_users"
    ).values_list("course_id", flat=True)
    type_based = CourseHeader.objects.filter(
        id__in=assigned_by_type, 
        archived_at__isnull=True 
    )

    # 4) Unión sin duplicados
    all_courses = list(
        set(assigned_courses) |
        set(public_courses)   |
        set(type_based)
    )

    # 5) Simular enrollments faltantes
    fake = []
    enrolled_ids = {e.course.id for e in enrolled_qs}
    for course in all_courses:
        # calculamos deadline_date si existe config.deadline
        if getattr(course, 'config', None) and course.config.deadline is not None:
            course.deadline_date = (
                course.created_at + timedelta(days=course.config.deadline)
            ).date()
        else:
            course.deadline_date = None

        if course.id not in enrolled_ids:
            fe = EnrolledCourse(course=course, user=request.user, progress=0)
            fe.notes = ''  # para no romper al leer .notes
            fake.append(fe)

    # 6) Combinamos reales y simulados
    all_enrollments = list(enrolled_qs) + fake

    # 7) Lógica de completado
    completed_course_ids = []
    for enroll in all_enrollments:
        course = enroll.course

        # a) Número total de lecciones
        total_lessons = Lesson.objects.filter(
            module_content__course_header=course
        ).count()

        # b) Número de preguntas del quiz “real”
        question_count = Question.objects.filter(
            quiz__course_header=course
        ).count()

        if question_count > 0:
            # Caso 1: quiz con preguntas → solo si pasó el quiz
            if QuizAttempt.objects.filter(
                user=request.user,
                quiz__course_header=course,
                passed=True
            ).exists():
                completed_course_ids.append(course.id)

        elif total_lessons > 0:
            # Caso 2: sin quiz real pero con lecciones → todas vistas
            viewed = [
                v.strip() for v in enroll.notes.split(',') if v.strip()
            ]
            if len(viewed) >= total_lessons:
                completed_course_ids.append(course.id)

        else:
            # Caso 3: ni quiz real ni lecciones → completar automáticamente
            completed_course_ids.append(course.id)

    # 8) Estadísticas de asignación
    assigned_ids = {c.id for c in assigned_courses}
    assigned_count = len(assigned_ids)

    pending_courses_count = len(all_courses) - len(completed_course_ids)


    # 9) Renderizar
    return render(request, 'courses/user/wizard_form_user.html', {
        'courses': all_courses,
        'enrolled_courses': all_enrollments,
        'today': today,
        'totalcursos': len(all_courses),
        'in_progress_courses_count': sum(
            1 for c in all_courses
            if c.deadline_date is None or c.deadline_date > today
        ),
        'inactive_courses_count': sum(
            1 for c in all_courses
            if c.deadline_date and c.deadline_date <= today
        ),
        'completed_course_ids': completed_course_ids,
        'assigned_courses_count': assigned_count,
        'assigned_course_ids': assigned_ids,
        'completed_courses_count': len(completed_course_ids),
        'pending_courses_count': pending_courses_count,
    })

@staff_member_required
def admin_courses(request):
    if request.user.is_superuser:
        # Si es un administrador, obtener todos los cursos
        courses = CourseHeader.objects.all()
        template_name = "courses/admin/admin_courses.html"
    else:
        # Si no es admin, obtener los cursos asignados al usuario
        enrolled_courses = EnrolledCourse.objects.filter(user=request.user)
        courses = [enrolled_course.course for enrolled_course in enrolled_courses]
        template_name = "courses/user/my_courses.html"
        
    totalcursos = len(courses)
    today = datetime.now().date()

    # Filtra los cursos para ver si están activos o inactivos
    inactive_courses_count = 0
    in_progress_courses_count = 0
    for course in courses:
        if hasattr(course, 'config'):
            deadline_date = course.created_at + timedelta(days=course.config.deadline)
            deadline_date = deadline_date.date()
            course.deadline_date = deadline_date

            if deadline_date <= today:
                inactive_courses_count += 1  # curso expirado
            elif deadline_date >= today:
                in_progress_courses_count += 1  # curso activo
        else:
            course.deadline_date = None

    return render(request, template_name, {
        'courses': courses,
        'totalcursos': totalcursos,
        'inactive_courses_count': inactive_courses_count,
        'in_progress_courses_count': in_progress_courses_count,
        'today': today,
    })

@csrf_protect
@login_required
def guardar_pregunta(request):
    if request.method == 'POST':
        try:
            course_id = request.POST.get("course_id")
            question_text = request.POST.get("question_text")
            question_type = request.POST.get("question_type")
            explanation = request.POST.get("explanation", "")
            question_score = int(request.POST.get("question_score", 1))  # valor por defecto = 1


            # Validación de curso
            course = get_object_or_404(CourseHeader, id=course_id)

            # Obtener o crear el quiz automáticamente
            quiz = get_object_or_404(Quiz, course_header=course)


            # 🔹 5.2 Guardar preguntas desde el localStorage
            quiz_questions_raw = request.POST.get("quiz_questions", "[]")
            quiz_questions = json.loads(quiz_questions_raw)

            for q in quiz_questions:
                question = Question.objects.create(
                    quiz=quiz,
                    question_text=q.get("question_text"),
                    question_type=q.get("question_type"),
                    explanation=q.get("explanation", ""),
                    score=q.get("score", 1)
                )

                for ans in q.get("answers", []):
                    Answer.objects.create(
                        question=question,
                        answer_text=ans.get("text"),
                        is_correct=ans.get("is_correct", False)
                    )



            # Procesar respuestas dinámicamente
            answer_prefix = "answers["
            answer_map = {}

            for key in request.POST:
                if key.startswith("answers["):
                    # Extrae índice y campo
                    import re
                    match = re.match(r"answers\[(\d+)\]\[(text|correct)\]", key)
                    if match:
                        idx, field = match.groups()
                        if idx not in answer_map:
                            answer_map[idx] = {}
                        answer_map[idx][field] = request.POST.get(key)

            # Crear objetos Answer
            for answer in answer_map.values():
                text = answer.get("text")
                is_correct = answer.get("correct") in ["true", "True", "1", "on"]
                if text:
                    Answer.objects.create(
                        question=question,
                        answer_text=text,
                        is_correct=is_correct
                    )

            return JsonResponse({"success": True, "message": "Pregunta y respuestas guardadas."})

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return JsonResponse({"success": False, "error": str(e)}, status=500)

    return JsonResponse({"success": False, "message": "Método no permitido"}, status=405)

@staff_member_required
@csrf_protect
def eliminar_pregunta(request, question_id):
    if request.method == 'POST':
        try:
            question = get_object_or_404(Question, id=question_id)
            course_id = question.quiz.course_header.id
            question.delete()
            return JsonResponse({'success': True, 'course_id': course_id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

@login_required
def obtener_preguntas_curso(request, course_id):
    try:
        quiz = Quiz.objects.filter(course_header_id=course_id).first()
        if not quiz:
            return JsonResponse({"questions": []})
        
        preguntas = []
        for q in quiz.question_set.all():
            respuestas = list(q.answer_set.values("answer_text", "is_correct"))
            preguntas.append({
                "id": q.id, 
                "question_text": q.question_text,
                "question_type": q.question_type,
                "answers": [
                    {"text": r["answer_text"], "is_correct": r["is_correct"]} for r in respuestas
                ],
                "explanation": q.single_answer if q.question_type == "Texto" else ""
            })

        return JsonResponse({"questions": preguntas})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_protect
@login_required
def submit_course_quiz(request, course_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    try:
        course = CourseHeader.objects.get(id=course_id)
        quiz = Quiz.objects.get(course_header=course)
        questions = quiz.question_set.all()

        # Validar intentos
        config = quiz.config
        if config and config.max_attempts:
            existing_attempts = QuizAttempt.objects.filter(user=request.user, quiz=quiz).count()
            if existing_attempts >= config.max_attempts:
                return JsonResponse({
                    'success': False,
                    'message': f'Has alcanzado el máximo de {config.max_attempts} intentos permitidos.'
                }, status=403)

        total_questions = questions.count()
        correct_count = 0

        for question in questions:
            if question.question_type == "Respuesta múltiple":
                field_name = f"question_{question.id}[]"
                user_answers = request.POST.getlist(field_name)
            else:
                field_name = f"question_{question.id}"
                user_answer = request.POST.get(field_name)
                user_answers = [user_answer] if user_answer else []

            user_answers_set = set(map(str, user_answers))
            correct_answers = question.answer_set.filter(is_correct=True).values_list('id', flat=True)
            correct_answers_set = set(map(str, correct_answers))

            if not user_answers_set:
                continue

            if question.question_type == "Respuesta múltiple":
                if user_answers_set & correct_answers_set:
                    correct_count += 1
            elif question.question_type == "Texto":
                continue  # Opcional: puedes agregar lógica de comparación exacta
            else:
                if user_answers_set & correct_answers_set:
                    correct_count += 1

        passing_score = config.passing_score if config else 60
        percentage = (correct_count / total_questions) * 100 if total_questions else 0
        passed = percentage >= passing_score

        # Guardar intento
        QuizAttempt.objects.create(
            user=request.user,
            quiz=quiz,
            course=course,
            score=correct_count,
            percentage=percentage,
            passed=passed
        )

        # Si aprobó, el curso tiene certificación activa y no tiene certificado aún, generarlo
        if (
            passed 
            and hasattr(course, 'config') 
            and course.config.certification  # <- usa tu booleano directamente
            and not CourseCertificate.objects.filter(user=request.user, course=course).exists()
        ):
            try:
                generar_y_guardar_certificado(request.user, course)
                print("✅ Certificado generado exitosamente.")
            except Exception as e:
                import traceback
                print("❌ Error al guardar certificado:")
                print(traceback.format_exc())


        return JsonResponse({
            'success': True,
            'score': correct_count,
            'percentage_score': percentage,
            'passed': passed,
            'message': 'Aprobado' if passed else 'Vuelve a intentarlo'
        })

    except CourseHeader.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Curso no encontrado'}, status=404)

    except Exception as e:
        import traceback
        print("⚠️ Error general en submit_course_quiz:")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'message': 'Error interno', 'error': str(e)}, status=500)



@login_required
def unread_course_count(request):
    unread_count = Notification.objects.filter(
        user=request.user,
        read_at__isnull=True,        # <— NOTA: aquí va read_at__isnull
        url__icontains="/courses/"   # ajusta si usas rutas distintas
    ).count()
    return JsonResponse({'unread_count': unread_count})

@require_POST
@login_required
def mark_all_courses_read(request):
    EnrolledCourse.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'success': True})

@login_required
@require_POST
def mark_lesson_complete(request):
    lesson_id = request.POST.get("lesson_id")
    if not lesson_id:
        return JsonResponse({"success": False, "error": "No se envió lesson_id."}, status=400)

    lesson = get_object_or_404(Lesson, pk=lesson_id)
    course = lesson.module_content.course_header

    # 👤 Verifica que el usuario esté inscrito en el curso
    enrolled, created = EnrolledCourse.objects.get_or_create(
        user=request.user,
        course=course,
        defaults={"status": "in_progress"}
    )

    # ✅ Guarda progreso en la sesión o en una tabla real (aquí ejemplo simple: notas JSON)
    if not enrolled.notes:
        enrolled.notes = ""

    # Guardar las lecciones vistas como IDs separados por coma (o usa un JSON, tú decides)
    viewed = set(enrolled.notes.split(",")) if enrolled.notes else set()
    viewed.add(str(lesson_id))
    enrolled.notes = ",".join(viewed)

    # 🧮 Calcula nuevo progreso
    total_lessons = Lesson.objects.filter(module_content__course_header=course).count()
    viewed_count = len(viewed)
    progress = round((viewed_count / total_lessons) * 100, 2) if total_lessons > 0 else 0
    enrolled.progress = progress

    # Si terminó TODO, puedes marcarlo como completado si quieres:
    if progress >= 100 and enrolled.status != "completed":
        enrolled.status = "completed"

    enrolled.save()

    return JsonResponse({"success": True, "progress": progress})
    
#esta vista solo la desbloqueo para ver el certificado sin necesidad de estar generando uno nuevo a cada rato
#hay que activarle su url para poder visitar la vista de como va estructurado el certificado
# def vista_previa_certificado(request):
#     nombre_usuario = request.user.get_full_name()
#     nombre_curso = "Creación de cursos"
#     width, height = 842, 595

#     # 1. Generar overlay de texto
#     buffer = BytesIO()
#     c = canvas.Canvas(buffer, pagesize=(width, height))
#     c.setFont("Helvetica-Bold", 30)
#     c.drawCentredString(580, 260, nombre_usuario)
#     c.setFont("Helvetica-Bold", 17)
#     c.drawCentredString(575, 179, f"{nombre_curso}")
#     c.setFont("Helvetica-Bold",  17)
#     fecha_hoy = date.today().strftime("%d/%m/%Y")
#     c.drawCentredString(780, 140, f"{fecha_hoy}")
#     c.drawCentredString(630, 140, f"0")

#     c.save()
#     buffer.seek(0)

#     # 2. Fusionar con PDF base
#     template_path = os.path.join(
#         settings.BASE_DIR, 'static', 'template', 'img', 'certificates', 'Diploma_TotalGas.pdf'
#     )
#     base_pdf = PdfReader(template_path)
#     overlay_pdf = PdfReader(buffer)
#     writer = PdfWriter()

#     base_page = base_pdf.pages[0]
#     base_page.merge_page(overlay_pdf.pages[0])
#     writer.add_page(base_page)

#     # 3. Guardar archivo final en memoria
#     final_output = BytesIO()
#     writer.write(final_output)
#     final_output.seek(0)

#     # 5. Mostrar al usuario
#     final_output.seek(0)
#     response = HttpResponse(final_output, content_type='application/pdf')
#     response['Content-Disposition'] = 'inline; filename="vista_previa_certificado.pdf"'
#     return response

@login_required
def generar_y_guardar_certificado(usuario, curso):

    width, height = 842, 595
    nombre_usuario = usuario.get_full_name()
    nombre_curso = curso.title

    # 1. Generar overlay de texto
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(580, 260, nombre_usuario)
    c.setFont("Helvetica-Bold", 17)
    c.drawCentredString(575, 179, f"{nombre_curso}")
    c.setFont("Helvetica-Bold",  17)
    fecha_hoy = date.today().strftime("%d/%m/%Y")
    c.drawCentredString(780, 140, f"{fecha_hoy}")
    c.drawCentredString(630, 140, f"{curso.duration} hrs")
    c.save()
    buffer.seek(0)

    # Ruta de tu diploma
    template_path = os.path.join(settings.BASE_DIR, 'static', 'template', 'img', 'certificates', 'Diploma_TotalGas.pdf')
    if not os.path.exists(template_path):
        print("❌ Archivo de plantilla no encontrado:", template_path)
        return None

    base_pdf = PdfReader(template_path)
    overlay_pdf = PdfReader(buffer)

    writer = PdfWriter()
    base_page = base_pdf.pages[0]
    base_page.merge_page(overlay_pdf.pages[0])
    writer.add_page(base_page)

    output = BytesIO()
    writer.write(output)
    output.seek(0)

    # Evitar duplicados
    if CourseCertificate.objects.filter(user=usuario, course=curso).exists():
        print("⚠️ Certificado ya existe para este usuario y curso.")
        return None

    certificado = CourseCertificate.objects.create(user=usuario, course=curso)
    filename = f"certificado_{slugify(usuario.username)}_{slugify(curso.title)}.pdf"
    certificado.file.save(filename, File(output))
    certificado.save()

    return certificado

@login_required
@user_passes_test(lambda u: u.is_superuser)
def course_summary_view(request):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    # Estilos
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    cell_style = ParagraphStyle(name='cell_style', fontSize=9, alignment=TA_LEFT)

    elements.append(Paragraph("Concentrado de Cursos", title_style))
    elements.append(Spacer(1, 12))

    # Encabezados
    data = [
        [
            Paragraph('<b>Curso</b>', cell_style),
            Paragraph('<b>Asignados</b>', cell_style),
            Paragraph('<b>Completaron</b>', cell_style),
            Paragraph('<b>Pendientes</b>', cell_style),
            Paragraph('<b>Fecha</b>', cell_style)
        ]
    ]

    today = datetime.now().date()
    cursos = CourseHeader.objects.all()

    for curso in cursos:
        config = CourseConfig.objects.filter(course=curso).first()
        assignments = CourseAssignment.objects.filter(course=curso)

        assigned_user_ids = set()

        if config and config.audience == "all_users":
            assigned_user_ids |= set(User.objects.filter(is_staff=False, is_superuser=False).values_list('id', flat=True))

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

        enrolled_user_ids = set(EnrolledCourse.objects.filter(course=curso).values_list('user_id', flat=True))
        assigned_user_ids |= enrolled_user_ids

        assigned_user_ids = set(User.objects.filter(
            id__in=assigned_user_ids,
            is_staff=False,
            is_superuser=False
        ).values_list('id', flat=True))

        asignados = len(assigned_user_ids)

        # Completados
        completaron = 0
        quiz = Quiz.objects.filter(course_header=curso).first()
        if quiz:
            completaron = QuizAttempt.objects.filter(course=curso, passed=True, user_id__in=assigned_user_ids).values('user').distinct().count()
        else:
            for uid in assigned_user_ids:
                enrolled = EnrolledCourse.objects.filter(course=curso, user_id=uid).first()
                if enrolled and enrolled.progress == 100:
                    completaron += 1

        pendientes = asignados - completaron
        fecha = curso.created_at.strftime("%d de %B de %Y") if curso.created_at else ""

        data.append([
            Paragraph(curso.title, cell_style),
            str(asignados),
            str(completaron),
            str(pendientes),
            fecha
        ])

    # Tabla con estilo
    table = Table(data, repeatRows=1, colWidths=[230, 60, 60, 60, 90])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)

    return HttpResponse(buffer, content_type='application/pdf')
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    styles = getSampleStyleSheet()

    # Estilo para el título
    elements.append(Paragraph("Concentrado de Cursos", styles['Heading1']))
    elements.append(Spacer(1, 12))

    # Estilo para celdas con texto largo
    wrap_style = ParagraphStyle(
        name="WrapStyle",
        parent=styles["Normal"],
        fontSize=9,
        alignment=TA_LEFT,
        wordWrap='CJK',
        leading=12,
    )

    # Encabezados
    data = [['Curso', 'Asignados', 'Completaron', 'Pendientes', 'Fecha']]

    cursos = CourseHeader.objects.all()
    for curso in cursos:
        asignados = EnrolledCourse.objects.filter(course=curso).count()
        completaron = EnrolledCourse.objects.filter(course=curso, completed_at__isnull=False).count()
        pendientes = asignados - completaron
        fecha = curso.created_at.strftime("%d de %B de %Y") if curso.created_at else ""

        # Usa Paragraph solo para el título
        data.append([
            Paragraph(curso.title, wrap_style),
            asignados,
            completaron,
            pendientes,
            fecha
        ])

    # Ajustes de ancho
    table = Table(data, repeatRows=1, colWidths=[220, 60, 60, 60, 100])

    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#d3d3d3")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)

    return HttpResponse(buffer, content_type='application/pdf')