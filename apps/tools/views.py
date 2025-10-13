from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# Create your views here.

@login_required
def tools_view(request):
    return render(request, "tools/loan_calculator_view.html")