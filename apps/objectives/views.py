from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages

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
    display_name = (request.user.get_full_name() or request.user.username).strip()
    ctx = {"user_name": display_name}
    return render(request, "objectives/user/objectives_dashboard_user.html", ctx)


@login_required
def create_objective(request):
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        if not title:
            messages.error(request, "Indica un título para el objetivo.")
        else:
            return redirect("objective_view")
    return render(request, "objectives/user/create_objective.html")