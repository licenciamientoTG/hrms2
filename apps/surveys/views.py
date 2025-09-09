from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test

# esta vista te redirige a las vistas de usuario y administrador
@login_required
def survey_dashboard(request):
    if request.user.is_superuser:
        return redirect('survey_dashboard_admin')
    else:
        return redirect('survey_dashboard_user')

# esta vista es para el administrador
@login_required
@user_passes_test(lambda u: u.is_superuser)
def survey_dashboard_admin(request):

    return render(request, 'surveys/admin/survey_dashboard_admin.html')

# esta vista es para el usuario
@login_required
def survey_dashboard_user(request):

    return render(request, 'surveys/user/survey_dashboard_user.html')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def survey_new(request):
    # Solo mostrar la plantilla de creación (sin lógica de guardado aún)
    return render(request, 'surveys/admin/survey_new.html', {
        # puedes pasar datos base si quieres (vacío por ahora)
    })