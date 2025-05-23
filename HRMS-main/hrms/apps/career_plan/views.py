from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def career_plan_dashboard_view(request):
    return render(request, 'career_plan/career_plan_dashboard.html')
