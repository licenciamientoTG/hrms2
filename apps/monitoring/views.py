from django.shortcuts import render
from django.contrib.admin.views.decorators import user_passes_test

@user_passes_test(lambda u: u.is_superuser)
def monitoring_view(request):
    return render(request, "monitoring/monitoring_view.html")
