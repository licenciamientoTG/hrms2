from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def recognition_dashboard_view(request):
    return render(request, 'recognitions/recognition_dashboard.html')


from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test

# esta vista te redirige a las vistas de usuario y administrador
@login_required
def recognition_dashboard(request):
    if request.user.is_superuser:
        return redirect('recognition_dashboard_admin')
    else:
        return redirect('recognition_dashboard_user')

# esta vista es para el administrador
@login_required
@user_passes_test(lambda u: u.is_superuser)
def recognition_dashboard_admin(request):

    return render(request, 'recognitions/admin/recognition_dashboard_admin.html')

# esta vista es para el usuario
@login_required
def recognition_dashboard_user(request):

    return render(request, 'recognitions/user/recognition_dashboard_user.html')