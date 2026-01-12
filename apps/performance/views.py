from django.shortcuts import render, redirect
from .forms import PerformanceReviewForm
from django.contrib.auth.decorators import login_required, user_passes_test

@login_required
def performance_view(request):
    if request.user.is_staff:
        return redirect('performance_view_admin')
    else:
        return redirect('performance_view_user')

@login_required
@user_passes_test(lambda u: u.is_staff)
def performance_view_admin(request):
    return render(request, 'performance/admin/performance_view_admin.html')

@login_required
def performance_view_user(request):
    return render(request, 'performance/user/performance_view_user.html')

# # esta vista es para el administrador
# @login_required
# @user_passes_test(lambda u: u.is_staff)
# def job_offers_dashboard_admin(request):

#     return render(request, 'job_offers/admin/job_offers_dashboard_admin.html')

# # esta vista es para el usuario
# @login_required
# def job_offers_dashboard_user(request):

#     return render(request, 'job_offers/user/job_offers_dashboard_user.html')