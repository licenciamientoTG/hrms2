from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def document_dashboard_view(request):
    return render(request, 'documents/document_dashboard.html')
