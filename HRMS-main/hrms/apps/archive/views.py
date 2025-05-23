from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def archive_dashboard_view(request):
    return render(request, 'archive/archive_dashboard.html')
