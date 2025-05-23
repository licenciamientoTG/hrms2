from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def objective_dashboard_view(request):
    return render(request, 'objectives/objective_dashboard.html')
