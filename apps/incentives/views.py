import json
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, user_passes_test
from departments.models import Department
from apps.employee.models import Employee
from apps.incentives.constants import STATION_TEAMS
from apps.incentives.models import IncentivoRegistro, ComentarioSemana, SemanaCerrada, PresupuestoVenta


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
        emp = Employee.objects.select_related('job_position').get(user=user)
        titulo = (emp.job_position.title if emp.job_position else '')
        titulo_lower = titulo.lower()
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

    try:
        emp = Employee.objects.select_related('job_position').get(user=request.user)
        titulo = emp.job_position.title if emp.job_position else ''
        titulo_lower = titulo.lower()
        es_gerente = 'gerente de estaci' in titulo_lower or 'subgerente de estaci' in titulo_lower
        es_jefe_zona = 'jefe de zona' in titulo_lower
        es_gerente_ops = (
            titulo == 'Gerente De Operaciones'
            and 'aqua car club' not in (emp.company or '').lower()
        )
    except Employee.DoesNotExist:
        pass

    # Otorgar permiso automáticamente a roles que lo justifican por puesto
    if es_gerente or es_jefe_zona or es_gerente_ops:
        _otorgar_permiso_incentivos(request.user)
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
    if not (request.user.is_superuser or request.user.is_staff):
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

    teams = {
        team_key: {'display': display_name, 'employees': [], 'gerente': None, 'subgerentes': []}
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
            }
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
            }
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
        venta_ganada = IncentivoRegistro.objects.filter(
            employee=emp,
            tipo='Venta',
            fecha__range=(week_start, week_end),
        ).exists()
    except Employee.DoesNotExist:
        diesel_fechas = set()
        diesel_dias = 0
        encargado_fechas = set()
        encargado_dias = 0
        venta_ganada = False

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
        'venta_ganada': venta_ganada,
        'otros_tipos': ['Mistery', 'ECV', 'Auditoría', 'Rotación', 'Inventario', 'Otros'],
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

        # Presupuesto del periodo: suma proporcional de cada mes dentro del rango
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

        _, excel_no = excel_no_and_pos(team_key)
        row = {
            'team_key':  team_key,
            'codigo':    excel_no,
            'nombre':    STATION_TEAMS.get(team_key, team_key),
            'pm_gas':    pm_gas,    'pm_diesel': pm_diesel, 'pm_total': pm_total,
            'ps_gas':    ps_gas,    'ps_diesel': ps_diesel, 'ps_total': ps_total,
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

    return JsonResponse({'ok': True, 'ventas': ventas})

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

    presupuesto_global = 0
    emp_counts = defaultdict(int)
    for r in registros:
        emp_counts[r['employee_id']] += r['count']
        if r['tipo'] == 'Diesel':
            presupuesto_global += r['count'] * 50
        elif r['tipo'] == 'Encargado':
            presupuesto_global += (200 + (r['count'] - 1) * 100) if r['count'] > 0 else 0

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

    presupuesto_global = 0
    emp_counts = defaultdict(int)
    for r in registros:
        emp_counts[r['employee_id']] += r['count']
        if r['tipo'] == 'Diesel':
            presupuesto_global += r['count'] * 50
        elif r['tipo'] == 'Encargado':
            presupuesto_global += (200 + (r['count'] - 1) * 100) if r['count'] > 0 else 0

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


@login_required
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
    if rol == 'gerente':
        try:
            gerente_emp = Employee.objects.get(user=request.user)
            tk = (gerente_emp.team or '').strip()
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
    resultado = {}

    for team_key in team_keys:
        # Presupuesto proporcional a los días de la semana en cada mes
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

        # Sincronizar registros Venta en BD
        empleados_ids = list(
            Employee.objects
            .filter(is_active=True, team=team_key)
            .values_list('id', flat=True)
        )
        if not empleados_ids:
            continue

        if verde:
            for emp_id in empleados_ids:
                IncentivoRegistro.objects.get_or_create(
                    employee_id=emp_id,
                    tipo='Venta',
                    fecha=week_start,
                    defaults={'registrado_por': request.user},
                )
        else:
            IncentivoRegistro.objects.filter(
                employee_id__in=empleados_ids,
                tipo='Venta',
                fecha=week_start,
            ).delete()

    return JsonResponse({'ok': True, 'estaciones': resultado})
