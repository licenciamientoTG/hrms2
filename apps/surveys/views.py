from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def survey_dashboard_view(request):
    return render(request, 'surveys/survey_dashboard.html')
