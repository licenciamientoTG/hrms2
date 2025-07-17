from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as auth_views

from apps.courses.models import EnrolledCourse, CourseHeader, CourseAssignment
from django.utils import timezone
from datetime import timedelta
from apps.employee.models import Employee

@login_required
def home(request):
    if request.user.is_superuser:
        return render(request, "authapp/home.html")

    user = request.user
    today = timezone.now().date()

    # Cursos directos
    enrolled_courses = EnrolledCourse.objects.filter(user=user).select_related('course', 'course__config')
    assigned_courses = [e.course for e in enrolled_courses]

    # Cursos públicos
    public_courses = CourseHeader.objects.filter(config__audience="all_users")

    # Cursos asignados tipo all_users
    assigned_by_type = CourseAssignment.objects.filter(
        assignment_type="all_users"
    ).values_list("course_id", flat=True)
    type_based_courses = CourseHeader.objects.filter(id__in=assigned_by_type)

    # Combinar todos
    all_courses = list(set(assigned_courses) | set(public_courses) | set(type_based_courses))

    # Calcular fecha límite
    for course in all_courses:
        if hasattr(course, 'config') and course.config and course.config.deadline is not None:
            deadline_date = course.created_at + timedelta(days=course.config.deadline)
            course.deadline_date = deadline_date.date()
        else:
            course.deadline_date = None

    # Contar solo cursos activos
    in_progress_courses_count = sum(
        1 for c in all_courses if c.deadline_date is None or c.deadline_date > today
    )

    return render(request, "authapp/home_user.html", {
        'in_progress_courses_count': in_progress_courses_count
    })


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", auth_views.LoginView.as_view(template_name="authapp/login.html"), name="login"),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path("home/", home, name="home"),
    path("auth/", include("authapp.urls")),
    path('departments/', include('departments.urls')),
    path('news/', include('apps.news.urls')),
    path('forms_requests/', include('apps.forms_requests.urls')),
    path('vacations/', include('apps.vacations.urls')),
    path('performance/', include('apps.performance.urls')),
    path('org_chart/', include('apps.org_chart.urls')),
    path('courses/', include('apps.courses.urls')),
    path('users/', include('apps.users.urls')),
    path('recognitions/', include('apps.recognitions.urls')),
    path('objectives/', include('apps.objectives.urls')),
    path('archive/', include('apps.archive.urls')),
    path('onboarding/', include('apps.onboarding.urls')),
    path('surveys/', include('apps.surveys.urls')),
    path('documents/', include('apps.documents.urls')),
    path('job_offers/', include('apps.job_offers.urls')), 
    path('policies/', include('apps.policies.urls')),
    path('career_plan/', include('apps.career_plan.urls')),
    path("auth/login/", auth_views.LoginView.as_view(template_name="authapp/login.html"), name="login"),


    # Paso 1: Vista para ingresar el email
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),

    # Paso 2: Confirmación de envío de email
    path('password_reset_done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),

    # Paso 3: Link en el email -> Formulario de nueva contraseña
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),

    # Paso 4: Confirmación de cambio de contraseña
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('vacations/', include('apps.vacations.urls')),



]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
