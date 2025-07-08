from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def vacation_request_view(request):
    return render(request, 'vacations/user/vacation_form_user.html')
