from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def onboarding_dashboard_view(request):
    return render(request, 'onboarding/onboarding_dashboard.html')
