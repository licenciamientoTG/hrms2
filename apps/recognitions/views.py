from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def recognition_dashboard_view(request):
    return render(request, 'recognitions/recognition_dashboard.html')
