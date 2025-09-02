from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test

# esta vista te redirige a las vistas de usuario y administrador
@login_required
def onboarding_dashboard(request):
    if request.user.is_superuser:
        return redirect('onboarding_dashboard_admin')
    else:
        return redirect('onboarding_dashboard_user')

# esta vista es para el administrador
@login_required
@user_passes_test(lambda u: u.is_superuser)
def onboarding_dashboard_admin(request):

    return render(request, 'onboarding/admin/onboarding_dashboard_admin.html')

# esta vista es para el usuario
@login_required
def onboarding_dashboard_user(request):

    return render(request, 'onboarding/user/onboarding_dashboard_user.html')