import json
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, user_passes_test
from departments.models import Department
from apps.employee.models import Employee
from apps.incentives.constants import STATION_TEAMS
from apps.incentives.models import IncentivoRegistro, ComentarioSemana, SemanaCerrada


def _deduplicar_por_tsa(employees):
    """Si un CURP aparece en dos empresas, conserva solo el registro de TSA."""
    seen = {}   # curp -> índice en result
    result = []
    for emp in employees:
        curp = (emp.curp or '').strip().upper()
        is_tsa = 'tsa' in (emp.company or '').lower()
        if not curp:
            result.append(emp)
            continue
        if curp not in seen:
            seen[curp] = len(result)
            result.append(emp)
        else:
            idx = seen[curp]
            existing_is_tsa = 'tsa' in (result[idx].company or '').lower()
            if is_tsa and not existing_is_tsa:
                result[idx] = emp  # reemplazar con el de TSA
    return result


def _otorgar_permiso_incentivos(user):
    """Asigna el permiso Modulo_incentivos al usuario si aún no lo tiene."""
    from django.contrib.contenttypes.models import ContentType
    from django.contrib.auth.models import Permission
    perm = Permission.objects.get(
        codename='Modulo_incentivos',
        content_type=ContentType.objects.get(app_label='incentives', model='incentivosconfig'),
    )
    if not user.has_perm('incentives.Modulo_incentivos'):
        user.user_permissions.add(perm)


@login_required
def incentives_dashboard(request):
    if request.user.is_superuser or request.user.is_staff:
        return redirect('incentives_dashboard_admin')

    try:
        emp = Employee.objects.select_related('job_position').get(user=request.user)
        titulo = (emp.job_position.title if emp.job_position else '').lower()
        es_gerente = 'gerente de estaci' in titulo or 'subgerente de estaci' in titulo
        es_jefe_zona = 'jefe de zona' in titulo
    except Employee.DoesNotExist:
        es_gerente = False
        es_jefe_zona = False

    # Otorgar permiso automáticamente a roles que lo justifican por puesto
    if es_gerente or es_jefe_zona:
        _otorgar_permiso_incentivos(request.user)
        if es_gerente:
            return redirect('incentives_dashboard_manager')
        return redirect('incentives_dashboard_zona')

    # Para el resto, requiere permiso asignado manualmente
    if not request.user.has_perm('incentives.Modulo_incentivos'):
        return redirect('home')

    return redirect('incentives_dashboard_user')


@login_required
@user_passes_test(lambda u: u.has_perm('incentives.Modulo_incentivos'))
def incentives_dashboard_admin(request):
    from datetime import date, timedelta
    from django.db.models import Count
    import json
    today = date.today()

    if 'reset' in request.GET:
        request.session['incentivos_admin_delta'] = 0
    elif 'delta' in request.GET:
        request.session['incentivos_admin_delta'] = int(request.GET['delta'])

    delta = request.session.get('incentivos_admin_delta', 0)

    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=delta)
    week_end = week_start + timedelta(days=6)
    days = [week_start + timedelta(days=i) for i in range(7)]

    TIPOS = ['Diesel', 'Encargado', 'Venta', 'Mistery', 'ECV', 'Auditoría', 'Rotación', 'Inventario', 'Otros']

    teams = {
        team_key: {'display': display_name, 'employees': [], 'gerente': None}
        for team_key, display_name in STATION_TEAMS.items()
    }

    employees = _deduplicar_por_tsa(list(
        Employee.objects
        .filter(is_active=True, team__in=STATION_TEAMS.keys())
        .select_related('job_position')
        .order_by('last_name', 'first_name')
    ))

    emp_ids = [emp.id for emp in employees]
    incentivo_counts = {
        row['employee_id']: row['total']
        for row in IncentivoRegistro.objects.filter(
            employee_id__in=emp_ids,
            fecha__range=(week_start, week_end),
        ).values('employee_id').annotate(total=Count('id'))
    }

    for emp in employees:
        team_key = emp.team.strip()
        if team_key not in teams:
            continue
        emp.incentivo_count = incentivo_counts.get(emp.id, 0)
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

    periodo_cerrado = SemanaCerrada.objects.filter(week_start=week_start).exists()

    # Presupuesto global: suma de todos los incentivos de la semana
    registros_semana = (
        IncentivoRegistro.objects
        .filter(employee_id__in=emp_ids, fecha__range=(week_start, week_end))
        .values('employee_id', 'tipo')
        .annotate(count=Count('id'))
    )
    presupuesto_global = 0
    for r in registros_semana:
        if r['tipo'] == 'Diesel':
            presupuesto_global += r['count'] * 50
        elif r['tipo'] == 'Encargado':
            presupuesto_global += 200 + (r['count'] - 1) * 100 if r['count'] > 0 else 0

    return render(request, 'incentives/admin/incentives_dashboard_admin.html', {
        'dept_data': dept_data,
        'week_start': week_start,
        'week_end': week_end,
        'today': today,
        'delta': delta,
        'days': days,
        'tipos': json.dumps(TIPOS),
        'periodo_cerrado': periodo_cerrado,
        'presupuesto_global': presupuesto_global,
    })


@login_required
def incentives_dashboard_zona(request):
    from datetime import date, timedelta
    from django.db.models import Count
    import json
    today = date.today()

    if 'reset' in request.GET:
        request.session['incentivos_zona_delta'] = 0
    elif 'delta' in request.GET:
        request.session['incentivos_zona_delta'] = int(request.GET['delta'])

    delta = request.session.get('incentivos_zona_delta', 0)

    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=delta)
    week_end = week_start + timedelta(days=6)
    days = [week_start + timedelta(days=i) for i in range(7)]

    TIPOS = ['Diesel', 'Encargado', 'Venta', 'Mistery', 'ECV', 'Auditoría', 'Rotación', 'Inventario', 'Otros']

    try:
        jefe = Employee.objects.select_related('job_position').get(user=request.user)
        primer_apellido = jefe.last_name.split()[0] if jefe.last_name else ''
        busqueda = f"{jefe.first_name} {primer_apellido}".strip()

        teams_del_jefe = set(
            Employee.objects.filter(
                team__in=STATION_TEAMS.keys(),
                job_position__title__icontains='gerente de estaci',
                leader__icontains=busqueda,
            ).values_list('team', flat=True)
        )
    except Employee.DoesNotExist:
        teams_del_jefe = set()

    teams = {
        team_key: {'display': STATION_TEAMS[team_key], 'employees': [], 'gerente': None}
        for team_key in teams_del_jefe
    }

    employees = _deduplicar_por_tsa(list(
        Employee.objects
        .filter(is_active=True, team__in=teams_del_jefe)
        .select_related('job_position')
        .order_by('last_name', 'first_name')
    ))

    # Conteo de incentivos por empleado para la semana actual
    emp_ids = [emp.id for emp in employees]
    incentivo_counts = {
        row['employee_id']: row['total']
        for row in IncentivoRegistro.objects.filter(
            employee_id__in=emp_ids,
            fecha__range=(week_start, week_end),
        ).values('employee_id').annotate(total=Count('id'))
    }

    for emp in employees:
        team_key = emp.team.strip()
        if team_key not in teams:
            continue
        emp.incentivo_count = incentivo_counts.get(emp.id, 0)
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

    periodo_cerrado = SemanaCerrada.objects.filter(week_start=week_start).exists()

    return render(request, 'incentives/zona/incentives_dashboard_zona.html', {
        'dept_data': dept_data,
        'week_start': week_start,
        'week_end': week_end,
        'today': today,
        'delta': delta,
        'days': days,
        'tipos': json.dumps(TIPOS),
        'periodo_cerrado': periodo_cerrado,
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
        colaboradores = _deduplicar_por_tsa(list(
            Employee.objects
            .filter(department=department, is_active=True)
            .exclude(user=request.user)
            .select_related('job_position')
            .order_by('last_name', 'first_name')
        ))
    except Employee.DoesNotExist:
        department = None
        colaboradores = Employee.objects.none()

    TIPOS = ['Diesel', 'Encargado', 'Venta', 'Mistery', 'ECV', 'Auditoría', 'Rotación', 'Inventario', 'Otros']

    periodo_cerrado = SemanaCerrada.objects.filter(week_start=week_start).exists()

    return render(request, 'incentives/manager/incentives_dashboard_manager.html', {
        'week_start': week_start,
        'week_end': week_end,
        'today': today,
        'delta': delta,
        'days': days,
        'department': department,
        'colaboradores': colaboradores,
        'tipos': TIPOS,
        'periodo_cerrado': periodo_cerrado,
    })


@login_required
def incentives_dashboard_user(request):
    from datetime import date, timedelta
    today = date.today()

    if 'reset' in request.GET:
        request.session['incentivos_delta'] = 0
    elif 'delta' in request.GET:
        request.session['incentivos_delta'] = int(request.GET['delta'])

    delta = request.session.get('incentivos_delta', 0)

    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=delta)
    week_end = week_start + timedelta(days=6)
    days = [week_start + timedelta(days=i) for i in range(7)]

    try:
        emp = Employee.objects.get(user=request.user)
        diesel_fechas = set(
            IncentivoRegistro.objects.filter(
                employee=emp,
                tipo='Diesel',
                fecha__range=(week_start, week_end),
            ).values_list('fecha', flat=True)
        )
        diesel_dias = sum(1 for d in days if d in diesel_fechas)
        encargado_fechas = set(
            IncentivoRegistro.objects.filter(
                employee=emp,
                tipo='Encargado',
                fecha__range=(week_start, week_end),
            ).values_list('fecha', flat=True)
        )
        encargado_dias = sum(1 for d in days if d in encargado_fechas)
    except Employee.DoesNotExist:
        diesel_fechas = set()
        diesel_dias = 0
        encargado_fechas = set()
        encargado_dias = 0

    diesel_total = diesel_dias * 50
    encargado_total = (200 + (encargado_dias - 1) * 100) if encargado_dias > 0 else 0
    gran_total = diesel_total + encargado_total

    return render(request, 'incentives/user/incentives_dashboard_user.html', {
        'week_start': week_start,
        'week_end': week_end,
        'today': today,
        'delta': delta,
        'days': days,
        'diesel_fechas': diesel_fechas,
        'diesel_dias': diesel_dias,
        'diesel_total': diesel_total,
        'encargado_fechas': encargado_fechas,
        'encargado_dias': encargado_dias,
        'encargado_total': encargado_total,
        'gran_total': gran_total,
        'otros_tipos': ['Venta', 'Mistery', 'ECV', 'Auditoría', 'Rotación', 'Inventario', 'Otros'],
    })


# ── AJAX ────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def toggle_semana_cerrada(request):
    """Abre o cierra una semana para edición. Solo admin/superuser."""
    if not (request.user.is_superuser or request.user.is_staff):
        return JsonResponse({'ok': False, 'error': 'Sin permiso'}, status=403)

    try:
        data = json.loads(request.body)
        week_start = data['week_start']
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'error': 'Datos inválidos'}, status=400)

    cerrada = SemanaCerrada.objects.filter(week_start=week_start).first()
    if cerrada:
        cerrada.delete()
        return JsonResponse({'ok': True, 'estado': 'abierta'})
    else:
        SemanaCerrada.objects.create(week_start=week_start, cerrada_por=request.user)
        return JsonResponse({'ok': True, 'estado': 'cerrada'})


@login_required
@require_POST
def toggle_incentivo(request):
    """Marca o desmarca un incentivo (crea o elimina el registro)."""
    from datetime import date, timedelta
    try:
        data = json.loads(request.body)
        emp_id = int(data['emp'])
        tipo = data['tipo'].strip()
        fecha = data['fecha']  # 'YYYY-MM-DD'
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'error': 'Datos inválidos'}, status=400)

    # Verificar si la semana está cerrada
    fecha_date = date.fromisoformat(fecha)
    week_start = fecha_date - timedelta(days=fecha_date.weekday())
    if SemanaCerrada.objects.filter(week_start=week_start).exists():
        return JsonResponse({'ok': False, 'error': 'Semana cerrada', 'cerrada': True}, status=403)

    try:
        emp = Employee.objects.get(pk=emp_id)
    except Employee.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Empleado no encontrado'}, status=404)

    # Si ya existe → desmarcar
    existente = IncentivoRegistro.objects.filter(employee=emp, tipo=tipo, fecha=fecha).first()
    if existente:
        existente.delete()
        return JsonResponse({'ok': True, 'estado': 'eliminado'})

    # Límite de 6 días por semana para Diesel
    if tipo == 'Diesel':
        dias_semana = IncentivoRegistro.objects.filter(
            employee=emp,
            tipo='Diesel',
            fecha__range=(week_start, week_start + timedelta(days=6)),
        ).count()
        if dias_semana >= 6:
            return JsonResponse(
                {'ok': False, 'error': 'Máximo 6 días de Diesel por semana ($300)', 'max_diesel': True},
                status=400,
            )

    # Límite de 6 palomitas por semana para Encargado (la 7ma no aplica)
    if tipo == 'Encargado':
        dias_semana = IncentivoRegistro.objects.filter(
            employee=emp,
            tipo='Encargado',
            fecha__range=(week_start, week_start + timedelta(days=6)),
        ).count()
        if dias_semana >= 6:
            return JsonResponse(
                {'ok': False, 'error': 'Máximo 6 días de Encargado por semana ($700)', 'max_encargado': True},
                status=400,
            )

    IncentivoRegistro.objects.create(employee=emp, tipo=tipo, fecha=fecha, registrado_por=request.user)
    return JsonResponse({'ok': True, 'estado': 'creado'})


@login_required
def semana_data(request):
    """Devuelve los incentivos registrados para un empleado en una semana."""
    from datetime import date, timedelta
    emp_id = request.GET.get('emp')
    semana = request.GET.get('semana')  # 'YYYY-MM-DD' lunes
    if not emp_id or not semana:
        return JsonResponse({'ok': False, 'error': 'Faltan parámetros'}, status=400)

    try:
        semana_date = date.fromisoformat(semana)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Fecha inválida'}, status=400)

    semana_end = semana_date + timedelta(days=6)
    registros = IncentivoRegistro.objects.filter(
        employee_id=emp_id,
        fecha__range=(semana_date, semana_end),
    ).values('tipo', 'fecha')

    comentarios = {
        c['tipo']: c['comentario']
        for c in ComentarioSemana.objects.filter(
            employee_id=emp_id,
            week_start=semana_date,
        ).values('tipo', 'comentario')
    }

    return JsonResponse({
        'ok': True,
        'registros': [
            {'tipo': r['tipo'], 'fecha': r['fecha'].isoformat()}
            for r in registros
        ],
        'comentarios': comentarios,
    })


@login_required
@require_POST
def guardar_comentario(request):
    """Guarda o actualiza el comentario semanal de un tipo de incentivo."""
    from datetime import date, timedelta
    try:
        data = json.loads(request.body)
        emp_id = int(data['emp'])
        tipo = data['tipo'].strip()
        week_start = data['week_start']
        comentario = data.get('comentario', '').strip()
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'error': 'Datos inválidos'}, status=400)

    # Verificar si la semana está cerrada
    week_start_date = date.fromisoformat(week_start)
    if SemanaCerrada.objects.filter(week_start=week_start_date).exists():
        return JsonResponse({'ok': False, 'error': 'Semana cerrada', 'cerrada': True}, status=403)

    try:
        emp = Employee.objects.get(pk=emp_id)
    except Employee.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Empleado no encontrado'}, status=404)

    ComentarioSemana.objects.update_or_create(
        employee=emp,
        tipo=tipo,
        week_start=week_start,
        defaults={'comentario': comentario},
    )
    return JsonResponse({'ok': True})
