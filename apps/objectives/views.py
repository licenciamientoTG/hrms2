from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib.auth.decorators import user_passes_test

#esta vista solo nos separa la vista del usuario y del administrador por medio de su url
@login_required
def objective_view(request):
    if request.user.is_superuser:
        return redirect('admin_objective')
    else:
        return redirect('user_objective')

#esta vista solo nos manda a admin_staff_requisitions.html
@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_objective(request):
    return render(request, 'objectives/admin/objectives_dashboard_admin.html')

#esta vista solo nos manda a user_objective.html
@login_required
def user_objective(request):
    return render(request, 'objectives/user/objectives_dashboard_user.html')