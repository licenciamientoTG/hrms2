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
from .models import CourseAssignment, CourseHeader, CourseConfig, EnrolledCourse, ModuleContent, Lesson, CourseCategory,  LessonAttachment, Quiz, Question, Answer, QuizAttempt, QuizConfig, QuizAttempt, CourseSubCategoryRelation
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
import os


LessonFormSet = formset_factory(LessonForm, extra=1)  # Permite agregar varias lecciones

@login_required
def course_wizard(request):
    if not request.user.is_superuser:
        return redirect('user_courses')

    employees = Employee.objects.filter(is_active=True)  
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
            config.course_id = request.session.get('course_id')
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
    courses = CourseHeader.objects.all()
    totalcursos = courses.count()

    inactive_courses_count = 0
    in_progress_courses_count = 0
    completed_courses = []

    for course in courses:
        config = getattr(course, 'config', None)

        if config and config.deadline:
            deadline_date = course.created_at + timedelta(days=config.deadline)
            course.deadline_date = deadline_date.date()
            if course.deadline_date <= today:
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
    })


@login_required
def visual_course_wizard(request):
    course_form = CourseHeaderForm()
    config_form = CourseConfigForm()
    module_formset = formset_factory(ModuleContentForm, extra=1)()
    lesson_formset = LessonFormSet()

    totalcursos = CourseHeader.objects.all().count()
    courses = CourseHeader.objects.all()
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

    employees = Employee.objects.filter(is_active=True)
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

            # 🔥 Mostrar en la consola de Django
            print("=== Datos recibidos ===")
            print("Step 1:", step1)
            print("Step 2:", step2)
            print("Modules:", modules)

            return JsonResponse({"status": "success", "message": "Curso guardado correctamente.", "data": data})

        except json.JSONDecodeError:
            return JsonResponse({"status": "error", "message": "Error al procesar los datos."}, status=400)

    return JsonResponse({"status": "error", "message": "Método no permitido."}, status=405)




@login_required
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


            # 🔹 5. Guardar CourseConfig
            CourseConfig.objects.create(
                course=course,
                course_type=step2_data.get("course_type"),
                sequential=step2_data.get("sequential") == "on",
                deadline=deadline,
                audience=step2_data.get("audience"),
                certification=step2_data.get("certification") == "on",
                requires_signature=step2_data.get("requires_signature") == "on"
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

@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def user_segmentation_view(request, course_id):
    course = get_object_or_404(CourseHeader, id=course_id)
    employees = Employee.objects.all()
    departments = Department.objects.all()
    job_positions = JobPosition.objects.all()
    locations = Location.objects.all()

    # Estructurar los datos para el template (CORREGIDO)
    employees_data = {
        'departments': {
            dept.id: [
                f"{emp.first_name} {emp.last_name}"
                for emp in employees.filter(department=dept)
            ]
            for dept in departments
        },
        'positions': {
            pos.id: [
                f"{emp.first_name} {emp.last_name}"
                for emp in employees.filter(job_position=pos)  # Cambiado de position a job_position
            ]
            for pos in job_positions
        },
        'locations': {
            loc.id: [
                f"{emp.first_name} {emp.last_name}"
                for emp in employees.filter(station=loc)  # Cambiado de location a station
            ]
            for loc in locations
        }
    }

    return render(request, 'courses/admin/segment_users.html', {
        'course': course,
        'employees': employees,
        'departments': departments,
        'job_positions': job_positions,
        'locations': locations,
        'employees_data_json': json.dumps(employees_data)
    })

@staff_member_required
@csrf_protect
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
            elif any([selected_departments, selected_positions, selected_locations]):
                assignment_type = 'by_department'
            else:
                assignment_type = 'specific_users'

            assignment = CourseAssignment.objects.create(
                course=course,
                assignment_type=assignment_type,
                assigned_by=request.user
            )

            # ManyToMany
            if selected_users:
                users = User.objects.filter(id__in=selected_users)
                assignment.users.set(users)

                # 🔁 Crear EnrolledCourse para cada usuario
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

@staff_member_required
def admin_course_stats(request, course_id):
    course = get_object_or_404(CourseHeader, id=course_id)
    config = CourseConfig.objects.filter(course=course).first()
    assignments = CourseAssignment.objects.filter(course=course)

    # 🛡️ Por defecto: ningún usuario
    users = User.objects.none()

    if config:
        if config.audience == "all_users":
            # Si el curso está configurado como para todos
            users = User.objects.filter(is_staff=False, is_superuser=False)

        elif config.audience == "segment":
            # Acumular todos los usuarios segmentados
            user_ids = set()

            for assignment in assignments:
                if assignment.assignment_type == "specific_users":
                    user_ids.update(assignment.users.values_list('id', flat=True))

                elif assignment.assignment_type == "by_department":
                    dept_users = User.objects.filter(
                        employee__department__in=assignment.departments.all()
                    ).values_list('id', flat=True)
                    user_ids.update(dept_users)

                    pos_users = User.objects.filter(
                        employee__job_position__in=assignment.positions.all()
                    ).values_list('id', flat=True)
                    user_ids.update(pos_users)

                    loc_users = User.objects.filter(
                        employee__station__in=assignment.locations.all()
                    ).values_list('id', flat=True)
                    user_ids.update(loc_users)

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
    
@staff_member_required
def admin_course_edit(request, course_id):
    course = get_object_or_404(CourseHeader, id=course_id)
    modules = ModuleContent.objects.filter(course_header=course).order_by("created_at")
    
    ModuleFormSet = modelformset_factory(ModuleContent, form=ModuleContentForm, extra=0)
    
    if request.method == "POST":
        course_form = CourseHeaderForm(request.POST, request.FILES, instance=course)
        module_formset = ModuleFormSet(request.POST, queryset=modules)

        if course_form.is_valid() and module_formset.is_valid():
            course_form.save()

            modules_saved = module_formset.save(commit=False)
            for module in modules_saved:
                module.course_header = course  # Asignar el curso al módulo
                module.save()

            # Si usas eliminación de módulos, recuerda manejar module_formset.deleted_objects

            return redirect('course_wizard')  # O a la url que quieras
        else:
            print(course_form.errors)
            print(module_formset.errors)


    else:
        course_form = CourseHeaderForm(instance=course)
        module_formset = ModuleFormSet(queryset=modules)

    return render(request, 'courses/admin/admin_course_edit.html', {
        'course_form': course_form,
        'module_formset': module_formset,
        'course': course,
        'modules': modules,
    })



@login_required
def user_courses(request):
    today = timezone.now().date()

    # Cursos asignados directamente al usuario
    enrolled_courses = EnrolledCourse.objects.filter(user=request.user).select_related('course', 'course__config')
    assigned_courses = [e.course for e in enrolled_courses]

    # Cursos con config.audience == "all_users"
    public_courses = CourseHeader.objects.filter(config__audience="all_users")

    # Cursos en CourseAssignment con tipo all_users
    assigned_by_type = CourseAssignment.objects.filter(
        assignment_type="all_users"
    ).values_list("course_id", flat=True)
    type_based_courses = CourseHeader.objects.filter(id__in=assigned_by_type)

    # Unir todos, sin duplicados
    all_courses = list(set(assigned_courses) | set(public_courses) | set(type_based_courses))

    # Simular progreso si no existe EnrolledCourse
    fake_enrollments = []
    enrolled_ids = set(e.course.id for e in enrolled_courses)
    for course in all_courses:
        if hasattr(course, 'config') and course.config and course.config.deadline is not None:
            deadline_date = course.created_at + timedelta(days=course.config.deadline)
            course.deadline_date = deadline_date.date()
        else:
            course.deadline_date = None

        if course.id not in enrolled_ids:
            fake_enrollments.append(EnrolledCourse(course=course, user=request.user, progress=0))


    # Combinar con los reales
    all_enrollments = list(enrolled_courses) + fake_enrollments

    completed_course_ids = []
    for course in all_courses:
        enrolled = next((e for e in enrolled_courses if e.course.id == course.id), None)
        total_lessons = Lesson.objects.filter(module_content__course_header=course).count()
        viewed = [v.strip() for v in enrolled.notes.split(",")] if enrolled and enrolled.notes else []
        quiz_passed = QuizAttempt.objects.filter(user=request.user, course=course, passed=True).exists()

        if ((total_lessons == 0 and quiz_passed) or
            (total_lessons > 0 and len(viewed) >= total_lessons and quiz_passed)):
            completed_course_ids.append(course.id)
        
    assigned_courses_combined = set(assigned_courses)
    assigned_course_ids = set(c.id for c in assigned_courses)
    assigned_courses_count = len(assigned_courses_combined)



    return render(request, 'courses/user/wizard_form_user.html', {
        'courses': all_courses,
        'enrolled_courses': all_enrollments,
        'today': today,
        'totalcursos': len(all_courses),
        'in_progress_courses_count': sum(1 for c in all_courses if c.deadline_date is None or c.deadline_date > today),
        'inactive_courses_count': sum(1 for c in all_courses if c.deadline_date and c.deadline_date <= today),
        'completed_course_ids': completed_course_ids,
        'assigned_courses_count': assigned_courses_count,
        'assigned_course_ids': assigned_course_ids,
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
    unread_count = EnrolledCourse.objects.filter(user=request.user, is_read=False).count()
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
#     c.setFont("Helvetica", 14)
#     c.drawCentredString(580, 225, f"POR CONLCUÍR SATIFACTORIAMENTE EL CURSO DE:")
#     c.setFont("Helvetica-Bold", 17)
#     c.drawCentredString(580, 200, f"{nombre_curso}")
#     c.setFont("Helvetica", 10)
#     fecha_hoy = date.today().strftime("%d/%m/%Y")
#     c.drawCentredString(580, 180, f"EL DÍA {fecha_hoy} CON UNA DURACION DE 0 HORAS")
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


#     # 4. GUARDAR EN BD Y ARCHIVO
#     try:
#         curso = CourseHeader.objects.get(title=nombre_curso)
#         existe_certificado = CourseCertificate.objects.filter(user=request.user, course=curso).exists()
#         if not existe_certificado:
#             certificado = CourseCertificate(user=request.user, course=curso)
#             filename = f"certificado_{slugify(request.user.username)}_{slugify(curso.title)}.pdf"
#             ruta_guardado = os.path.join("certificates", filename)
#             certificado.file.save(ruta_guardado, File(final_output))
#             certificado.save()
#             print("✅ Certificado guardado correctamente")
#     except Exception as e:
#         return HttpResponse(e)

#     # 5. Mostrar al usuario
#     final_output.seek(0)
#     response = HttpResponse(final_output, content_type='application/pdf')
#     response['Content-Disposition'] = 'inline; filename="vista_previa_certificado.pdf"'
#     return response

def generar_y_guardar_certificado(usuario, curso):

    width, height = 842, 595
    nombre_usuario = usuario.get_full_name()
    nombre_curso = curso.title

    # 1. Generar overlay de texto
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(580, 260, nombre_usuario)
    c.setFont("Helvetica", 14)
    c.drawCentredString(580, 225, f"POR CONLCUÍR SATIFACTORIAMENTE EL CURSO DE:")
    c.setFont("Helvetica-Bold", 17)
    c.drawCentredString(580, 200, f"{nombre_curso}")
    c.setFont("Helvetica", 10)
    fecha_hoy = date.today().strftime("%d/%m/%Y")
    c.drawCentredString(580, 180, f"EL DÍA {fecha_hoy} CON UNA DURACION DE {curso.duration} HORAS")
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

    print("✅ Certificado guardado:", filename)
    return certificado

