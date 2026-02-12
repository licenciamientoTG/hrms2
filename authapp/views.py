from datetime import date, timedelta

from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib.auth import get_user_model

from .forms import LoginForm, RegisterForm
from apps.courses.models import EnrolledCourse, CourseHeader, CourseAssignment
from apps.employee.models import Employee


def login_view(request):
    next_url = request.POST.get('next') or request.GET.get('next')

    if request.method == "POST":
        form = LoginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            if next_url:
                return redirect(next_url) 
            else:
                return redirect("home")    
    else:
        form = LoginForm()

    return render(request, "authapp/login.html", {"form": form})


@login_required
def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")
        else:
            messages.error(request, "Error al registrar usuario")
    else:
        form = RegisterForm()

    return render(request, "authapp/register.html", {"form": form})


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


# ==========================
#  Helper para 3er lunes de noviembre
# ==========================

def third_monday_of_november(year: int) -> date:
    """
    Regresa la fecha del tercer lunes de noviembre del año dado.
    """
    nov1 = date(year, 11, 1)
    # weekday(): lunes = 0 ... domingo = 6
    offset = (0 - nov1.weekday()) % 7  # 0 = lunes
    first_monday = nov1 + timedelta(days=offset)
    third_monday = first_monday + timedelta(weeks=2)  # 3er lunes
    return third_monday


# ==========================
#  Home / Dashboard de usuario
# ==========================

@login_required
def home(request):
    # --- Dashboard de superusuario ---
    if request.user.is_staff:
        User = get_user_model()
        total_colaboradores = User.objects.filter(
            is_active=True,
            is_superuser=False,
        ).count()

        return render(request, "authapp/home.html", {
            "total_colaboradores": total_colaboradores
        })

    # --- Dashboard de usuario normal ---
    user = request.user
    today = timezone.localdate()

    try:
        empleado = Employee.objects.get(user=user)
        vacation_balance = empleado.vacation_balance or 0
        saving_fund = empleado.saving_fund or 0
    except Employee.DoesNotExist:
        vacation_balance = 0
        saving_fund = 0

    # ==== Avance entre 3ª semana de noviembre pasada y próxima ====
    current_year_target = third_monday_of_november(today.year)

    if today >= current_year_target:
        last_saving_date = current_year_target
        next_saving_date = third_monday_of_november(today.year + 1)
    else:
        last_saving_date = third_monday_of_november(today.year - 1)
        next_saving_date = current_year_target

    total_days = (next_saving_date - last_saving_date).days or 1
    elapsed_days = max((today - last_saving_date).days, 0)

    saving_progress_percent = int(elapsed_days * 100 / total_days)
    saving_progress_percent = max(0, min(saving_progress_percent, 100))

    # ==== Cursos ====
    enrolled_courses = EnrolledCourse.objects.filter(
        user=user
    ).select_related('course', 'course__config')
    assigned_courses = [e.course for e in enrolled_courses]

    public_courses = CourseHeader.objects.filter(config__audience="all_users")

    assigned_by_type = CourseAssignment.objects.filter(
        assignment_type="all_users"
    ).values_list("course_id", flat=True)
    type_based_courses = CourseHeader.objects.filter(id__in=assigned_by_type)

    all_courses = list(set(assigned_courses) | set(public_courses) | set(type_based_courses))

    for course in all_courses:
        if hasattr(course, 'config') and course.config and course.config.deadline is not None:
            deadline_date = course.created_at + timedelta(days=course.config.deadline)
            course.deadline_date = deadline_date.date()
        else:
            course.deadline_date = None

    in_progress_courses_count = sum(
        1 for c in all_courses if c.deadline_date is None or c.deadline_date > today
    )

    return render(request, "authapp/home_user.html", {
        "in_progress_courses_count": in_progress_courses_count,
        "vacation_balance": vacation_balance,
        "saving_fund": saving_fund,
        "saving_progress_percent": saving_progress_percent,
        "next_saving_date": next_saving_date,
        "last_saving_date": last_saving_date,
    })

@login_required
def terms_and_conditions_view(request):
    if request.method == "POST":
        if hasattr(request.user, 'userprofile'):
            profile = request.user.userprofile
            profile.accepted_terms = True
            profile.save()
            messages.success(request, "Has aceptado los términos y condiciones.")
            return redirect("home")
    
    return render(request, "authapp/terms_and_conditions.html")
