from django.shortcuts import render
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test


#esta vista solo nos separa la vista del usuario y del administrador por medio de su url
@login_required
def staff_requisitions_view(request):
    if request.user.is_staff:
        return redirect('admin_staff_requisitions')
    else:
        return redirect('user_staff_requisitions')

#esta vista solo nos manda a admin_staff_requisitions.html
@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_staff_requisitions(request):
    return render(request, 'staff_requisitions/admin/admin_staff_requisitions.html')

#esta vista solo nos manda a user_staff_requisitions.html
@login_required
def user_staff_requisitions(request):
    return render(request, 'staff_requisitions/user/user_staff_requisitions.html')