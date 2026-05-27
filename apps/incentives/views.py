from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from departments.models import Department
from apps.employee.models import Employee
from apps.incentives.constants import STATION_TEAMS


@login_required
def incentives_dashboard(request):
    if not request.user.has_perm('incentives.Modulo_incentivos'):
        return redirect('home')

    if request.user.is_superuser or request.user.is_staff:
        return redirect('incentives_dashboard_admin')

    try:
        emp = Employee.objects.select_related('job_position').get(user=request.user)
        titulo = (emp.job_position.title if emp.job_position else '').lower()
        es_gerente = 'gerente de estaci' in titulo or 'subgerente de estaci' in titulo
    except Employee.DoesNotExist:
        es_gerente = False

    if es_gerente:
        return redirect('incentives_dashboard_manager')
    return redirect('incentives_dashboard_user')


@login_required
@user_passes_test(lambda u: u.has_perm('incentives.Modulo_incentivos'))
def incentives_dashboard_admin(request):
    from datetime import date, timedelta
    today = date.today()

    if 'reset' in request.GET:
        request.session['incentivos_admin_delta'] = 0
    elif 'delta' in request.GET:
        request.session['incentivos_admin_delta'] = int(request.GET['delta'])

    delta = request.session.get('incentivos_admin_delta', 0)

    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=delta)
    week_end = week_start + timedelta(days=6)

    # Inicializar todas las estaciones vacías
    teams = {
        team_key: {'display': display_name, 'employees': [], 'gerente': None}
        for team_key, display_name in STATION_TEAMS.items()
    }

    # Llenar con empleados activos que pertenezcan a una estación del diccionario
    employees = (
        Employee.objects
        .filter(is_active=True, team__in=STATION_TEAMS.keys())
        .select_related('job_position')
        .order_by('last_name', 'first_name')
    )

    for emp in employees:
        team_key = emp.team.strip()
        if team_key not in teams:
            continue
        teams[team_key]['employees'].append(emp)
        titulo = (emp.job_position.title if emp.job_position else '').lower()
        if 'gerente de estaci' in titulo and 'subgerente' not in titulo and teams[team_key]['gerente'] is None:
            teams[team_key]['gerente'] = f"{emp.first_name} {emp.last_name}".strip()

    dept_data = sorted(
        [
            {'team': data['display'], 'gerente': data['gerente'], 'employees': data['employees']}
            for data in teams.values()
        ],
        key=lambda x: x['team']
    )

    return render(request, 'incentives/admin/incentives_dashboard_admin.html', {
        'dept_data': dept_data,
        'week_start': week_start,
        'week_end': week_end,
        'today': today,
        'delta': delta,
    })


@login_required
def incentives_dashboard_manager(request):
    from datetime import date, timedelta
    today = date.today()

    if 'reset' in request.GET:
        request.session['incentivos_manager_delta'] = 0
    elif 'delta' in request.GET:
        request.session['incentivos_manager_delta'] = int(request.GET['delta'])

    delta = request.session.get('incentivos_manager_delta', 0)

    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=delta)
    week_end = week_start + timedelta(days=6)
    days = [week_start + timedelta(days=i) for i in range(7)]

    try:
        gerente_emp = Employee.objects.select_related('department').get(user=request.user)
        department = gerente_emp.department
        colaboradores = (
            Employee.objects
            .filter(department=department, is_active=True)
            .exclude(user=request.user)
            .select_related('job_position')
            .order_by('last_name', 'first_name')
        )
    except Employee.DoesNotExist:
        department = None
        colaboradores = Employee.objects.none()

    TIPOS = ['Diesel', 'Encargado', 'Mistery', 'Venta', 'ECU', 'Auditoría', 'Rotación', 'Inventario', 'Otros']

    return render(request, 'incentives/manager/incentives_dashboard_manager.html', {
        'week_start': week_start,
        'week_end': week_end,
        'today': today,
        'delta': delta,
        'days': days,
        'department': department,
        'colaboradores': colaboradores,
        'tipos': TIPOS,
    })


@login_required
def incentives_dashboard_user(request):
    from datetime import date, timedelta
    today = date.today()

    # Navegar semanas: ?delta ajusta y guarda en sesión, ?reset vuelve a la semana actual
    if 'reset' in request.GET:
        request.session['incentivos_delta'] = 0
    elif 'delta' in request.GET:
        request.session['incentivos_delta'] = int(request.GET['delta'])

    delta = request.session.get('incentivos_delta', 0)

    # Semana ISO: lunes a domingo
    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=delta)
    week_end = week_start + timedelta(days=6)
    days = [week_start + timedelta(days=i) for i in range(7)]

    # Aquí irá la consulta real cuando existan los modelos:
    # incentivos = Incentivo.objects.filter(employee__user=request.user, fecha__range=(week_start, week_end))

    return render(request, 'incentives/user/incentives_dashboard_user.html', {
        'week_start': week_start,
        'week_end': week_end,
        'today': today,
        'delta': delta,
        'days': days,
    })
