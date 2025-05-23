from django.shortcuts import render
from .models import Department, Employee
from django.contrib.auth.decorators import login_required

@login_required
def org_chart_view(request):
    departments = Department.objects.prefetch_related('subdepartments').all()
    employees = Employee.objects.select_related('department', 'supervisor').all()

    return render(request, 'org_chart/org_chart.html', {
        'departments': departments,
        'employees': employees,
    })
