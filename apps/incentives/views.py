import json
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, user_passes_test
from departments.models import Department
from apps.employee.models import Employee
from apps.incentives.constants import STATION_TEAMS
from apps.incentives.models import IncentivoRegistro, ComentarioSemana, SemanaCerrada, PresupuestoVenta, PresupuestoVentaSemanal, ConfiguracionIncentivos
from apps.incentives.sheets_service import leer_ventas_praxedis_colosio, SHEETS_TEAM_KEYS


def _parsear_seniority(seniority_raw):
    """Parsea 'DD/MM/YYYY' a date; devuelve None si no es válido."""
    from datetime import datetime
    if not seniority_raw:
        return None
    try:
        return datetime.strptime(seniority_raw.strip(), '%d/%m/%Y').date()
    except ValueError:
        return None


def _filtrar_empleados_por_semana(employees, week_end, inactivos_con_registro=None):
    """Filtra la lista de empleados para una semana:
    - Activos: excluye a quien ingresó después de week_end.
    - Inactivos: solo incluye a quien tiene registro en esa semana (ids en inactivos_con_registro).
    """
    if inactivos_con_registro is None:
        inactivos_con_registro = set()
    result = []
    for emp in employees:
        if emp.is_active:
            sd = _parsear_seniority(emp.seniority_raw)
            if sd is not None and sd > week_end:
                continue
            result.append(emp)
        else:
            if emp.id in inactivos_con_registro:
                result.append(emp)
    return result


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


def _get_rol_incentivos(user):
    """Devuelve el rol del usuario: 'admin', 'zona', 'gerente', 'operaciones', 'user' o None."""
    if user.is_superuser or user.is_staff:
        return 'admin'
    try:
        emp = Employee.objects.select_related('job_position', 'department').get(user=user)
        titulo = (emp.job_position.title if emp.job_position else '')
        titulo_lower = titulo.lower()
        dept_nombre = (emp.department.name if emp.department else '').lower()
        if 'supervisor de nóminas' in titulo_lower or 'supervisor de nominas' in titulo_lower or 'nomina' in dept_nombre:
            return 'admin'
        if 'jefe de zona' in titulo_lower:
            return 'zona'
        if 'gerente de estaci' in titulo_lower or 'subgerente de estaci' in titulo_lower:
            return 'gerente'
        if titulo == 'Gerente De Operaciones' and 'aqua car club' not in (emp.company or '').lower():
            return 'operaciones'
    except Employee.DoesNotExist:
        pass
    if user.has_perm('incentives.Modulo_incentivos'):
        return 'user'
    return None


@login_required
def incentives_dashboard(request):
    if request.user.is_superuser or request.user.is_staff:
        return redirect('incentives_dashboard_admin')

    es_gerente = False
    es_jefe_zona = False
    es_gerente_ops = False
    es_nominas = False

    try:
        emp = Employee.objects.select_related('job_position', 'department').get(user=request.user)
        titulo = emp.job_position.title if emp.job_position else ''
        titulo_lower = titulo.lower()
        dept_nombre = (emp.department.name if emp.department else '').lower()
        es_nominas = 'supervisor de nóminas' in titulo_lower or 'supervisor de nominas' in titulo_lower or 'nomina' in dept_nombre
        es_gerente = 'gerente de estaci' in titulo_lower or 'subgerente de estaci' in titulo_lower
        es_jefe_zona = 'jefe de zona' in titulo_lower
        es_gerente_ops = (
            titulo == 'Gerente De Operaciones'
            and 'aqua car club' not in (emp.company or '').lower()
        )
    except Employee.DoesNotExist:
        pass

    # Otorgar permiso automáticamente a roles que lo justifican por puesto
    if es_nominas or es_gerente or es_jefe_zona or es_gerente_ops:
        _otorgar_permiso_incentivos(request.user)
        if es_nominas:
            return redirect('incentives_dashboard_admin')
        if es_gerente:
            return redirect('incentives_dashboard_manager')
        if es_jefe_zona:
            return redirect('incentives_dashboard_zona')
        return redirect('incentives_dashboard_operaciones')

    # Para el resto, requiere permiso asignado manualmente
    if not request.user.has_perm('incentives.Modulo_incentivos'):
        return redirect('home')

    return redirect('incentives_dashboard_user')


@login_required
def incentives_dashboard_admin(request):
    if _get_rol_incentivos(request.user) != 'admin':
        return redirect('incentives_dashboard')
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
    from apps.incentives.constants import EXCEL_ORDER_LOOKUP

    teams = {
        team_key: {'display': display_name, 'employees': [], 'gerente': None, 'subgerentes': []}
        for team_key, display_name in STATION_TEAMS.items()
    }

    # IDs de empleados inactivos que tienen registro en esta semana (para mostrarlos igual)
    inactivos_con_registro = set(
        IncentivoRegistro.objects
        .filter(fecha__range=(week_start, week_end), employee__is_active=False,
                employee__team__in=STATION_TEAMS.keys())
        .values_list('employee_id', flat=True)
    )

    from django.db.models import Q
    employees = _filtrar_empleados_por_semana(
        _deduplicar_por_tsa(list(
            Employee.objects
            .filter(team__in=STATION_TEAMS.keys())
            .filter(Q(is_active=True) | Q(id__in=inactivos_con_registro))
            .select_related('job_position')
            .order_by('last_name', 'first_name')
        )),
        week_end,
        inactivos_con_registro,
    )

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
        elif 'subgerente de estaci' in titulo:
            teams[team_key]['subgerentes'].append(f"{emp.first_name} {emp.last_name}".strip())

    dept_data = sorted(
        [
            {
                'team': data['display'],
                'gerente': data['gerente'],
                'subgerentes': data['subgerentes'],
                'employees': data['employees'],
                'tiene_captura': any(getattr(emp, 'incentivo_count', 0) > 0 for emp in data['employees']),
                '_tk': tk,
            }
            for tk, data in teams.items()
        ],
        key=lambda x: EXCEL_ORDER_LOOKUP.get(x['_tk'], (9999, x['team']))[0]
    )

    periodo_cerrado = SemanaCerrada.objects.filter(week_start=week_start).exists()

    # Presupuesto global: suma de todos los incentivos de la semana
    registros_semana = (
        IncentivoRegistro.objects
        .filter(employee_id__in=emp_ids, fecha__range=(week_start, week_end))
        .values('employee_id', 'tipo')
        .annotate(count=Count('id'))
    )
    cfg = ConfiguracionIncentivos.get()
    presupuesto_global = 0
    for r in registros_semana:
        if r['tipo'] == 'Diesel':
            presupuesto_global += r['count'] * cfg.diesel_por_dia
        elif r['tipo'] == 'Encargado':
            presupuesto_global += cfg.encargado_primer_dia + (r['count'] - 1) * cfg.encargado_incremento if r['count'] > 0 else 0

    estaciones_con_captura = sum(
        1 for item in dept_data
        if any(getattr(emp, 'incentivo_count', 0) > 0 for emp in item['employees'])
    )
    total_estaciones = len(dept_data)

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
        'estaciones_con_captura': estaciones_con_captura,
        'total_estaciones': total_estaciones,
        'cfg': cfg,
    })


@login_required
def incentives_dashboard_zona(request):
    if _get_rol_incentivos(request.user) != 'zona':
        return redirect('incentives_dashboard')
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
    from apps.incentives.constants import EXCEL_ORDER_LOOKUP

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
        team_key: {'display': STATION_TEAMS[team_key], 'employees': [], 'gerente': None, 'subgerentes': []}
        for team_key in teams_del_jefe
    }

    from django.db.models import Q
    inactivos_con_registro_zona = set(
        IncentivoRegistro.objects
        .filter(fecha__range=(week_start, week_end), employee__is_active=False,
                employee__team__in=teams_del_jefe)
        .values_list('employee_id', flat=True)
    )
    employees = _filtrar_empleados_por_semana(
        _deduplicar_por_tsa(list(
            Employee.objects
            .filter(team__in=teams_del_jefe)
            .filter(Q(is_active=True) | Q(id__in=inactivos_con_registro_zona))
            .select_related('job_position')
            .order_by('last_name', 'first_name')
        )),
        week_end,
        inactivos_con_registro_zona,
    )

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
        elif 'subgerente de estaci' in titulo:
            teams[team_key]['subgerentes'].append(f"{emp.first_name} {emp.last_name}".strip())

    dept_data = sorted(
        [
            {
                'team': data['display'],
                'gerente': data['gerente'],
                'subgerentes': data['subgerentes'],
                'employees': data['employees'],
                'tiene_captura': any(getattr(emp, 'incentivo_count', 0) > 0 for emp in data['employees']),
                '_tk': tk,
            }
            for tk, data in teams.items()
        ],
        key=lambda x: EXCEL_ORDER_LOOKUP.get(x['_tk'], (9999, x['team']))[0]
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
        'cfg': ConfiguracionIncentivos.get(),
    })


@login_required
def incentives_dashboard_manager(request):
    if _get_rol_incentivos(request.user) != 'gerente':
        return redirect('incentives_dashboard')
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
        'cfg': ConfiguracionIncentivos.get(),
    })


@login_required
def incentives_dashboard_user(request):
    if _get_rol_incentivos(request.user) != 'user':
        return redirect('incentives_dashboard')
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
        venta_registro = IncentivoRegistro.objects.filter(
            employee=emp,
            tipo='Venta',
            fecha__range=(week_start, week_end),
        ).values('monto').first()
        venta_ganada = venta_registro is not None
        venta_monto = int(venta_registro['monto']) if venta_registro and venta_registro['monto'] else None
        mistery_reg = IncentivoRegistro.objects.filter(
            employee=emp,
            tipo='Mistery',
            fecha__range=(week_start, week_end),
        ).values('monto').first()
        mistery_ganada = mistery_reg is not None
        mistery_monto = int(mistery_reg['monto']) if mistery_reg and mistery_reg['monto'] else 0
    except Employee.DoesNotExist:
        diesel_fechas = set()
        diesel_dias = 0
        encargado_fechas = set()
        encargado_dias = 0
        venta_ganada = False
        venta_monto = None
        mistery_ganada = False
        mistery_monto = 0

    cfg = ConfiguracionIncentivos.get()
    diesel_total = diesel_dias * cfg.diesel_por_dia
    encargado_total = (cfg.encargado_primer_dia + (encargado_dias - 1) * cfg.encargado_incremento) if encargado_dias > 0 else 0
    gran_total = diesel_total + encargado_total + (venta_monto or 0) + mistery_monto

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
        'venta_ganada': venta_ganada,
        'venta_monto': venta_monto,
        'mistery_ganada': mistery_ganada,
        'mistery_monto': mistery_monto,
        'otros_tipos': ['ECV', 'Auditoría', 'Rotación', 'Inventario', 'Otros'],
    })


@login_required
def incentives_dashboard_operaciones(request):
    if _get_rol_incentivos(request.user) != 'operaciones':
        return redirect('incentives_dashboard')
    from datetime import date, timedelta
    import calendar
    from apps.incentives.constants import STATION_TEAMS, EXCEL_ORDER_LOOKUP

    today = date.today()
    lunes_hoy = today - timedelta(days=today.weekday())
    domingo_hoy = lunes_hoy + timedelta(days=6)

    # ── Rango de fechas ───────────────────────────────────────────────────────
    if 'reset' in request.GET:
        request.session.pop('incentivos_ops_fecha_ini', None)
        request.session.pop('incentivos_ops_fecha_fin', None)

    if 'fecha_ini' in request.GET and 'fecha_fin' in request.GET:
        try:
            fecha_ini = date.fromisoformat(request.GET['fecha_ini'])
            fecha_fin = date.fromisoformat(request.GET['fecha_fin'])
            if fecha_fin < fecha_ini:
                fecha_ini, fecha_fin = fecha_fin, fecha_ini
            request.session['incentivos_ops_fecha_ini'] = fecha_ini.isoformat()
            request.session['incentivos_ops_fecha_fin'] = fecha_fin.isoformat()
        except ValueError:
            fecha_ini = lunes_hoy
            fecha_fin = domingo_hoy
    else:
        saved_ini = request.session.get('incentivos_ops_fecha_ini')
        saved_fin = request.session.get('incentivos_ops_fecha_fin')
        if saved_ini and saved_fin:
            try:
                fecha_ini = date.fromisoformat(saved_ini)
                fecha_fin = date.fromisoformat(saved_fin)
            except ValueError:
                fecha_ini = lunes_hoy
                fecha_fin = domingo_hoy
        else:
            fecha_ini = lunes_hoy
            fecha_fin = domingo_hoy

    dias_total_rango = (fecha_fin - fecha_ini).days + 1
    semana_num  = fecha_ini.isocalendar()[1]
    semana_year = fecha_ini.isocalendar()[0]

    # ── Meses involucrados en el rango ────────────────────────────────────────
    meses_en_rango = []
    cur = date(fecha_ini.year, fecha_ini.month, 1)
    while cur <= fecha_fin:
        dias_mes = calendar.monthrange(cur.year, cur.month)[1]
        mes_fin_date = date(cur.year, cur.month, dias_mes)
        inicio_en_mes = max(fecha_ini, cur)
        fin_en_mes = min(fecha_fin, mes_fin_date)
        dias_en_rango_mes = (fin_en_mes - inicio_en_mes).days + 1
        meses_en_rango.append({
            'mes': cur,
            'dias_mes': dias_mes,
            'dias_en_rango': dias_en_rango_mes,
        })
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)

    # ── Presupuestos por mes ──────────────────────────────────────────────────
    presupuestos_por_mes = {}
    for m in meses_en_rango:
        regs = PresupuestoVenta.objects.filter(mes=m['mes'])
        presupuestos_por_mes[m['mes']] = {r.team_key: r for r in regs}

    meses_sin_ppto = [m['mes'] for m in meses_en_rango if not presupuestos_por_mes.get(m['mes'])]

    # Mes principal: el que más días aporta al rango (para mostrar en columna "Presupuesto Mensual")
    mes_principal = max(meses_en_rango, key=lambda m: m['dias_en_rango'])['mes']

    # Mes por defecto para la carga: el primero sin presupuesto, o el mes principal
    mes_upload_default = meses_sin_ppto[0] if meses_sin_ppto else mes_principal

    # Todos los meses que ya tienen presupuesto cargado (para advertencia de sobreescritura)
    import json as _json
    _meses_cargados = (PresupuestoVenta.objects
                       .order_by('mes').values_list('mes', flat=True).distinct())
    meses_con_ppto_json = _json.dumps([m.strftime('%Y-%m') for m in _meses_cargados])

    # ── Construir filas ───────────────────────────────────────────────────────
    def excel_no_and_pos(tk):
        if tk in EXCEL_ORDER_LOOKUP:
            return EXCEL_ORDER_LOOKUP[tk]
        return (9999, tk)

    all_team_keys = set()
    for ppto in presupuestos_por_mes.values():
        all_team_keys.update(ppto.keys())

    rows = []
    totales_ppto = {k: 0 for k in ('pm_gas', 'pm_diesel', 'pm_total', 'ps_gas', 'ps_diesel', 'ps_total')}

    for team_key in sorted(all_team_keys, key=lambda tk: excel_no_and_pos(tk)[0]):
        ppto_principal = presupuestos_por_mes.get(mes_principal, {}).get(team_key)
        pm_gas = pm_diesel = pm_total = 0.0
        if ppto_principal:
            pm_gas    = float((ppto_principal.maxima or 0) + (ppto_principal.gasolina_super or 0))
            pm_diesel = float(ppto_principal.diesel or 0)
            pm_total  = float(ppto_principal.total or 0)

        # Presupuesto del periodo: override semanal tiene prioridad
        semana_ini_lunes = fecha_ini - timedelta(days=fecha_ini.weekday())
        override_sem = PresupuestoVentaSemanal.objects.filter(
            team_key=team_key, semana=semana_ini_lunes,
        ).first()
        if override_sem:
            ps_gas    = round(float(override_sem.gas))
            ps_diesel = round(float(override_sem.diesel))
            ps_total  = ps_gas + ps_diesel
            tiene_override = True
        else:
            ps_gas_f = ps_diesel_f = 0.0
            for m in meses_en_rango:
                ppto = presupuestos_por_mes.get(m['mes'], {}).get(team_key)
                if ppto and m['dias_mes'] > 0:
                    m_gas    = float((ppto.maxima or 0) + (ppto.gasolina_super or 0))
                    m_diesel = float(ppto.diesel or 0)
                    ps_gas_f    += (m_gas    / m['dias_mes']) * m['dias_en_rango']
                    ps_diesel_f += (m_diesel / m['dias_mes']) * m['dias_en_rango']
            ps_gas    = round(ps_gas_f)
            ps_diesel = round(ps_diesel_f)
            ps_total  = ps_gas + ps_diesel
            tiene_override = False

        _, excel_no = excel_no_and_pos(team_key)
        row = {
            'team_key':      team_key,
            'codigo':        excel_no,
            'nombre':        STATION_TEAMS.get(team_key, team_key),
            'pm_gas':        pm_gas,    'pm_diesel': pm_diesel, 'pm_total': pm_total,
            'ps_gas':        ps_gas,    'ps_diesel': ps_diesel, 'ps_total': ps_total,
            'tiene_override': tiene_override,
        }
        rows.append(row)
        for k in totales_ppto:
            totales_ppto[k] += row[k]

    return render(request, 'incentives/operaciones/incentives_dashboard_operaciones.html', {
        'fecha_ini':          fecha_ini,
        'fecha_fin':          fecha_fin,
        'dias_total_rango':   dias_total_rango,
        'semana_num':         semana_num,
        'semana_year':        semana_year,
        'today':              today,
        'meses_en_rango':     meses_en_rango,
        'mes_principal':      mes_principal,
        'mes_upload_default': mes_upload_default,
        'meses_sin_ppto':     meses_sin_ppto,
        'meses_con_ppto_json': meses_con_ppto_json,
        'rows':               rows,
        'totales_ppto':       totales_ppto,
        'semana_override':    (fecha_ini - timedelta(days=fecha_ini.weekday())).isoformat(),
    })


# ── AJAX ────────────────────────────────────────────────────────────────────

@login_required
def ventas_sg12_json(request):
    """Devuelve ventas semanales desde ControlGas en JSON (para carga asíncrona)."""
    if _get_rol_incentivos(request.user) != 'operaciones':
        return JsonResponse({'ok': False, 'error': 'Sin permiso'}, status=403)

    from datetime import date
    from django.db import connection
    from django.core.cache import cache
    from apps.incentives.constants import SG12_COD_TO_TEAM_KEY

    try:
        semana_ini = date.fromisoformat(request.GET['semana_ini'])
        semana_fin = date.fromisoformat(request.GET['semana_fin'])
    except (KeyError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Parámetros inválidos'}, status=400)

    cache_key = f"ventas_sg12_v10_{semana_ini}_{semana_fin}"
    ventas = cache.get(cache_key)
    if ventas is None:
        ventas = {}
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        EstacionCod,
                        ROUND(SUM(CASE WHEN LOWER(Producto) NOT LIKE %s THEN Cantidad ELSE 0 END), 0),
                        ROUND(SUM(CASE WHEN LOWER(Producto) LIKE %s     THEN Cantidad ELSE 0 END), 0),
                        ROUND(SUM(Cantidad), 0)
                    FROM SG12.dbo.VVentasGlobalesGas WITH (NOLOCK)
                    WHERE Fecha BETWEEN %s AND %s
                    GROUP BY EstacionCod
                """, ['%diesel%', '%diesel%', semana_ini.isoformat(), semana_fin.isoformat()])
                for estacion_cod, gas, diesel, total in cursor.fetchall():
                    tk = SG12_COD_TO_TEAM_KEY.get(estacion_cod)
                    if not tk:
                        continue
                    ventas[tk] = {
                        'gas':    int(gas or 0),
                        'diesel': int(diesel or 0),
                        'total':  int(total or 0),
                    }
            cache.set(cache_key, ventas, timeout=3600)
        except Exception as e:
            return JsonResponse({'ok': False, 'error': str(e)})

    # Complementar con datos de Google Sheets para Praxedis y Colosio
    sheets_cache_key = f"ventas_sheets_v1_{semana_ini}"
    sheets_ventas = cache.get(sheets_cache_key)
    sheets_error = None
    if sheets_ventas is None:
        sheets_ventas, sheets_error = leer_ventas_praxedis_colosio(semana_ini)
        if not sheets_error:
            cache.set(sheets_cache_key, sheets_ventas, timeout=3600)
    for tk, sv in sheets_ventas.items():
        ventas[tk] = {'gas': sv['gas'], 'diesel': sv['diesel'], 'total': sv['total']}

    return JsonResponse({
        'ok': True,
        'ventas': ventas,
        'sheets_error': sheets_error,
    })

@login_required
@require_POST
def parsear_excel_ventas(request):
    """Recibe un Excel de presupuesto de ventas, lo parsea y devuelve vista previa."""
    if _get_rol_incentivos(request.user) != 'operaciones':
        return JsonResponse({'ok': False, 'error': 'Sin permiso'}, status=403)

    archivo = request.FILES.get('archivo')
    if not archivo:
        return JsonResponse({'ok': False, 'error': 'No se recibió archivo'}, status=400)

    try:
        import openpyxl
        from apps.incentives.constants import EXCEL_CODE_TO_TEAM_KEY
        wb = openpyxl.load_workbook(archivo, data_only=True)
        ws = wb.active

        filas = []
        for row in ws.iter_rows(min_row=4, values_only=True):
            codigo = row[0]
            nombre = row[1]
            if codigo is None and nombre is None:
                continue

            # openpyxl devuelve celdas numéricas como float (ej. 4188.0); convertir a entero primero
            if isinstance(codigo, float):
                codigo = str(int(codigo))
            else:
                codigo = str(codigo).strip() if codigo is not None else ''
            nombre = str(nombre).strip() if nombre is not None else ''

            def to_num(val):
                if val is None or val == '' or val == '—':
                    return 0
                try:
                    return float(val)
                except (ValueError, TypeError):
                    try:
                        # Limpiar formato de moneda: "$656,419" → 656419.0
                        limpio = str(val).replace('$', '').replace(',', '').strip()
                        return float(limpio) if limpio else 0
                    except (ValueError, TypeError):
                        return 0

            maxima = to_num(row[2] if len(row) > 2 else None)
            super_  = to_num(row[3] if len(row) > 3 else None)
            diesel  = to_num(row[4] if len(row) > 4 else None)
            total   = to_num(row[5] if len(row) > 5 else None)

            # Determinar team_key
            team_key = None
            if codigo in STATION_TEAMS:
                team_key = codigo
            elif codigo in EXCEL_CODE_TO_TEAM_KEY:
                team_key = EXCEL_CODE_TO_TEAM_KEY[codigo]

            filas.append({
                'codigo': codigo,
                'nombre_excel': nombre,
                'nombre_sistema': STATION_TEAMS.get(team_key, '—') if team_key else '—',
                'team_key': team_key,
                'maxima': maxima,
                'super': super_,
                'diesel': diesel,
                'total': total,
                'match': team_key is not None,
            })

        coincidencias = sum(1 for f in filas if f['match'])
        sin_match = len(filas) - coincidencias

        return JsonResponse({
            'ok': True,
            'filas': filas,
            'coincidencias': coincidencias,
            'sin_match': sin_match,
        })

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@login_required
def presupuesto_mes_json(request):
    """Devuelve los datos de presupuesto ya guardados para un mes dado (YYYY-MM)."""
    if _get_rol_incentivos(request.user) != 'operaciones':
        return JsonResponse({'ok': False, 'error': 'Sin permiso'}, status=403)

    mes_str = request.GET.get('mes', '')  # 'YYYY-MM'
    if not mes_str:
        return JsonResponse({'ok': False, 'error': 'Falta el parámetro mes'}, status=400)

    try:
        from datetime import date
        y, m = mes_str.split('-')
        mes_date = date(int(y), int(m), 1)
    except (ValueError, AttributeError):
        return JsonResponse({'ok': False, 'error': 'Formato de mes inválido'}, status=400)

    registros = PresupuestoVenta.objects.filter(mes=mes_date).order_by('team_key')
    filas = []
    for r in registros:
        nombre_sistema = STATION_TEAMS.get(r.team_key, r.team_key)
        filas.append({
            'codigo':         r.team_key,
            'nombre_excel':   nombre_sistema,
            'nombre_sistema': nombre_sistema,
            'team_key':       r.team_key,
            'maxima':         float(r.maxima or 0),
            'super':          float(r.gasolina_super or 0),
            'diesel':         float(r.diesel or 0),
            'total':          float(r.total or 0),
            'match':          True,
        })

    return JsonResponse({
        'ok':           True,
        'filas':        filas,
        'coincidencias': len(filas),
        'sin_match':    0,
    })


@login_required
@require_POST
def guardar_presupuesto_ventas(request):
    """Guarda (o reemplaza) el presupuesto mensual de ventas por estación."""
    if _get_rol_incentivos(request.user) != 'operaciones':
        return JsonResponse({'ok': False, 'error': 'Sin permiso'}, status=403)

    try:
        data = json.loads(request.body)
        mes_str = data['mes']           # 'YYYY-MM-DD'
        filas = data['filas']           # lista de objetos del parser
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'error': 'Datos inválidos'}, status=400)

    from datetime import date
    mes = date.fromisoformat(mes_str)

    guardados = 0
    for f in filas:
        if not f.get('match') or not f.get('team_key'):
            continue
        PresupuestoVenta.objects.update_or_create(
            team_key=f['team_key'],
            mes=mes,
            defaults={
                'maxima':         f.get('maxima', 0) or 0,
                'gasolina_super': f.get('super', 0) or 0,
                'diesel':         f.get('diesel', 0) or 0,
                'total':          f.get('total', 0) or 0,
                'subido_por':     request.user,
            },
        )
        guardados += 1

    return JsonResponse({'ok': True, 'guardados': guardados})


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


def _resumen_semana(week_start):
    """Calcula presupuesto global y estaciones con captura para una semana."""
    from datetime import timedelta
    from django.db.models import Count
    from collections import defaultdict

    week_end = week_start + timedelta(days=6)
    employees = _deduplicar_por_tsa(list(
        Employee.objects
        .filter(is_active=True, team__in=STATION_TEAMS.keys())
        .only('id', 'team')
    ))
    emp_ids = [emp.id for emp in employees]

    registros = (
        IncentivoRegistro.objects
        .filter(employee_id__in=emp_ids, fecha__range=(week_start, week_end))
        .values('employee_id', 'tipo')
        .annotate(count=Count('id'))
    )

    cfg = ConfiguracionIncentivos.get()
    presupuesto_global = 0
    emp_counts = defaultdict(int)
    for r in registros:
        emp_counts[r['employee_id']] += r['count']
        if r['tipo'] == 'Diesel':
            presupuesto_global += r['count'] * cfg.diesel_por_dia
        elif r['tipo'] == 'Encargado':
            presupuesto_global += (cfg.encargado_primer_dia + (r['count'] - 1) * cfg.encargado_incremento) if r['count'] > 0 else 0

    team_emp_map = defaultdict(list)
    for emp in employees:
        team_emp_map[emp.team.strip()].append(emp.id)

    estaciones_con_captura = sum(
        1 for emp_id_list in team_emp_map.values()
        if any(emp_counts.get(eid, 0) > 0 for eid in emp_id_list)
    )

    return {
        'presupuesto_global': presupuesto_global,
        'estaciones_con_captura': estaciones_con_captura,
        'total_estaciones': len(STATION_TEAMS),
    }


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

    cfg = ConfiguracionIncentivos.get()

    # Límite de días por semana para Diesel
    if tipo == 'Diesel':
        dias_semana = IncentivoRegistro.objects.filter(
            employee=emp,
            tipo='Diesel',
            fecha__range=(week_start, week_start + timedelta(days=6)),
        ).count()
        diesel_max = cfg.diesel_por_dia * cfg.diesel_max_dias
        if dias_semana >= cfg.diesel_max_dias:
            return JsonResponse(
                {'ok': False, 'error': f'Máximo {cfg.diesel_max_dias} días de Diesel por semana (${diesel_max})', 'max_diesel': True},
                status=400,
            )

    # Límite de días por semana para Encargado
    if tipo == 'Encargado':
        dias_semana = IncentivoRegistro.objects.filter(
            employee=emp,
            tipo='Encargado',
            fecha__range=(week_start, week_start + timedelta(days=6)),
        ).count()
        encargado_max = cfg.encargado_primer_dia + (cfg.encargado_max_dias - 1) * cfg.encargado_incremento
        if dias_semana >= cfg.encargado_max_dias:
            return JsonResponse(
                {'ok': False, 'error': f'Máximo {cfg.encargado_max_dias} días de Encargado por semana (${encargado_max})', 'max_encargado': True},
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
    ).values('tipo', 'fecha', 'monto')

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
            {
                'tipo': r['tipo'],
                'fecha': r['fecha'].isoformat(),
                'monto': int(r['monto']) if r['monto'] is not None else None,
            }
            for r in registros
        ],
        'comentarios': comentarios,
    })


@login_required
def resumen_global(request):
    """Devuelve presupuesto global y estatus de captura por estación para la semana dada."""
    from datetime import date, timedelta
    from django.db.models import Count
    from collections import defaultdict

    semana = request.GET.get('semana')
    if not semana:
        return JsonResponse({'ok': False, 'error': 'Falta parámetro semana'}, status=400)
    try:
        week_start = date.fromisoformat(semana)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Fecha inválida'}, status=400)

    week_end = week_start + timedelta(days=6)

    employees = _deduplicar_por_tsa(list(
        Employee.objects
        .filter(is_active=True, team__in=STATION_TEAMS.keys())
        .only('id', 'team')
    ))
    emp_ids = [emp.id for emp in employees]

    registros = (
        IncentivoRegistro.objects
        .filter(employee_id__in=emp_ids, fecha__range=(week_start, week_end))
        .values('employee_id', 'tipo')
        .annotate(count=Count('id'))
    )

    cfg = ConfiguracionIncentivos.get()
    presupuesto_global = 0
    emp_counts = defaultdict(int)
    for r in registros:
        emp_counts[r['employee_id']] += r['count']
        if r['tipo'] == 'Diesel':
            presupuesto_global += r['count'] * cfg.diesel_por_dia
        elif r['tipo'] == 'Encargado':
            presupuesto_global += (cfg.encargado_primer_dia + (r['count'] - 1) * cfg.encargado_incremento) if r['count'] > 0 else 0

    team_emp_map = defaultdict(list)
    for emp in employees:
        team_emp_map[emp.team.strip()].append(emp.id)

    estaciones_con_captura = sum(
        1 for emp_id_list in team_emp_map.values()
        if any(emp_counts.get(eid, 0) > 0 for eid in emp_id_list)
    )
    total_estaciones = len(STATION_TEAMS)

    return JsonResponse({
        'ok': True,
        'presupuesto_global': presupuesto_global,
        'estaciones_con_captura': estaciones_con_captura,
        'total_estaciones': total_estaciones,
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


def _calcular_monto_venta(team_key, seniority_raw, cfg=None):
    """Devuelve el monto del bono de Venta para un empleado, o None si no aplica.

    Reglas (fechas fijas de negocio):
    - seniority_raw >= 08/07/2026 → None (no aplica, fecha de corte fija)
    - Estación Bajío → cfg.venta_monto_bajio
    - Resto, antigüedad ≤ 2019 → cfg.venta_monto_antiguedad
    - Resto, antigüedad ≥ 2020 → cfg.venta_monto_regular
    """
    from datetime import datetime, date as _date
    from apps.incentives.constants import BAJIO_TEAM_KEYS

    if cfg is None:
        cfg = ConfiguracionIncentivos.get()

    CUTOFF = _date(2026, 7, 8)
    seniority_date = None
    if seniority_raw:
        try:
            seniority_date = datetime.strptime(seniority_raw.strip(), "%d/%m/%Y").date()
        except ValueError:
            pass

    if seniority_date is not None and seniority_date >= CUTOFF:
        return None

    if team_key in BAJIO_TEAM_KEYS:
        return cfg.venta_monto_bajio

    if seniority_date is not None and seniority_date.year <= 2019:
        return cfg.venta_monto_antiguedad

    return cfg.venta_monto_regular


def sync_venta_semana(request):
    """Sincroniza el bono de Venta según el estado verde/rojo de los Indicadores Operativos.

    Consulta SG12 para la semana indicada, compara contra PresupuestoVenta y:
      - Verde (venta real >= presupuesto): crea IncentivoRegistro tipo='Venta' para todos
        los empleados activos de esa estación usando week_start como fecha.
      - Rojo: elimina esos registros.
    Devuelve el estado por station_key para que el JS actualice la UI.
    """
    from datetime import date, timedelta
    from django.db import connection
    from django.core.cache import cache
    from apps.incentives.constants import SG12_COD_TO_TEAM_KEY
    import calendar as _calendar

    rol = _get_rol_incentivos(request.user)
    if not rol:
        return JsonResponse({'ok': False, 'error': 'Sin permiso'}, status=403)

    semana_str = request.GET.get('semana')
    if not semana_str:
        return JsonResponse({'ok': False, 'error': 'Falta parámetro semana'}, status=400)
    try:
        week_start = date.fromisoformat(semana_str)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Fecha inválida'}, status=400)

    week_end = week_start + timedelta(days=6)

    # Semana cerrada: no sincronizar (los registros ya están bloqueados)
    if SemanaCerrada.objects.filter(week_start=week_start).exists():
        return JsonResponse({'ok': True, 'cerrada': True, 'estaciones': {}})

    # Team keys según rol
    if rol in ('gerente', 'user'):
        try:
            emp = Employee.objects.get(user=request.user)
            tk = (emp.team or '').strip()
            team_keys = [tk] if tk in STATION_TEAMS else []
        except Employee.DoesNotExist:
            return JsonResponse({'ok': True, 'estaciones': {}})
    else:
        # admin, zona, operaciones — sincroniza todas las estaciones
        team_keys = list(STATION_TEAMS.keys())

    if not team_keys:
        return JsonResponse({'ok': True, 'estaciones': {}})

    # Ventas SG12 (reutiliza la misma caché que ventas_sg12_json)
    cache_key = f"ventas_sg12_v10_{week_start}_{week_end}"
    ventas = cache.get(cache_key)
    if ventas is None:
        ventas = {}
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        EstacionCod,
                        ROUND(SUM(CASE WHEN LOWER(Producto) NOT LIKE %s THEN Cantidad ELSE 0 END), 0),
                        ROUND(SUM(CASE WHEN LOWER(Producto) LIKE %s     THEN Cantidad ELSE 0 END), 0),
                        ROUND(SUM(Cantidad), 0)
                    FROM SG12.dbo.VVentasGlobalesGas WITH (NOLOCK)
                    WHERE Fecha BETWEEN %s AND %s
                    GROUP BY EstacionCod
                """, ['%diesel%', '%diesel%', week_start.isoformat(), week_end.isoformat()])
                for estacion_cod, gas, diesel, total in cursor.fetchall():
                    tk = SG12_COD_TO_TEAM_KEY.get(estacion_cod)
                    if tk:
                        ventas[tk] = {
                            'gas':    int(gas or 0),
                            'diesel': int(diesel or 0),
                            'total':  int(total or 0),
                        }
            cache.set(cache_key, ventas, timeout=3600)
        except Exception as e:
            return JsonResponse({'ok': False, 'error': str(e)})

    # Ventas Google Sheets para Praxedis y Colosio
    sheets_cache_key = f"ventas_sheets_v1_{week_start}"
    sheets_ventas = cache.get(sheets_cache_key)
    if sheets_ventas is None:
        sheets_ventas, _ = leer_ventas_praxedis_colosio(week_start)
        if sheets_ventas:
            cache.set(sheets_cache_key, sheets_ventas, timeout=3600)

    # Meses involucrados en la semana (para calcular presupuesto proporcional)
    def _meses_en_rango(ini, fin):
        meses = []
        cur = date(ini.year, ini.month, 1)
        while cur <= fin:
            dias_mes = _calendar.monthrange(cur.year, cur.month)[1]
            mes_fin = date(cur.year, cur.month, dias_mes)
            dias_en_rango = (min(fin, mes_fin) - max(ini, cur)).days + 1
            meses.append({'mes': cur, 'dias_mes': dias_mes, 'dias_en_rango': dias_en_rango})
            cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
        return meses

    meses = _meses_en_rango(week_start, week_end)
    cfg = ConfiguracionIncentivos.get()
    resultado = {}

    for team_key in team_keys:

        # ── Praxedis y Colosio: presupuesto y venta desde Google Sheets ──────
        if team_key in SHEETS_TEAM_KEYS:
            override = PresupuestoVentaSemanal.objects.filter(team_key=team_key, semana=week_start).first()
            if override:
                sv = sheets_ventas.get(team_key) if sheets_ventas else None
                vs_total = sv['total'] if sv else 0
                ps_total_ov = float(override.total)
                if ps_total_ov == 0:
                    resultado[team_key] = {'verde': None, 'sin_presupuesto': True, 'fuente': 'override'}
                    continue
                verde = vs_total >= ps_total_ov
                resultado[team_key] = {'verde': verde, 'vs': vs_total, 'ps': ps_total_ov, 'fuente': 'override'}
                empleados = list(Employee.objects.filter(is_active=True, team=team_key).values('id', 'seniority_raw'))
                if empleados:
                    if verde:
                        for emp in empleados:
                            monto = _calcular_monto_venta(team_key, emp['seniority_raw'], cfg)
                            if monto is None:
                                IncentivoRegistro.objects.filter(employee_id=emp['id'], tipo='Venta', fecha=week_start).delete()
                                continue
                            obj, created = IncentivoRegistro.objects.get_or_create(
                                employee_id=emp['id'], tipo='Venta', fecha=week_start,
                                defaults={'registrado_por': request.user, 'monto': monto},
                            )
                            if not created and obj.monto != monto:
                                obj.monto = monto
                                obj.save(update_fields=['monto'])
                    else:
                        IncentivoRegistro.objects.filter(
                            employee_id__in=[e['id'] for e in empleados],
                            tipo='Venta', fecha=week_start,
                        ).delete()
                continue

            sv = sheets_ventas.get(team_key) if sheets_ventas else None
            if not sv:
                resultado[team_key] = {'verde': None, 'sin_datos': True, 'fuente': 'sheets'}
                continue
            vs_total  = sv['total']
            ps_total  = sv['ppto_total']
            if ps_total == 0:
                resultado[team_key] = {'verde': None, 'sin_presupuesto': True, 'fuente': 'sheets'}
                continue
            verde = vs_total >= ps_total
            resultado[team_key] = {
                'verde': verde, 'vs': vs_total, 'ps': ps_total, 'fuente': 'sheets',
            }
            empleados = list(
                Employee.objects
                .filter(is_active=True, team=team_key)
                .values('id', 'seniority_raw')
            )
            if empleados:
                if verde:
                    for emp in empleados:
                        monto = _calcular_monto_venta(team_key, emp['seniority_raw'], cfg)
                        if monto is None:
                            IncentivoRegistro.objects.filter(
                                employee_id=emp['id'], tipo='Venta', fecha=week_start,
                            ).delete()
                            continue
                        obj, created = IncentivoRegistro.objects.get_or_create(
                            employee_id=emp['id'], tipo='Venta', fecha=week_start,
                            defaults={'registrado_por': request.user, 'monto': monto},
                        )
                        if not created and obj.monto != monto:
                            obj.monto = monto
                            obj.save(update_fields=['monto'])
                else:
                    IncentivoRegistro.objects.filter(
                        employee_id__in=[e['id'] for e in empleados],
                        tipo='Venta', fecha=week_start,
                    ).delete()
            continue

        # ── Resto de estaciones: override semanal tiene prioridad sobre proporcional mensual ──
        override = PresupuestoVentaSemanal.objects.filter(team_key=team_key, semana=week_start).first()
        if override:
            ps_total = float(override.total)
        else:
            ps_total = 0.0
            for m in meses:
                ppto = PresupuestoVenta.objects.filter(team_key=team_key, mes=m['mes']).first()
                if ppto and m['dias_mes'] > 0:
                    m_gas    = float((ppto.maxima or 0) + (ppto.gasolina_super or 0))
                    m_diesel = float(ppto.diesel or 0)
                    ps_total += ((m_gas + m_diesel) / m['dias_mes']) * m['dias_en_rango']

        if ps_total == 0:
            resultado[team_key] = {'verde': None, 'sin_presupuesto': True}
            continue

        venta_sg12 = ventas.get(team_key)
        if not venta_sg12:
            resultado[team_key] = {'verde': None, 'sin_datos': True}
            continue

        vs_total = venta_sg12['total']
        verde = vs_total >= round(ps_total)
        resultado[team_key] = {'verde': verde, 'vs': vs_total, 'ps': round(ps_total)}

        empleados = list(
            Employee.objects
            .filter(is_active=True, team=team_key)
            .values('id', 'seniority_raw')
        )
        if not empleados:
            continue

        if verde:
            for emp in empleados:
                monto = _calcular_monto_venta(team_key, emp['seniority_raw'], cfg)
                if monto is None:
                    IncentivoRegistro.objects.filter(
                        employee_id=emp['id'],
                        tipo='Venta',
                        fecha=week_start,
                    ).delete()
                    continue
                obj, created = IncentivoRegistro.objects.get_or_create(
                    employee_id=emp['id'],
                    tipo='Venta',
                    fecha=week_start,
                    defaults={'registrado_por': request.user, 'monto': monto},
                )
                if not created and obj.monto != monto:
                    obj.monto = monto
                    obj.save(update_fields=['monto'])
        else:
            IncentivoRegistro.objects.filter(
                employee_id__in=[e['id'] for e in empleados],
                tipo='Venta',
                fecha=week_start,
            ).delete()

    return JsonResponse({'ok': True, 'estaciones': resultado})


@login_required
def sync_mistery_semana(request):
    """Sincroniza el incentivo Mistery leyendo TGV2.dbo.AuditoriaMystery.

    Para la semana indicada (week_start=lunes):
      - date_mistery en TGV2 = domingo de esa semana (week_start + 6 días)
      - qualification >= 100 → crea IncentivoRegistro tipo='Mistery' para todos
        los empleados activos de esa estación (fecha=week_start).
      - qualification <  100 → elimina esos registros si existían.
    Estaciones sin dato en TGV2 no se tocan.
    """
    from datetime import date, timedelta
    from django.db import connections
    from apps.incentives.constants import SG12_COD_TO_TEAM_KEY

    rol = _get_rol_incentivos(request.user)
    if not rol:
        return JsonResponse({'ok': False, 'error': 'Sin permiso'}, status=403)

    semana_str = request.GET.get('semana')
    if not semana_str:
        return JsonResponse({'ok': False, 'error': 'Falta parámetro semana'}, status=400)
    try:
        week_start = date.fromisoformat(semana_str)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Fecha inválida'}, status=400)

    if SemanaCerrada.objects.filter(week_start=week_start).exists():
        return JsonResponse({'ok': True, 'cerrada': True, 'estaciones': {}})

    # date_mistery en TGV2 es el domingo de la semana ISO
    date_mistery = week_start + timedelta(days=6)

    # Leer calificaciones desde TGV2
    try:
        with connections['default'].cursor() as cursor:
            cursor.execute(
                "SELECT codgas, qualification FROM TGV2.dbo.AuditoriaMystery WHERE date_mistery = %s",
                [date_mistery.isoformat()],
            )
            rows = cursor.fetchall()
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})

    cfg = ConfiguracionIncentivos.get()
    resultado = {}

    for codgas, qualification in rows:
        team_key = SG12_COD_TO_TEAM_KEY.get(codgas)
        if not team_key:
            continue

        try:
            cal = float(qualification)
        except (TypeError, ValueError):
            continue

        ganador = cal >= 100
        resultado[team_key] = {'qualification': cal, 'ganador': ganador}

        empleados = list(
            Employee.objects.filter(is_active=True, team=team_key).values_list('id', flat=True)
        )
        if not empleados:
            continue

        if ganador:
            for emp_id in empleados:
                obj, created = IncentivoRegistro.objects.get_or_create(
                    employee_id=emp_id,
                    tipo='Mistery',
                    fecha=week_start,
                    defaults={'registrado_por': request.user, 'monto': cfg.mistery_monto},
                )
                if not created and obj.monto != cfg.mistery_monto_evaluado:
                    # Actualizar monto si cambió en config (sin tocar al evaluado)
                    if obj.monto != cfg.mistery_monto:
                        obj.monto = cfg.mistery_monto
                        obj.save(update_fields=['monto'])
        else:
            IncentivoRegistro.objects.filter(
                employee_id__in=empleados,
                tipo='Mistery',
                fecha=week_start,
            ).delete()

    return JsonResponse({'ok': True, 'estaciones': resultado})


@login_required
def presupuesto_semana_json(request):
    """Devuelve el override semanal de presupuesto para una estación y semana."""
    if _get_rol_incentivos(request.user) != 'operaciones':
        return JsonResponse({'ok': False, 'error': 'Sin permiso'}, status=403)

    from datetime import date
    tk = request.GET.get('tk', '').strip()
    semana_str = request.GET.get('semana', '')
    if not tk or not semana_str:
        return JsonResponse({'ok': False, 'error': 'Faltan parámetros'}, status=400)
    try:
        semana = date.fromisoformat(semana_str)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Fecha inválida'}, status=400)

    override = PresupuestoVentaSemanal.objects.filter(team_key=tk, semana=semana).first()
    return JsonResponse({
        'ok': True,
        'override': {
            'gas':    float(override.gas),
            'diesel': float(override.diesel),
            'total':  float(override.total),
        } if override else None,
    })


@login_required
@require_POST
def guardar_presupuesto_semana(request):
    """Guarda o elimina el override semanal de presupuesto para una estación."""
    if _get_rol_incentivos(request.user) != 'operaciones':
        return JsonResponse({'ok': False, 'error': 'Sin permiso'}, status=403)

    from datetime import date
    from decimal import Decimal
    try:
        data = json.loads(request.body)
        team_key  = data['team_key'].strip()
        semana_str = data['semana']
        gas    = float(data.get('gas', 0) or 0)
        diesel = float(data.get('diesel', 0) or 0)
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'error': 'Datos inválidos'}, status=400)

    try:
        semana = date.fromisoformat(semana_str)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Fecha inválida'}, status=400)

    if gas == 0 and diesel == 0:
        deleted, _ = PresupuestoVentaSemanal.objects.filter(team_key=team_key, semana=semana).delete()
        return JsonResponse({'ok': True, 'accion': 'eliminado' if deleted else 'sin_cambio'})

    PresupuestoVentaSemanal.objects.update_or_create(
        team_key=team_key,
        semana=semana,
        defaults={
            'gas':        Decimal(str(gas)),
            'diesel':     Decimal(str(diesel)),
            'subido_por': request.user,
        },
    )
    return JsonResponse({'ok': True, 'accion': 'guardado'})


@login_required
def mistery_evaluado_json(request):
    """Devuelve el emp_id del evaluado de Mistery para la semana dada (gerente de su dpto)."""
    rol = _get_rol_incentivos(request.user)
    if rol not in ('gerente', 'admin'):
        return JsonResponse({'ok': False, 'error': 'Sin permiso'}, status=403)

    from datetime import date
    semana_str = request.GET.get('semana')
    if not semana_str:
        return JsonResponse({'ok': False, 'error': 'Falta semana'}, status=400)
    try:
        week_start = date.fromisoformat(semana_str)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Fecha inválida'}, status=400)

    try:
        gerente_emp = Employee.objects.select_related('department').get(user=request.user)
        emp_ids = list(
            Employee.objects.filter(department=gerente_emp.department, is_active=True)
            .values_list('id', flat=True)
        )
    except Employee.DoesNotExist:
        return JsonResponse({'ok': True, 'evaluado_emp_id': None})

    cfg = ConfiguracionIncentivos.get()
    evaluado_id = IncentivoRegistro.objects.filter(
        employee_id__in=emp_ids,
        tipo='Mistery',
        fecha=week_start,
        monto=cfg.mistery_monto_evaluado,
    ).values_list('employee_id', flat=True).first()

    return JsonResponse({'ok': True, 'evaluado_emp_id': evaluado_id})


@login_required
@require_POST
def marcar_evaluado_mistery(request):
    """Marca a un empleado como la persona evaluada en Mistery ($500). Solo gerente."""
    rol = _get_rol_incentivos(request.user)
    if rol not in ('gerente', 'admin'):
        return JsonResponse({'ok': False, 'error': 'Sin permiso'}, status=403)

    try:
        data = json.loads(request.body)
        emp_id = data.get('emp_id')   # None/0 = deseleccionar
        week_start_str = data['week_start']
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'error': 'Datos inválidos'}, status=400)

    from datetime import date
    try:
        week_start = date.fromisoformat(week_start_str)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Fecha inválida'}, status=400)

    if SemanaCerrada.objects.filter(week_start=week_start).exists():
        return JsonResponse({'ok': False, 'error': 'Semana cerrada', 'cerrada': True}, status=403)

    try:
        gerente_emp = Employee.objects.select_related('department').get(user=request.user)
        emp_ids = list(
            Employee.objects.filter(department=gerente_emp.department, is_active=True)
            .values_list('id', flat=True)
        )
    except Employee.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Empleado no encontrado'}, status=404)

    cfg = ConfiguracionIncentivos.get()

    # Resetear todos a monto general
    IncentivoRegistro.objects.filter(
        employee_id__in=emp_ids,
        tipo='Mistery',
        fecha=week_start,
    ).update(monto=cfg.mistery_monto)

    # Si se seleccionó un evaluado, asignarle el monto especial
    if emp_id:
        try:
            emp_id = int(emp_id)
        except (ValueError, TypeError):
            return JsonResponse({'ok': False, 'error': 'ID inválido'}, status=400)
        if emp_id not in emp_ids:
            return JsonResponse({'ok': False, 'error': 'El empleado no pertenece al departamento'}, status=400)
        updated = IncentivoRegistro.objects.filter(
            employee_id=emp_id,
            tipo='Mistery',
            fecha=week_start,
        ).update(monto=cfg.mistery_monto_evaluado)
        if not updated:
            return JsonResponse({'ok': False, 'error': 'El empleado no tiene registro de Mistery esta semana'}, status=400)

    return JsonResponse({'ok': True, 'evaluado_emp_id': emp_id or None})


def _puede_configurar_incentivos(user):
    return (
        user.is_superuser
        or user.is_staff
        or user.has_perm('incentives.configurar_incentivos')
    )


@login_required
def configuracion_incentivos(request):
    """Vista para configurar los montos de incentivos (admin / nóminas)."""
    if not _puede_configurar_incentivos(request.user):
        return redirect('incentives_dashboard')

    cfg = ConfiguracionIncentivos.get()
    errores = []
    guardado = False

    if request.method == 'POST':
        try:
            encargado_primer_dia  = int(request.POST['encargado_primer_dia'])
            encargado_incremento  = int(request.POST['encargado_incremento'])
            encargado_max_dias    = int(request.POST['encargado_max_dias'])
            diesel_por_dia        = int(request.POST['diesel_por_dia'])
            diesel_max_dias       = int(request.POST['diesel_max_dias'])
            venta_monto_bajio      = int(request.POST['venta_monto_bajio'])
            venta_monto_antiguedad = int(request.POST['venta_monto_antiguedad'])
            venta_monto_regular    = int(request.POST['venta_monto_regular'])
            mistery_monto          = int(request.POST['mistery_monto'])
            mistery_monto_evaluado = int(request.POST['mistery_monto_evaluado'])
        except (KeyError, ValueError):
            errores.append('Todos los campos deben ser números enteros.')
        else:
            if encargado_primer_dia <= 0 or encargado_incremento <= 0:
                errores.append('Los montos deben ser mayores a cero.')
            if encargado_max_dias < 1 or encargado_max_dias > 7:
                errores.append('El máximo de días de Encargado debe estar entre 1 y 7.')
            if diesel_max_dias < 1 or diesel_max_dias > 7:
                errores.append('El máximo de días de Diesel debe estar entre 1 y 7.')
            if venta_monto_bajio <= 0 or venta_monto_antiguedad <= 0 or venta_monto_regular <= 0:
                errores.append('Los montos de Venta deben ser mayores a cero.')
            if mistery_monto < 0 or mistery_monto_evaluado < 0:
                errores.append('Los montos de Mistery no pueden ser negativos.')

        if not errores:
            cfg.encargado_primer_dia   = encargado_primer_dia
            cfg.encargado_incremento   = encargado_incremento
            cfg.encargado_max_dias     = encargado_max_dias
            cfg.diesel_por_dia         = diesel_por_dia
            cfg.diesel_max_dias        = diesel_max_dias
            cfg.venta_monto_bajio      = venta_monto_bajio
            cfg.venta_monto_antiguedad = venta_monto_antiguedad
            cfg.venta_monto_regular    = venta_monto_regular
            cfg.mistery_monto          = mistery_monto
            cfg.mistery_monto_evaluado = mistery_monto_evaluado
            cfg.actualizado_por        = request.user
            cfg.save()
            guardado = True

    # Calcular tope y escala para mostrar en la UI
    encargado_escala = [
        cfg.encargado_primer_dia + i * cfg.encargado_incremento
        for i in range(cfg.encargado_max_dias)
    ]
    encargado_tope = encargado_escala[-1] if encargado_escala else 0
    diesel_tope    = cfg.diesel_por_dia * cfg.diesel_max_dias

    return render(request, 'incentives/admin/configuracion_incentivos.html', {
        'cfg': cfg,
        'encargado_escala': encargado_escala,
        'encargado_tope': encargado_tope,
        'diesel_tope': diesel_tope,
        'errores': errores,
        'guardado': guardado,
    })
