from django.forms import formset_factory
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404, render, redirect
from django.core.files.storage import DefaultStorage
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from pyexpat.errors import messages
from formtools.wizard.views import SessionWizardView

from apps.employee.models import Employee, JobCategory, JobPosition
from apps.location.models import Location
from .forms import CourseHeaderForm, CourseConfigForm, ModuleContentForm, LessonForm, QuizForm
from .models import CourseAssignment, CourseHeader, CourseConfig, EnrolledCourse, ModuleContent, Lesson, CourseCategory,  LessonAttachment, Quiz
import json
from datetime import timedelta, datetime, timezone
from departments.models import Department
from django.contrib.auth.models import User
from django.contrib.admin.views.decorators import staff_member_required
from django.forms import modelformset_factory
from django.shortcuts import redirect
from django.utils import timezone
import os


LessonFormSet = formset_factory(LessonForm, extra=1)  # Permite agregar varias lecciones

@login_required
def course_wizard(request):
    if request.user.is_superuser:
        employees = Employee.objects.filter(is_active=True)
        departments = Department.objects.all()
        job_positions = JobPosition.objects.all()
        locations = Location.objects.all()
        template_name = "courses/admin/admin_courses.html"
    else:
        employees = None
        departments = None
        job_positions = None
        locations = None
        template_name = "courses/user/wizard_form_user.html"

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

    # 🔧 Aquí definimos los cursos y totalcursos de forma segura
    if request.user.is_superuser:
        courses = CourseHeader.objects.all()
        totalcursos = courses.count()
    else:
        enrolled_courses = EnrolledCourse.objects.filter(user=request.user).select_related('course', 'course__config')
        assigned_courses = [e.course for e in enrolled_courses]

        public_courses = CourseHeader.objects.filter(config__audience="all_users")

        assigned_by_type = CourseAssignment.objects.filter(
            assignment_type="all_users"
        ).values_list("course_id", flat=True)
        type_based_courses = CourseHeader.objects.filter(id__in=assigned_by_type)

        courses = list(set(assigned_courses) | set(public_courses) | set(type_based_courses))
        totalcursos = len(courses)

        fake_enrollments = []
        enrolled_ids = set(e.course.id for e in enrolled_courses)
        for course in courses:
            if hasattr(course, 'config') and course.config.deadline is not None:
                course.deadline_date = (course.created_at + timedelta(days=course.config.deadline)).date()
            else:
                course.deadline_date = None

            if course.id not in enrolled_ids:
                fake_enrollments.append(EnrolledCourse(course=course, user=request.user, progress=0))

        all_enrollments = list(enrolled_courses) + fake_enrollments


    courses_config = CourseConfig.objects.all()
    today = datetime.now().date()

    # 📆 Calculamos fechas de los cursos
    inactive_courses_count = 0
    in_progress_courses_count = 0

    for course in courses:
        if hasattr(course, 'config') and course.config.deadline is not None:
            deadline_date = course.created_at + timedelta(days=course.config.deadline)
            course.deadline_date = deadline_date.date()
            if course.deadline_date <= today:
                inactive_courses_count += 1
            else:
                in_progress_courses_count += 1
        else:
            course.deadline_date = None

    return render(request, template_name, {
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
    })


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



@csrf_exempt  # ⚠️ Solo para pruebas locales. En producción usa el token CSRF del frontend
@login_required
def save_course_ajax(request):
    if request.method == 'POST':
        try:
            # 🔹 1. Obtener los datos desde `request.POST` y `request.FILES`
            step1_raw = request.POST.get("step1", "{}")
            step2_raw = request.POST.get("step2", "{}")
            modules_raw = request.POST.get("modules", "[]")
            portrait_file = request.FILES.get("portrait")

            step1_data = json.loads(step1_raw)
            step2_data = json.loads(step2_raw)
            modules_data = json.loads(modules_raw)

            ALLOWED_EXTENSIONS = [".pdf", ".docx", ".pptx", ".mp4"]
            
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

            # 🔹 4. Guardar CourseHeader (con imagen)
            course = CourseHeader.objects.create(
                title=step1_data.get("title"),
                description=step1_data.get("description"),
                duration=step1_data.get("duration"),
                user=request.user,
                category=category,
                portrait=portrait_file  # <<✅ Aquí se guarda la imagen
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
                                "message": f"El archivo '{resource_file.name}' no está permitido. Solo se aceptan PDF, DOCX, PPTX y MP4."
                            }, status=400)
                        
                    Lesson.objects.create(
                        module_content=new_module,
                        title=lesson.get("title"),
                        lesson_type=lesson.get("type"),
                        description=lesson.get("description"),
                        video_url=lesson.get("video_url"),
                        resource=resource_file  # ✅ Esto guardará el archivo en media/lessons/
                    )




            return JsonResponse({"status": "success", "message": "Curso guardado correctamente."})

        except json.JSONDecodeError:
            return JsonResponse({"status": "error", "message": "Error al procesar los datos JSON."}, status=400)

    return JsonResponse({"status": "error", "message": "Método no permitido."}, status=405)


def process_assignments(request):
    # Si la peticion es de tipo POST
    if request.method == 'POST':
        return HttpResponse("Procesar asignaciones")
    return HttpResponseBadRequest("Método no permitido")

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
                'redirect_url': '/courses/course_wizard/'
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
    modules = ModuleContent.objects.filter(course_header=course).order_by("created_at")

    return render(request, 'courses/user/view_course.html', {
        'course': course,
        'modules': modules,
        'enrolled': enrolled
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
        if hasattr(course, 'config') and course.config.deadline is not None:
            course.deadline_date = (course.created_at + timedelta(days=course.config.deadline)).date()
        else:
            course.deadline_date = None

        if course.id not in enrolled_ids:
            fake_enrollments.append(EnrolledCourse(course=course, user=request.user, progress=0))

    # Combinar con los reales
    all_enrollments = list(enrolled_courses) + fake_enrollments

    return render(request, 'courses/user/wizard_form_user.html', {
        'courses': all_courses,
        'enrolled_courses': all_enrollments,
        'today': today,
        'totalcursos': len(all_courses),
        'in_progress_courses_count': sum(1 for c in all_courses if c.deadline_date is None or c.deadline_date > today),
        'inactive_courses_count': sum(1 for c in all_courses if c.deadline_date and c.deadline_date <= today),
    })

@login_required
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
