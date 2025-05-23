from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required

def policies_dashboard_view(request):
    return render(request, 'policies/policies_dashboard.html')
