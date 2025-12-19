from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
from django.shortcuts import redirect

#esta vista redirige al usuario a la vista adecuada según su rol
@login_required
def policies_dashboard_view(request):
    if request.user.is_staff:
        return redirect('policies_admin_view')
    else:
        return redirect('policies_user_view')


#esta vista es para administradores
@login_required
@user_passes_test(lambda u: u.is_staff)
def policies_admin_view(request):
    return render(request, 'policies/admin/policies_admin.html')

#esta vista es para usuarios normales
@login_required
def policies_user_view(request):
    return render(request, 'policies/user/policies_user.html')
