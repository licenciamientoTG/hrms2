from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from departments.models import Department
from apps.employee.models import Employee


@login_required
def incentives_dashboard(request):
    if request.user.is_staff:
        return redirect('incentives_dashboard_admin')
    else:
        return redirect('incentives_dashboard_user')


@login_required
@user_passes_test(lambda u: u.is_staff)
def incentives_dashboard_admin(request):
    departments = Department.objects.all().order_by('name')

    gerentes = (
        Employee.objects
        .filter(job_position__title__icontains='gerente de estación', is_active=True)
        .select_related('department', 'job_position')
    )
    gerentes_by_dept = {emp.department_id: emp for emp in gerentes}

    employees_by_dept = {}
    for emp in Employee.objects.filter(is_active=True).select_related('department', 'job_position').order_by('last_name', 'first_name'):
        employees_by_dept.setdefault(emp.department_id, []).append(emp)

    dept_data = []
    for dept in departments:
        gerente = gerentes_by_dept.get(dept.id)
        if gerente:
            dept_data.append({
                'dept': dept,
                'gerente': f"{gerente.first_name} {gerente.last_name}".strip(),
                'employees': employees_by_dept.get(dept.id, []),
            })

    return render(request, 'incentives/admin/incentives_dashboard_admin.html', {
        'dept_data': dept_data,
    })


@login_required
def incentives_dashboard_user(request):
    return render(request, 'incentives/user/incentives_dashboard_user.html')
