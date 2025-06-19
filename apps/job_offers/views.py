from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def job_offers_dashboard_view(request):
    return render(request, 'job_offers/job_offers_dashboard.html')
