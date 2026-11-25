import json
import logging
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, user_passes_test
from departments.models import Department
from apps.employee.models import Employee
from apps.incentives.constants import STATION_TEAMS, DIESEL_TEAM_KEYS
from apps.incentives.models import IncentivoRegistro, ComentarioSemana, SemanaCerrada, PresupuestoVenta, PresupuestoVentaSemanal, ConfiguracionIncentivos, CategoriaECV, IndicadorECV, PrenominaUpload, PrenominaRegistro, IncidenciaRegistro, IncidenciaUpload, IndicadorVentaSemanal, FaltanteEstacionSemanal
from apps.incentives.sheets_service import leer_ventas_praxedis_colosio, SHEETS_TEAM_KEYS

logger = logging.getLogger(__name__)

# Puestos que no aplican para incentivos aunque estén en una estación
PUESTOS_EXCLUIDOS_INCENTIVOS = (
    'Gerente de Unidad de Negocio',
    'Operador',
    'Auxiliar De Limpieza',
)


def _monto_proporcional_prenomina(employee_number, prenomina_lookup, monto_base, check_faltas=False):
    """Calcula el monto proporcional según días trabajados en prenómina.

    Regla: floor(dias_vacaciones) + floor(dias_incapacidad) por separado = días ausentes.
    Si el empleado no está en el lookup se devuelve el monto completo.
    Si check_faltas=True y el empleado tiene >= 1 falta, devuelve 0.
    """
    import math
    if employee_number not in prenomina_lookup:
        return monto_base
    dias_vac, dias_inc, dias_falta = prenomina_lookup[employee_number]
    if check_faltas and dias_falta >= 1:
        return 0
    dias_ausentes = math.floor(dias_vac) + math.floor(dias_inc)
    dias_trabajados = max(0, 6 - dias_ausentes)
    return round(monto_base / 6 * dias_trabajados)


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
    """Si un CURP aparece en dos empresas, conserva solo el registro de TSA.
    Si ninguno es TSA, gana el de start_date más reciente (puesto actual).
    """
    from datetime import date as _date
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
            elif not is_tsa and not existing_is_tsa:
                # Ninguno es TSA: gana el de start_date más reciente
                emp_start = emp.start_date or _date.min
                existing_start = result[idx].start_date or _date.min
                if emp_start > existing_start:
                    result[idx] = emp
    return result


def _score_mayor(alcance, umbral_min, umbral_obj, umbral_exc):
    """Score (0–120) para indicadores donde mayor valor es mejor.
    Interpolación lineal continua de umbral_min (→80) a umbral_exc (→120),
    igual que la fórmula del Excel ECV. Score 0 si alcance < umbral_min.
    umbral_obj no afecta el cálculo pero se conserva para compatibilidad.
    """
    if umbral_exc <= umbral_min:
        return 0.0
    calculo = 80.0 + (alcance - umbral_min) / (umbral_exc - umbral_min) * 40.0
    if calculo >= 120.0:
        return 120.0
    if calculo >= 80.0:
        return calculo
    return 0.0


def _score_menor(alcance, umbral_min, umbral_obj, umbral_exc):
    """Score (0–120) para indicadores donde menor valor es mejor. Escalonado por umbrales."""
    if alcance <= umbral_exc:
        return 120.0
    if alcance <= umbral_obj:
        return 100.0
    if alcance <= umbral_min:
        return 80.0
    return 0.0


def _calc_indicador(nombre, alcance_val, score_fn, inds_dict):
    """Calcula calculo (0–120) y valor (% ponderado) para un indicador ECV."""
    ind = inds_dict.get(nombre)
    umbrales = {
        'ponderacion':      float(ind.ponderacion)      if ind else None,
        'umbral_minimo':    float(ind.umbral_minimo)    if ind else None,
        'umbral_objetivo':  float(ind.umbral_objetivo)  if ind else None,
        'umbral_excelente': float(ind.umbral_excelente) if ind else None,
    }
    if ind is None or alcance_val is None:
        return {'alcance': alcance_val, 'calculo': None, 'valor': None, **umbrales}
    calculo = score_fn(
        alcance_val,
        float(ind.umbral_minimo),
        float(ind.umbral_objetivo),
        float(ind.umbral_excelente),
    )
    valor = round(calculo * float(ind.ponderacion) / 100, 4)
    return {'alcance': round(alcance_val, 2), 'calculo': round(calculo, 2), 'valor': valor, **umbrales}


def _calcular_incidencias_semana(week_start):
    """
    Calcula el indicador de incidencias en cortes para todas las estaciones
    en la semana dada.

    El upload que se usa es el de la semana ANTERIOR (week_start - 1 = domingo previo):
    las incidencias se envían el lunes siguiente al cierre de la semana anterior,
    por lo que al calcular el ECV de la semana N ya están disponibles las de N-1.

    Returns:
        {
          'semana_cargada': bool,
          'semana_domingo': date,
          'estaciones': {
              team_key: {
                  'count':  int,
                  'logro':  Decimal | None,   # None si la semana no está cargada
                  'puntos': Decimal | None,
              }
          }
        }
    """
    from datetime import timedelta
    from decimal import Decimal
    from django.db.models import Count as _Count
    from apps.incentives.constants import STATION_TEAMS, DIESEL_TEAM_KEYS

    # El ECV de la semana N usa el upload de la semana anterior (N-1):
    # las incidencias se reportan el lunes siguiente al cierre de semana,
    # así que al calcular el ECV de la semana N ya están disponibles las de N-1.
    semana_domingo = week_start - timedelta(days=1)
    semana_cargada = IncidenciaUpload.objects.filter(semana=semana_domingo).exists()

    # Conteo por estación para ese domingo
    conteos = {}
    if semana_cargada:
        conteos = {
            row['estacion_key']: row['total']
            for row in IncidenciaRegistro.objects
            .filter(semana=semana_domingo)
            .values('estacion_key')
            .annotate(total=_Count('id'))
        }

    # Cargar indicadores de incidencia (cat A y B)
    indicadores = {}
    for ind in IndicadorECV.objects.filter(nombre='incidencia').select_related('categoria'):
        indicadores[ind.categoria.nombre] = ind

    def _logro(n, ind):
        n = Decimal(n)
        if n <= ind.umbral_excelente:
            return Decimal('1.2')
        if n <= ind.umbral_objetivo:
            return Decimal('1.0')
        if n <= ind.umbral_minimo:
            return Decimal('0.8')
        return Decimal('0.0')

    estaciones = {}
    for team_key in STATION_TEAMS:
        cat = 'B' if team_key in DIESEL_TEAM_KEYS else 'A'
        ind = indicadores.get(cat)
        if ind is None:
            continue
        count = conteos.get(team_key, 0)
        if semana_cargada:
            logro  = _logro(count, ind)
            puntos = logro * (ind.ponderacion / Decimal('100'))
        else:
            logro  = None
            puntos = None
        estaciones[team_key] = {'count': count, 'logro': logro, 'puntos': puntos}

    return {
        'semana_cargada': semana_cargada,
        'semana_domingo': semana_domingo,
        'estaciones':     estaciones,
    }


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


def _teams_del_jefe_zona(jefe):
    """Devuelve el set de team_keys (estaciones) a cargo de un jefe de zona
    (o gerente de operaciones), siguiendo gerentes/subgerentes que le
    reportan directa o indirectamente. Compartida por incentives_dashboard_zona
    (qué estaciones mostrar) y exportar_ecv_excel (a qué estaciones limitar
    la descarga del Excel ECV cuando la pide un jefe de zona)."""
    from django.db.models import Q

    primer_apellido = jefe.last_name.split()[0] if jefe.last_name else ''
    busqueda = f"{jefe.first_name} {primer_apellido}".strip()

    # ── Nivel 1: gerentes que reportan directamente al jefe (por FK o texto) ──
    teams_con_gerente = set(
        Employee.objects.filter(
            team__in=STATION_TEAMS.keys(),
            job_position__title__icontains='gerente de estaci',
            is_active=True,
        ).exclude(
            job_position__title__icontains='sub'
        ).filter(
            Q(leader_fk=jefe) | Q(leader__icontains=busqueda)
        ).values_list('team', flat=True)
    )

    # ── Nivel 2: gerentes/subgerentes que reportan a un intermedio que reporta al jefe ──
    intermedios_ids = set(
        Employee.objects.filter(
            Q(leader_fk=jefe) | Q(leader__icontains=busqueda),
            is_active=True,
        ).values_list('id', flat=True)
    )
    teams_via_intermedio = set(
        Employee.objects.filter(
            team__in=STATION_TEAMS.keys(),
            job_position__title__icontains='gerente de estaci',
            leader_fk__in=intermedios_ids,
            is_active=True,
        ).values_list('team', flat=True)
    )

    # Estaciones sin gerente activo: buscar vía subgerentes (nivel 1 y 2)
    teams_con_gerente_any = set(
        Employee.objects.filter(
            team__in=STATION_TEAMS.keys(),
            job_position__title__icontains='gerente de estaci',
            is_active=True,
        ).exclude(
            job_position__title__icontains='sub'
        ).values_list('team', flat=True)
    )
    teams_sin_gerente = set(STATION_TEAMS.keys()) - teams_con_gerente_any
    teams_por_subgerente = set(
        Employee.objects.filter(
            team__in=teams_sin_gerente,
            job_position__title__icontains='subgerente de estaci',
            is_active=True,
        ).filter(
            Q(leader_fk=jefe) | Q(leader__icontains=busqueda) | Q(leader_fk__in=intermedios_ids)
        ).values_list('team', flat=True)
    )

    return teams_con_gerente | teams_via_intermedio | teams_por_subgerente


def _subgerente_tiene_gerente(user):
    """
    Retorna True si el usuario es subgerente Y su estación tiene un gerente activo.
    En ese caso el subgerente NO puede registrar incentivos (el gerente tiene prioridad).
    """
    try:
        emp = Employee.objects.select_related('job_position').get(user=user)
        titulo = (emp.job_position.title if emp.job_position else '').lower()
        if 'subgerente de estaci' not in titulo:
            return False
        team_key = (emp.team or '').strip()
        if not team_key:
            return False
        return Employee.objects.filter(
            team=team_key,
            is_active=True,
            job_position__title__icontains='gerente de estaci',
        ).exclude(
            job_position__title__icontains='subgerente',
        ).exists()
    except Employee.DoesNotExist:
        return False


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
    rol = _get_rol_incentivos(request.user)
    if rol not in ('admin', 'operaciones'):
        return redirect('incentives_dashboard')
    es_solo_lectura = False
    es_operaciones = (rol == 'operaciones')
    from datetime import date, timedelta
    from django.db.models import Count
    import json
    today = date.today()

    session_key = 'incentivos_admin_delta'
    if 'reset' in request.GET:
        request.session[session_key] = 0
    elif 'delta' in request.GET:
        request.session[session_key] = int(request.GET['delta'])

    delta = request.session.get(session_key, 0)

    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=delta)
    week_end = week_start + timedelta(days=6)
    days = [week_start + timedelta(days=i) for i in range(7)]

    # TODO: agregar cuando estén listos: 'Inventario', 'Otros'
    TIPOS = ['Diesel', 'Encargado', 'Venta', 'Mistery']
    # TODO: agregar cuando estén listos: 'Auditoría', 'Rotación', 'Inventario', 'Otros'
    TIPOS_MANAGER = ['ECV']
    from apps.incentives.constants import EXCEL_ORDER_LOOKUP

    teams = {
        team_key: {'display': display_name, 'employees': [], 'gerente': None, 'subgerentes': [], 'jefe_zona': None}
        for team_key, display_name in STATION_TEAMS.items()
    }

    # Nombres válidos de jefes de zona (por puesto), para validar el campo leader
    from django.db.models import Q as _Q
    _jefes_zona_nombres = set(
        f"{e.first_name} {e.last_name}".strip()
        for e in Employee.objects.filter(
            _Q(job_position__title__icontains='jefe de zona') |
            _Q(job_position__title__icontains='gerente de operaciones'),
            is_active=True,
        ).select_related('job_position')
    )

    def _resolver_jefe_zona(emp):
        """Sigue la cadena leader_fk hasta encontrar un jefe de zona (máx. 2 saltos)."""
        current = emp
        for _ in range(2):
            if current.leader_fk is None:
                break
            lf = current.leader_fk
            nombre = f"{lf.first_name} {lf.last_name}".strip()
            if nombre in _jefes_zona_nombres:
                return nombre
            # Cargar el siguiente nivel si no está ya cargado
            try:
                current = Employee.objects.select_related('leader_fk').get(pk=lf.pk)
            except Employee.DoesNotExist:
                break
        return None

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
            .exclude(job_position__title__in=PUESTOS_EXCLUIDOS_INCENTIVOS)
            .filter(Q(is_active=True) | Q(id__in=inactivos_con_registro))
            .select_related('job_position', 'leader_fk')
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
        if 'gerente de estaci' in titulo and 'subgerente' not in titulo:
            if teams[team_key]['gerente'] is None:
                teams[team_key]['gerente'] = f"{emp.first_name} {emp.last_name}".strip()
            if teams[team_key]['jefe_zona'] is None:
                teams[team_key]['jefe_zona'] = _resolver_jefe_zona(emp)
        elif 'subgerente de estaci' in titulo:
            teams[team_key]['subgerentes'].append(f"{emp.first_name} {emp.last_name}".strip())
            if teams[team_key]['jefe_zona'] is None:
                teams[team_key]['jefe_zona'] = _resolver_jefe_zona(emp)

    dept_data = sorted(
        [
            {
                'team': data['display'],
                'gerente': data['gerente'],
                'subgerentes': data['subgerentes'],
                'jefe_zona': data['jefe_zona'],
                'employees': data['employees'],
                'tiene_captura': any(getattr(emp, 'incentivo_count', 0) > 0 for emp in data['employees']),
                'team_key': tk,
                '_tk': tk,
                'excel_no': EXCEL_ORDER_LOOKUP.get(tk, (9999, ''))[1],
            }
            for tk, data in teams.items()
        ],
        key=lambda x: EXCEL_ORDER_LOOKUP.get(x['_tk'], (9999, x['team']))[0]
    )

    periodo_cerrado = SemanaCerrada.objects.filter(week_start=week_start).exists()

    # Presupuesto global: suma de todos los incentivos de la semana
    from django.db.models import Sum
    registros_semana = (
        IncentivoRegistro.objects
        .filter(employee_id__in=emp_ids, fecha__range=(week_start, week_end))
        .values('employee_id', 'tipo')
        .annotate(count=Count('id'), suma_monto=Sum('monto'))
    )
    cfg = ConfiguracionIncentivos.get()
    presupuesto_global = 0
    for r in registros_semana:
        if r['tipo'] == 'Diesel':
            presupuesto_global += r['count'] * cfg.diesel_por_dia
        elif r['tipo'] == 'Encargado':
            presupuesto_global += cfg.encargado_primer_dia + (r['count'] - 1) * cfg.encargado_incremento if r['count'] > 0 else 0
        elif r['tipo'] in ('Venta', 'Mistery'):
            presupuesto_global += int(r['suma_monto'] or 0)

    estaciones_con_captura = sum(
        1 for item in dept_data
        if any(getattr(emp, 'incentivo_count', 0) > 0 for emp in item['employees'])
    )
    total_estaciones = len(dept_data)

    semanas_con_prenomina = list(
        PrenominaUpload.objects.order_by('semana').values_list('semana', flat=True)
    )
    semanas_con_prenomina_json = json.dumps([s.isoformat() for s in semanas_con_prenomina])

    return render(request, 'incentives/admin/incentives_dashboard_admin.html', {
        'dept_data': dept_data,
        'week_start': week_start,
        'week_end': week_end,
        'today': today,
        'delta': delta,
        'days': days,
        'tipos': json.dumps(TIPOS),
        'tipos_manager': json.dumps(TIPOS_MANAGER),
        'periodo_cerrado': periodo_cerrado,
        'presupuesto_global': presupuesto_global,
        'estaciones_con_captura': estaciones_con_captura,
        'total_estaciones': total_estaciones,
        'cfg': cfg,
        'semanas_con_prenomina_json': semanas_con_prenomina_json,
        'diesel_team_keys_json': json.dumps(list(DIESEL_TEAM_KEYS)),
        'es_solo_lectura': es_solo_lectura,
        'es_operaciones': es_operaciones,
    })


@login_required
def incentives_dashboard_zona(request):
    if _get_rol_incentivos(request.user) != 'zona':
        return redirect('incentives_dashboard')
    from datetime import date, timedelta
    from django.db.models import Count, Q
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

    # TODO: agregar cuando estén listos: 'Inventario', 'Otros'
    TIPOS = ['Diesel', 'Encargado', 'Venta', 'Mistery']
    # TODO: agregar cuando estén listos: 'Auditoría', 'Rotación', 'Inventario', 'Otros'
    TIPOS_MANAGER = ['ECV']
    from apps.incentives.constants import EXCEL_ORDER_LOOKUP

    try:
        jefe = Employee.objects.select_related('job_position').get(user=request.user)
        teams_del_jefe = _teams_del_jefe_zona(jefe)
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
            .exclude(job_position__title__in=PUESTOS_EXCLUIDOS_INCENTIVOS)
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
                'team_key': tk,
                '_tk': tk,
                'excel_no': EXCEL_ORDER_LOOKUP.get(tk, (9999, ''))[1],
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
        'tipos_manager': json.dumps(TIPOS_MANAGER),
        'periodo_cerrado': periodo_cerrado,
        'cfg': ConfiguracionIncentivos.get(),
        'diesel_team_keys_json': json.dumps(list(DIESEL_TEAM_KEYS)),
    })


@login_required
def incentives_dashboard_manager(request):
    if _get_rol_incentivos(request.user) != 'gerente':
        return redirect('incentives_dashboard')
    sin_permiso_subgerente = _subgerente_tiene_gerente(request.user)
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
        team_key = (gerente_emp.team or '').strip()
        station_name = STATION_TEAMS.get(team_key, department.name if department else '')
        from django.db.models import Q
        inactivos_con_registro = set(
            IncentivoRegistro.objects
            .filter(fecha__range=(week_start, week_end), employee__is_active=False,
                    employee__team=team_key)
            .values_list('employee_id', flat=True)
        )
        colaboradores = _filtrar_empleados_por_semana(
            _deduplicar_por_tsa(list(
                Employee.objects
                .filter(team=team_key)
                .filter(Q(is_active=True) | Q(id__in=inactivos_con_registro))
                .select_related('job_position')
                .order_by('last_name', 'first_name')
            )),
            week_end,
            inactivos_con_registro,
        )
        tiene_diesel = team_key in DIESEL_TEAM_KEYS
        titulo_emp = (gerente_emp.job_position.title if gerente_emp.job_position else '').lower()
        es_subgerente_manager = 'subgerente' in titulo_emp
    except Employee.DoesNotExist:
        department = None
        team_key = ''
        station_name = ''
        colaboradores = Employee.objects.none()
        tiene_diesel = False
        es_subgerente_manager = False

    # TODO: agregar cuando estén listos: 'Auditoría', 'Rotación', 'Inventario', 'Otros'
    TIPOS = ['Diesel', 'Encargado', 'Venta', 'Mistery', 'ECV']

    periodo_cerrado = SemanaCerrada.objects.filter(week_start=week_start).exists()

    return render(request, 'incentives/manager/incentives_dashboard_manager.html', {
        'week_start': week_start,
        'week_end': week_end,
        'today': today,
        'delta': delta,
        'days': days,
        'department': department,
        'team_key': team_key,
        'tiene_diesel': tiene_diesel,
        'station_name': station_name,
        'colaboradores': colaboradores,
        'tipos': TIPOS,
        'periodo_cerrado': periodo_cerrado,
        'cfg': ConfiguracionIncentivos.get(),
        'sin_permiso_subgerente': sin_permiso_subgerente,
        'es_subgerente_manager': es_subgerente_manager,
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
        tiene_diesel = emp.team in DIESEL_TEAM_KEYS
        diesel_fechas = set(
            IncentivoRegistro.objects.filter(
                employee=emp,
                tipo='Diesel',
                fecha__range=(week_start, week_end),
            ).values_list('fecha', flat=True)
        ) if tiene_diesel else set()
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
        tiene_diesel = False
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
        'tiene_diesel': tiene_diesel,
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
        'otros_tipos': [],  # TODO: agregar cuando estén listos: 'Inventario', 'Otros'
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
def parsear_prenomina(request):
    """Recibe un Excel de prenómina, lo parsea y devuelve vista previa."""
    if _get_rol_incentivos(request.user) != 'admin':
        return JsonResponse({'ok': False, 'error': 'Sin permiso'}, status=403)

    archivo = request.FILES.get('archivo')
    if not archivo:
        return JsonResponse({'ok': False, 'error': 'No se recibió archivo'}, status=400)

    try:
        import csv, io

        def to_num(val):
            if val is None or val == '':
                return 0.0
            try:
                return float(str(val).replace(',', '').strip())
            except (ValueError, TypeError):
                return 0.0

        raw = archivo.read()
        for enc in ('utf-8-sig', 'latin-1', 'cp1252'):
            try:
                contenido = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            return JsonResponse({'ok': False, 'error': 'No se pudo detectar el encoding del archivo'}, status=400)
        reader = csv.reader(io.StringIO(contenido))
        next(reader, None)  # saltar encabezado

        filas = []
        for row in reader:
            if not any(row):
                continue
            numero = str(row[0]).strip() if len(row) > 0 else ''
            nombre = str(row[1]).strip() if len(row) > 1 else ''
            if not numero and not nombre:
                continue
            filas.append({
                'numero':              numero,
                'nombre':              nombre,
                'horas_ordinarias':    to_num(row[2]  if len(row) > 2  else ''),
                'horas_dobles':        to_num(row[3]  if len(row) > 3  else ''),
                'horas_triples':       to_num(row[4]  if len(row) > 4  else ''),
                'dias_falta':          to_num(row[5]  if len(row) > 5  else ''),
                'dias_permiso_sg':     to_num(row[6]  if len(row) > 6  else ''),
                'dias_vacaciones':     to_num(row[7]  if len(row) > 7  else ''),
                'dias_incapacidad':    to_num(row[8]  if len(row) > 8  else ''),
                'horas_festivo':       to_num(row[9]  if len(row) > 9  else ''),
                'horas_descanso_trab': to_num(row[10] if len(row) > 10 else ''),
                'equipo':              str(row[11]).strip() if len(row) > 11 else '',
                'puesto':              str(row[12]).strip() if len(row) > 12 else '',
                'estatus':             str(row[13]).strip() if len(row) > 13 else '',
                'neto':                to_num(row[14] if len(row) > 14 else ''),
            })

        return JsonResponse({'ok': True, 'total': len(filas), 'muestra': filas[:5], 'filas': filas})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def guardar_prenomina(request):
    """Guarda la prenómina parseada para una semana. Reemplaza si ya existía."""
    if _get_rol_incentivos(request.user) != 'admin':
        return JsonResponse({'ok': False, 'error': 'Sin permiso'}, status=403)

    try:
        from datetime import date
        data = json.loads(request.body)
        semana_str = data.get('semana')
        filas = data.get('filas', [])
        if not semana_str or not filas:
            return JsonResponse({'ok': False, 'error': 'Datos incompletos'}, status=400)
        semana = date.fromisoformat(semana_str)
        # Reemplazar si ya existe para esa semana
        PrenominaUpload.objects.filter(semana=semana).delete()
        upload = PrenominaUpload.objects.create(
            semana=semana,
            subido_por=request.user,
            total_registros=len(filas),
        )
        registros = [
            PrenominaRegistro(
                upload=upload,
                numero=f['numero'],
                nombre=f['nombre'],
                horas_ordinarias=f['horas_ordinarias'],
                horas_dobles=f['horas_dobles'],
                horas_triples=f['horas_triples'],
                dias_falta=f['dias_falta'],
                dias_permiso_sg=f['dias_permiso_sg'],
                dias_vacaciones=f['dias_vacaciones'],
                dias_incapacidad=f['dias_incapacidad'],
                horas_festivo=f['horas_festivo'],
                horas_descanso_trab=f['horas_descanso_trab'],
                equipo=f['equipo'],
                puesto=f['puesto'],
                estatus=f['estatus'],
                neto=f['neto'],
            )
            for f in filas
        ]
        PrenominaRegistro.objects.bulk_create(registros)

        # Recalcular montos de Mistery para esta semana según la prenómina recién guardada
        prenomina_lookup = {
            f['numero']: (float(f['dias_vacaciones']), float(f['dias_incapacidad']), float(f['dias_falta']))
            for f in filas
        }
        cfg = ConfiguracionIncentivos.get()
        emp_numbers = {
            e['id']: e['employee_number']
            for e in Employee.objects.values('id', 'employee_number')
        }
        # Recalcular Mistery
        mistery_regs = IncentivoRegistro.objects.filter(tipo='Mistery', fecha=semana)
        for reg in mistery_regs:
            if reg.monto == cfg.mistery_monto_evaluado:
                continue  # no tocar al evaluado
            monto = _monto_proporcional_prenomina(
                emp_numbers.get(reg.employee_id, ''), prenomina_lookup, cfg.mistery_monto, check_faltas=True,
            )
            if reg.monto != monto:
                reg.monto = monto
                reg.save(update_fields=['monto'])

        # Recalcular Venta
        emp_data = {
            e['id']: (e['employee_number'], e['team'], e['seniority_raw'])
            for e in Employee.objects.values('id', 'employee_number', 'team', 'seniority_raw')
        }
        venta_regs = IncentivoRegistro.objects.filter(tipo='Venta', fecha=semana)
        for reg in venta_regs:
            emp_num, team_key, seniority_raw = emp_data.get(reg.employee_id, ('', '', ''))
            monto_base = _calcular_monto_venta(team_key, seniority_raw, cfg)
            if monto_base is None:
                continue
            monto = _monto_proporcional_prenomina(emp_num, prenomina_lookup, monto_base)
            if reg.monto != monto:
                reg.monto = monto
                reg.save(update_fields=['monto'])

        return JsonResponse({'ok': True, 'total': len(registros)})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
def prenomina_semana_json(request):
    """Devuelve los registros de prenómina ya guardados para una semana dada."""
    if _get_rol_incentivos(request.user) != 'admin':
        return JsonResponse({'ok': False, 'error': 'Sin permiso'}, status=403)

    from datetime import date as date_type
    semana_str = request.GET.get('semana')
    if not semana_str:
        return JsonResponse({'ok': False, 'error': 'Falta parámetro semana'}, status=400)
    try:
        semana = date_type.fromisoformat(semana_str)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Fecha inválida'}, status=400)

    try:
        upload = PrenominaUpload.objects.get(semana=semana)
    except PrenominaUpload.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Sin datos para esa semana'}, status=404)

    registros = list(upload.registros.values(
        'numero', 'nombre', 'equipo', 'puesto', 'estatus',
        'horas_ordinarias', 'dias_falta', 'neto',
    ))
    for r in registros:
        r['horas_ordinarias'] = float(r['horas_ordinarias'])
        r['dias_falta']       = float(r['dias_falta'])
        r['neto']             = float(r['neto'])

    return JsonResponse({
        'ok': True,
        'total': upload.total_registros,
        'subido_el': upload.subido_el.strftime('%d/%m/%Y %H:%M'),
        'subido_por': upload.subido_por.get_full_name() if upload.subido_por else '—',
        'registros': registros,
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
    from django.db.models import Count, Sum
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
        .annotate(count=Count('id'), suma_monto=Sum('monto'))
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
        elif r['tipo'] in ('Venta', 'Mistery'):
            presupuesto_global += int(r['suma_monto'] or 0)

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
        forzar = bool(data.get('forzar', False))
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'error': 'Datos inválidos'}, status=400)

    # Subgerente bloqueado si su estación tiene gerente activo
    if _subgerente_tiene_gerente(request.user):
        return JsonResponse(
            {'ok': False, 'error': 'Tu estación tiene gerente asignado; solo el gerente puede registrar incentivos.'},
            status=403,
        )

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

    # Estaciones sin bomba de Diesel no pueden registrar ese incentivo
    if tipo == 'Diesel' and emp.team not in DIESEL_TEAM_KEYS:
        return JsonResponse(
            {'ok': False, 'error': 'Esta estación no tiene bono de Diesel'},
            status=400,
        )

    # Gerentes y subgerentes no reciben Diesel ni Mistery
    if tipo in ('Diesel', 'Mistery'):
        titulo_emp = (emp.job_position.title if emp.job_position else '').lower()
        if 'gerente de estaci' in titulo_emp or 'subgerente de estaci' in titulo_emp:
            return JsonResponse(
                {'ok': False, 'error': f'Gerentes y subgerentes no aplican para {tipo}'},
                status=400,
            )

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
        # Solo una persona por estación por día (advertencia, se puede forzar)
        if emp.team and not forzar:
            otro = IncentivoRegistro.objects.filter(
                tipo='Encargado',
                fecha=fecha_date,
                employee__team=emp.team,
            ).exclude(employee=emp).select_related('employee').first()
            if otro:
                nombre = f"{otro.employee.first_name} {otro.employee.last_name}".strip()
                return JsonResponse(
                    {'ok': False, 'error': f'Ya está marcado Encargado para {nombre} en esta fecha', 'duplicado_estacion': True},
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

    # Verificar si el empleado no califica para el bono de Venta por reglas de antigüedad
    venta_no_aplica = False
    ecv_venta = None
    try:
        emp_obj = Employee.objects.select_related('job_position').only(
            'team', 'seniority_raw', 'job_position__title'
        ).get(pk=emp_id)
        venta_no_aplica = (_calcular_monto_venta(emp_obj.team or '', emp_obj.seniority_raw) is None)
        # Para gerentes/subgerentes: devolver estado de venta desde DB (sin ir a SG12)
        titulo = (emp_obj.job_position.title if emp_obj.job_position else '').lower()
        if 'gerente de estaci' in titulo or 'subgerente de estaci' in titulo:
            ind = IndicadorVentaSemanal.objects.filter(
                team_key=(emp_obj.team or '').strip(),
                week_start=semana_date,
            ).first()
            if ind:
                ecv_venta = {
                    'verde_gas':    ind.verde_gas,
                    'verde_diesel': ind.verde_diesel,
                    'vs_gas':       ind.vs_gas,
                    'ps_gas':       ind.ps_gas,
                    'vs_diesel':    ind.vs_diesel,
                    'ps_diesel':    ind.ps_diesel,
                }
    except Employee.DoesNotExist:
        pass

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
        'venta_no_aplica': venta_no_aplica,
        'ecv_venta': ecv_venta,
    })


@login_required
def resumen_global(request):
    """Devuelve presupuesto global y estatus de captura por estación para la semana dada."""
    from datetime import date, timedelta
    from django.db.models import Count, Sum
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
        .annotate(count=Count('id'), suma_monto=Sum('monto'))
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
        elif r['tipo'] in ('Venta', 'Mistery'):
            presupuesto_global += int(r['suma_monto'] or 0)

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

    # Semana cerrada: solo lectura — calculamos el estado para el ECV pero no tocamos registros
    semana_cerrada = SemanaCerrada.objects.filter(week_start=week_start).exists()

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

    # Construir lookup de prenómina: employee_number → (dias_vacaciones, dias_incapacidad, dias_falta)
    prenomina_lookup = {}
    try:
        upload = PrenominaUpload.objects.get(semana=week_start)
        for reg in upload.registros.values('numero', 'dias_vacaciones', 'dias_incapacidad', 'dias_falta'):
            prenomina_lookup[reg['numero']] = (
                float(reg['dias_vacaciones']),
                float(reg['dias_incapacidad']),
                float(reg['dias_falta']),
            )
    except PrenominaUpload.DoesNotExist:
        pass

    emp_numbers = {
        e['id']: e['employee_number']
        for e in Employee.objects.values('id', 'employee_number')
    }

    for team_key in team_keys:

        # ── Praxedis y Colosio: presupuesto y venta desde Google Sheets ──────
        if team_key in SHEETS_TEAM_KEYS:
            override = PresupuestoVentaSemanal.objects.filter(team_key=team_key, semana=week_start).first()
            if override:
                sv = sheets_ventas.get(team_key) if sheets_ventas else None
                vs_total    = sv['total'] if sv else 0
                vs_gas      = sv['gas'] if sv else 0
                vs_diesel   = sv['diesel'] if sv else 0
                ps_total_ov  = float(override.total)
                ps_gas_ov    = float(override.gas)
                ps_diesel_ov = float(override.diesel)
                if ps_total_ov == 0:
                    resultado[team_key] = {'verde': None, 'sin_presupuesto': True, 'fuente': 'override'}
                    continue
                verde = vs_total >= ps_total_ov
                verde_gas    = (vs_gas >= ps_gas_ov)       if ps_gas_ov    > 0 else None
                verde_diesel = (vs_diesel >= ps_diesel_ov) if ps_diesel_ov > 0 else None
                resultado[team_key] = {
                    'verde': verde, 'vs': vs_total, 'ps': ps_total_ov, 'fuente': 'override',
                    'verde_gas': verde_gas, 'vs_gas': vs_gas, 'ps_gas': ps_gas_ov,
                    'verde_diesel': verde_diesel, 'vs_diesel': vs_diesel, 'ps_diesel': ps_diesel_ov,
                }
                if not semana_cerrada:
                    empleados = list(Employee.objects.filter(is_active=True, team=team_key).exclude(job_position__title__icontains='gerente de estaci').values('id', 'seniority_raw'))
                    if empleados:
                        if verde:
                            for emp in empleados:
                                monto_base = _calcular_monto_venta(team_key, emp['seniority_raw'], cfg)
                                if monto_base is None:
                                    IncentivoRegistro.objects.filter(employee_id=emp['id'], tipo='Venta', fecha=week_start).delete()
                                    continue
                                monto = _monto_proporcional_prenomina(
                                    emp_numbers.get(emp['id'], ''), prenomina_lookup, monto_base,
                                )
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
            vs_gas    = sv['gas']
            ps_gas    = sv['ppto_gas']
            vs_diesel = sv['diesel']
            ps_diesel = sv['ppto_diesel']
            if ps_total == 0:
                resultado[team_key] = {'verde': None, 'sin_presupuesto': True, 'fuente': 'sheets'}
                continue
            verde = vs_total >= ps_total
            verde_gas    = (vs_gas >= ps_gas)       if ps_gas    > 0 else None
            verde_diesel = (vs_diesel >= ps_diesel) if ps_diesel > 0 else None
            resultado[team_key] = {
                'verde': verde, 'vs': vs_total, 'ps': ps_total, 'fuente': 'sheets',
                'verde_gas': verde_gas, 'vs_gas': vs_gas, 'ps_gas': ps_gas,
                'verde_diesel': verde_diesel, 'vs_diesel': vs_diesel, 'ps_diesel': ps_diesel,
            }
            if not semana_cerrada:
                empleados = list(
                    Employee.objects
                    .filter(is_active=True, team=team_key)
                    .exclude(job_position__title__icontains='gerente de estaci')
                    .values('id', 'seniority_raw')
                )
                if empleados:
                    if verde:
                        for emp in empleados:
                            monto_base = _calcular_monto_venta(team_key, emp['seniority_raw'], cfg)
                            if monto_base is None:
                                IncentivoRegistro.objects.filter(
                                    employee_id=emp['id'], tipo='Venta', fecha=week_start,
                                ).delete()
                                continue
                            monto = _monto_proporcional_prenomina(
                                emp_numbers.get(emp['id'], ''), prenomina_lookup, monto_base,
                            )
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
            ps_total   = float(override.total)
            ps_gas     = float(override.gas)
            ps_diesel  = float(override.diesel)
        else:
            ps_total = ps_gas_f = ps_diesel_f = 0.0
            for m in meses:
                ppto = PresupuestoVenta.objects.filter(team_key=team_key, mes=m['mes']).first()
                if ppto and m['dias_mes'] > 0:
                    m_gas    = float((ppto.maxima or 0) + (ppto.gasolina_super or 0))
                    m_diesel = float(ppto.diesel or 0)
                    ps_total    += ((m_gas + m_diesel) / m['dias_mes']) * m['dias_en_rango']
                    ps_gas_f    += (m_gas    / m['dias_mes']) * m['dias_en_rango']
                    ps_diesel_f += (m_diesel / m['dias_mes']) * m['dias_en_rango']
            ps_gas    = round(ps_gas_f)
            ps_diesel = round(ps_diesel_f)

        if ps_total == 0:
            resultado[team_key] = {'verde': None, 'sin_presupuesto': True}
            continue

        venta_sg12 = ventas.get(team_key)
        if not venta_sg12:
            resultado[team_key] = {'verde': None, 'sin_datos': True}
            continue

        vs_total   = venta_sg12['total']
        vs_gas     = venta_sg12['gas']
        vs_diesel  = venta_sg12['diesel']
        verde      = vs_total >= round(ps_total)
        verde_gas  = (vs_gas >= ps_gas)    if ps_gas    > 0 else None
        verde_diesel = (vs_diesel >= ps_diesel) if ps_diesel > 0 else None
        resultado[team_key] = {
            'verde': verde, 'vs': vs_total, 'ps': round(ps_total),
            'verde_gas': verde_gas, 'vs_gas': vs_gas, 'ps_gas': round(ps_gas),
            'verde_diesel': verde_diesel, 'vs_diesel': vs_diesel, 'ps_diesel': round(ps_diesel),
        }

        if not semana_cerrada:
            empleados = list(
                Employee.objects
                .filter(is_active=True, team=team_key)
                .exclude(job_position__title__icontains='gerente de estaci')
                .values('id', 'seniority_raw')
            )
            if not empleados:
                continue

            if verde:
                for emp in empleados:
                    monto_base = _calcular_monto_venta(team_key, emp['seniority_raw'], cfg)
                    if monto_base is None:
                        IncentivoRegistro.objects.filter(
                            employee_id=emp['id'],
                            tipo='Venta',
                            fecha=week_start,
                        ).delete()
                        continue
                    monto = _monto_proporcional_prenomina(
                        emp_numbers.get(emp['id'], ''), prenomina_lookup, monto_base,
                    )
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

    # Persistir resultado en DB para que semana_data lo sirva instantáneamente
    for tk, est in resultado.items():
        IndicadorVentaSemanal.objects.update_or_create(
            team_key=tk,
            week_start=week_start,
            defaults={
                'verde_gas':    est.get('verde_gas'),
                'verde_diesel': est.get('verde_diesel'),
                'vs_gas':       est.get('vs_gas'),
                'ps_gas':       est.get('ps_gas'),
                'vs_diesel':    est.get('vs_diesel'),
                'ps_diesel':    est.get('ps_diesel'),
            },
        )

    return JsonResponse({'ok': True, 'cerrada': semana_cerrada, 'estaciones': resultado})


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

    # Semana cerrada: solo lectura — calculamos el estado para el ECV pero no tocamos registros
    semana_cerrada = SemanaCerrada.objects.filter(week_start=week_start).exists()

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

    if not semana_cerrada:
        # Construir lookup de prenómina: employee_number → (dias_vacaciones, dias_incapacidad, dias_falta)
        prenomina_lookup = {}
        try:
            upload = PrenominaUpload.objects.get(semana=week_start)
            for reg in upload.registros.values('numero', 'dias_vacaciones', 'dias_incapacidad', 'dias_falta'):
                prenomina_lookup[reg['numero']] = (
                    float(reg['dias_vacaciones']),
                    float(reg['dias_incapacidad']),
                    float(reg['dias_falta']),
                )
        except PrenominaUpload.DoesNotExist:
            pass

        emp_numbers = {
            e['id']: e['employee_number']
            for e in Employee.objects.values('id', 'employee_number')
        }

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

        if semana_cerrada:
            continue

        empleados = list(
            Employee.objects.filter(is_active=True, team=team_key)
            .exclude(job_position__title__icontains='gerente de estaci')
            .exclude(job_position__title__icontains='subgerente de estaci')
            .values_list('id', flat=True)
        )
        if not empleados:
            continue

        if ganador:
            for emp_id in empleados:
                monto = _monto_proporcional_prenomina(
                    emp_numbers.get(emp_id, ''), prenomina_lookup, cfg.mistery_monto, check_faltas=True,
                )
                obj, created = IncentivoRegistro.objects.get_or_create(
                    employee_id=emp_id,
                    tipo='Mistery',
                    fecha=week_start,
                    defaults={'registrado_por': request.user, 'monto': monto},
                )
                if not created and obj.monto != cfg.mistery_monto_evaluado:
                    if obj.monto != monto:
                        obj.monto = monto
                        obj.save(update_fields=['monto'])
        else:
            IncentivoRegistro.objects.filter(
                employee_id__in=empleados,
                tipo='Mistery',
                fecha=week_start,
            ).delete()

    return JsonResponse({'ok': True, 'cerrada': semana_cerrada, 'estaciones': resultado})


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
    """Devuelve el emp_id del evaluado de Mistery para la semana dada."""
    rol = _get_rol_incentivos(request.user)
    if rol not in ('gerente', 'admin', 'zona'):
        return JsonResponse({'ok': False, 'error': 'Sin permiso'}, status=403)

    from datetime import date
    semana_str = request.GET.get('semana')
    team_key   = request.GET.get('team_key', '').strip()  # admin puede pasar team_key
    if not semana_str:
        return JsonResponse({'ok': False, 'error': 'Falta semana'}, status=400)
    try:
        week_start = date.fromisoformat(semana_str)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Fecha inválida'}, status=400)

    if rol in ('admin', 'zona') and team_key:
        emp_ids = list(
            Employee.objects.filter(team=team_key, is_active=True)
            .values_list('id', flat=True)
        )
    else:
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
    """Marca a un empleado como la persona evaluada en Mistery ($500). Gerente, admin o zona."""
    rol = _get_rol_incentivos(request.user)
    if rol not in ('gerente', 'admin', 'zona'):
        return JsonResponse({'ok': False, 'error': 'Sin permiso'}, status=403)

    try:
        data = json.loads(request.body)
        emp_id         = data.get('emp_id')        # None/0 = deseleccionar
        week_start_str = data['week_start']
        team_key       = data.get('team_key', '').strip()  # admin pasa team_key
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'error': 'Datos inválidos'}, status=400)

    from datetime import date
    try:
        week_start = date.fromisoformat(week_start_str)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Fecha inválida'}, status=400)

    if SemanaCerrada.objects.filter(week_start=week_start).exists():
        return JsonResponse({'ok': False, 'error': 'Semana cerrada', 'cerrada': True}, status=403)

    if rol in ('admin', 'zona') and team_key:
        emp_ids = list(
            Employee.objects.filter(team=team_key, is_active=True)
            .values_list('id', flat=True)
        )
    else:
        try:
            gerente_emp = Employee.objects.select_related('department').get(user=request.user)
            emp_ids = list(
                Employee.objects.filter(department=gerente_emp.department, is_active=True)
                .values_list('id', flat=True)
            )
        except Employee.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'Empleado no encontrado'}, status=404)

    cfg = ConfiguracionIncentivos.get()

    # Construir lookup de prenómina para calcular montos proporcionales al resetear
    prenomina_lookup = {}
    try:
        upload = PrenominaUpload.objects.get(semana=week_start)
        for reg in upload.registros.values('numero', 'dias_vacaciones', 'dias_incapacidad', 'dias_falta'):
            prenomina_lookup[reg['numero']] = (
                float(reg['dias_vacaciones']),
                float(reg['dias_incapacidad']),
                float(reg['dias_falta']),
            )
    except PrenominaUpload.DoesNotExist:
        pass

    emp_numbers = {
        e['id']: e['employee_number']
        for e in Employee.objects.filter(id__in=emp_ids).values('id', 'employee_number')
    }

    # Resetear todos a monto proporcional según prenómina
    regs_a_resetear = IncentivoRegistro.objects.filter(
        employee_id__in=emp_ids,
        tipo='Mistery',
        fecha=week_start,
    )
    for reg in regs_a_resetear:
        monto = _monto_proporcional_prenomina(
            emp_numbers.get(reg.employee_id, ''), prenomina_lookup, cfg.mistery_monto, check_faltas=True,
        )
        if reg.monto != monto:
            reg.monto = monto
            reg.save(update_fields=['monto'])

    # Si se seleccionó un evaluado, asignarle el monto especial
    if emp_id:
        try:
            emp_id = int(emp_id)
        except (ValueError, TypeError):
            return JsonResponse({'ok': False, 'error': 'ID inválido'}, status=400)
        if emp_id not in emp_ids:
            return JsonResponse({'ok': False, 'error': 'El empleado no pertenece al equipo'}, status=400)
        updated = IncentivoRegistro.objects.filter(
            employee_id=emp_id,
            tipo='Mistery',
            fecha=week_start,
        ).update(monto=cfg.mistery_monto_evaluado)
        if not updated:
            return JsonResponse({'ok': False, 'error': 'El empleado no tiene registro de Mistery esta semana'}, status=400)

    return JsonResponse({'ok': True, 'evaluado_emp_id': emp_id or None})


@login_required
def desglose_bonos(request):
    """Desglose de totales de bonos por estación. Solo staff y Gerente De Operaciones."""
    rol = _get_rol_incentivos(request.user)
    if rol not in ('admin', 'operaciones'):
        return redirect('incentives_dashboard')

    from datetime import date, timedelta
    from django.db.models import Count, Sum
    from collections import defaultdict
    from apps.incentives.constants import STATION_TEAMS, EXCEL_ORDER_LOOKUP

    today = date.today()
    lunes_hoy = today - timedelta(days=today.weekday())
    domingo_hoy = lunes_hoy + timedelta(days=6)

    if 'reset' in request.GET:
        request.session.pop('desglose_fecha_ini', None)
        request.session.pop('desglose_fecha_fin', None)

    if 'fecha_ini' in request.GET and 'fecha_fin' in request.GET:
        try:
            fecha_ini = date.fromisoformat(request.GET['fecha_ini'])
            fecha_fin = date.fromisoformat(request.GET['fecha_fin'])
            if fecha_fin < fecha_ini:
                fecha_ini, fecha_fin = fecha_fin, fecha_ini
            request.session['desglose_fecha_ini'] = fecha_ini.isoformat()
            request.session['desglose_fecha_fin'] = fecha_fin.isoformat()
        except ValueError:
            fecha_ini = lunes_hoy
            fecha_fin = domingo_hoy
    else:
        saved_ini = request.session.get('desglose_fecha_ini')
        saved_fin = request.session.get('desglose_fecha_fin')
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

    cfg = ConfiguracionIncentivos.get()

    # Usar exactamente el mismo filtrado de empleados que el panel admin para que
    # los totales coincidan: deduplicación por TSA + filtro de antigüedad.
    from django.db.models import Q
    inactivos_con_registro = set(
        IncentivoRegistro.objects
        .filter(fecha__range=(fecha_ini, fecha_fin), employee__is_active=False,
                employee__team__in=STATION_TEAMS.keys())
        .values_list('employee_id', flat=True)
    )
    employees = _filtrar_empleados_por_semana(
        _deduplicar_por_tsa(list(
            Employee.objects
            .filter(team__in=STATION_TEAMS.keys())
            .exclude(job_position__title__in=PUESTOS_EXCLUIDOS_INCENTIVOS)
            .filter(Q(is_active=True) | Q(id__in=inactivos_con_registro))
            .only('id', 'team', 'curp', 'company', 'seniority_raw', 'is_active')
        )),
        fecha_fin,
        inactivos_con_registro,
    )
    emp_ids = [emp.id for emp in employees]
    emp_team_map = {emp.id: emp.team.strip() for emp in employees}

    registros = (
        IncentivoRegistro.objects
        .filter(employee_id__in=emp_ids, fecha__range=(fecha_ini, fecha_fin))
        .values('employee_id', 'tipo')
        .annotate(count=Count('id'), suma_monto=Sum('monto'))
    )

    # Acumular por estación
    TIPOS_CON_MONTO = {'Diesel', 'Encargado', 'Venta', 'Mistery', 'ECV', 'Auditoría', 'Auditoria', 'Rotación', 'Rotacion'}
    station_totales = defaultdict(lambda: {
        'Diesel': 0, 'Encargado': 0, 'Venta': 0, 'Mistery': 0,
        'ECV': 0, 'Auditoria': 0, 'Rotacion': 0,
        'total': 0,
    })

    for r in registros:
        team_key = emp_team_map.get(r['employee_id'], '').strip()
        if not team_key or team_key not in STATION_TEAMS:
            continue
        tipo = r['tipo']
        count = r['count'] or 0
        suma = int(r['suma_monto'] or 0)

        if tipo == 'Diesel':
            monto = count * cfg.diesel_por_dia
            station_totales[team_key]['Diesel'] += monto
        elif tipo == 'Encargado':
            monto = (cfg.encargado_primer_dia + (count - 1) * cfg.encargado_incremento) if count > 0 else 0
            station_totales[team_key]['Encargado'] += monto
        elif tipo == 'Venta':
            monto = suma
            station_totales[team_key]['Venta'] += monto
        elif tipo == 'Mistery':
            monto = suma
            station_totales[team_key]['Mistery'] += monto
        elif tipo == 'ECV':
            monto = suma
            station_totales[team_key]['ECV'] += monto
        elif tipo in ('Auditoría', 'Auditoria'):
            monto = suma
            station_totales[team_key]['Auditoria'] += monto
        elif tipo in ('Rotación', 'Rotacion'):
            monto = suma
            station_totales[team_key]['Rotacion'] += monto
        else:
            monto = 0

        station_totales[team_key]['total'] += monto

    # Construir filas ordenadas
    rows = []
    for team_key, display in STATION_TEAMS.items():
        t = station_totales[team_key]
        rows.append({
            'team_key':  team_key,
            'nombre':    display,
            'diesel':    t['Diesel'],
            'encargado': t['Encargado'],
            'venta':     t['Venta'],
            'mistery':   t['Mistery'],
            'ecv':       t['ECV'],
            'auditoria': t['Auditoria'],
            'rotacion':  t['Rotacion'],
            'total':     t['total'],
        })

    rows.sort(key=lambda x: EXCEL_ORDER_LOOKUP.get(x['team_key'], (9999, x['team_key']))[0])

    # Filas con al menos un registro
    rows_con_datos = [r for r in rows if r['total'] > 0]

    totales = {
        'diesel':    sum(r['diesel']    for r in rows),
        'encargado': sum(r['encargado'] for r in rows),
        'venta':     sum(r['venta']     for r in rows),
        'mistery':   sum(r['mistery']   for r in rows),
        'ecv':       sum(r['ecv']       for r in rows),
        'auditoria': sum(r['auditoria'] for r in rows),
        'rotacion':  sum(r['rotacion']  for r in rows),
        'total':     sum(r['total']     for r in rows),
    }

    mostrar_sin_datos = request.GET.get('sin_datos') == '1'
    semana_num  = fecha_ini.isocalendar()[1]
    semana_year = fecha_ini.isocalendar()[0]

    return render(request, 'incentives/admin/desglose_bonos.html', {
        'fecha_ini': fecha_ini,
        'fecha_fin': fecha_fin,
        'today': today,
        'rows': rows if mostrar_sin_datos else rows_con_datos,
        'totales': totales,
        'cfg': cfg,
        'mostrar_sin_datos': mostrar_sin_datos,
        'semana_num': semana_num,
        'semana_year': semana_year,
    })


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

            # Guardar indicadores ECV
            from decimal import Decimal, InvalidOperation
            for ind in IndicadorECV.objects.select_related('categoria').all():
                prefix = f'ecv_{ind.categoria.id}_{ind.nombre}'
                try:
                    ind.ponderacion      = Decimal(request.POST[f'{prefix}_ponderacion'])
                    ind.umbral_minimo    = Decimal(request.POST[f'{prefix}_minimo'])
                    ind.umbral_objetivo  = Decimal(request.POST[f'{prefix}_objetivo'])
                    ind.umbral_excelente = Decimal(request.POST[f'{prefix}_excelente'])
                    ind.save()
                except (KeyError, InvalidOperation):
                    pass

            guardado = True

    # Calcular tope y escala para mostrar en la UI
    encargado_escala = [
        cfg.encargado_primer_dia + i * cfg.encargado_incremento
        for i in range(cfg.encargado_max_dias)
    ]
    encargado_tope = encargado_escala[-1] if encargado_escala else 0
    diesel_tope    = cfg.diesel_por_dia * cfg.diesel_max_dias

    categorias_ecv = CategoriaECV.objects.prefetch_related('indicadores').order_by('nombre')

    return render(request, 'incentives/admin/configuracion_incentivos.html', {
        'cfg': cfg,
        'encargado_escala': encargado_escala,
        'encargado_tope': encargado_tope,
        'diesel_tope': diesel_tope,
        'errores': errores,
        'guardado': guardado,
        'categorias_ecv': categorias_ecv,
    })


@login_required
def sync_incidencias_semana(request):
    """API: devuelve el conteo y logro de incidencias por estación para la semana."""
    from datetime import date
    semana_str = request.GET.get('semana', '')
    try:
        week_start = date.fromisoformat(semana_str)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Semana inválida'})

    resultado = _calcular_incidencias_semana(week_start)

    estaciones_json = {}
    for team_key, datos in resultado['estaciones'].items():
        logro = float(datos['logro']) if datos['logro'] is not None else None
        estaciones_json[team_key] = {
            'count': datos['count'],
            'logro': logro,
            'verde': (logro is not None and logro > 0),
        }

    return JsonResponse({
        'ok': True,
        'semana_cargada': resultado['semana_cargada'],
        'estaciones': estaciones_json,
    })


@login_required
def sync_faltantes_semana(request):
    """
    API: devuelve el total de faltantes por estación a partir del snapshot
    guardado en FaltanteEstacionSemanal (captura manual o import de Excel).
    """
    from datetime import date

    semana_str = request.GET.get('semana')
    try:
        week_start = date.fromisoformat(semana_str) if semana_str else None
    except ValueError:
        week_start = None

    ind = IndicadorECV.objects.filter(nombre='faltante').first()
    umbral_min = float(ind.umbral_minimo)  if ind else 500.0
    umbral_obj = float(ind.umbral_objetivo) if ind else 100.0
    umbral_exc = float(ind.umbral_excelente) if ind else 0.0

    # El snapshot solo se llena de forma manual (captura o import de Excel).
    # Si la semana no tiene snapshot guardado, no hay faltantes que mostrar
    # (nunca se lee ni se persiste automáticamente el F8 abierto, ya que eso
    # refleja "faltantes pendientes ahora", no el histórico de esa semana).
    # Si la semana SÍ tiene snapshot (al menos una estación capturada), una
    # estación que no aparece en él es porque no tuvo faltantes ese registro
    # ($0, verde) — no porque falte el dato.
    snapshot_qs = FaltanteEstacionSemanal.objects.filter(week_start=week_start) if week_start else None
    if snapshot_qs is not None:
        totales = {r.team_key: float(r.monto) for r in snapshot_qs}
        semana_capturada = bool(totales)
    else:
        totales = {}
        semana_capturada = False

    def _nivel(monto):
        calculo = _score_menor(monto, umbral_min, umbral_obj, umbral_exc)
        if calculo >= 120:
            nivel = 'excelente'
        elif calculo >= 100:
            nivel = 'objetivo'
        elif calculo >= 80:
            nivel = 'minimo'
        else:
            nivel = 'no_cumple'
        return nivel, calculo

    estaciones_json = {}
    team_keys_a_mostrar = set(totales) | (set(STATION_TEAMS) if semana_capturada else set())
    for team_key in team_keys_a_mostrar:
        monto = totales.get(team_key, 0.0)
        nivel, calculo = _nivel(monto)
        estaciones_json[team_key] = {
            'total':   round(monto, 2),
            'verde':   monto <= umbral_min,
            'nivel':   nivel,
            'calculo': calculo,
        }

    return JsonResponse({'ok': True, 'estaciones': estaciones_json})


@login_required
@require_POST
def capturar_faltantes_f8(request):
    """
    Acción manual: lee el F8 "FALTANTES (Respuestas)" en este momento
    (faltantes actualmente abiertos, igual que el reporte oficial F8 SEMANAL)
    y reemplaza el snapshot de FaltanteEstacionSemanal de la semana indicada
    con ese dato. No se ejecuta automáticamente — solo vía este botón.
    """
    from datetime import date
    from apps.incentives.faltantes_service import leer_faltantes_f8_abiertos

    rol = _get_rol_incentivos(request.user)
    if rol not in ('admin', 'operaciones'):
        return JsonResponse({'ok': False, 'error': 'Sin permiso'}, status=403)

    try:
        data = json.loads(request.body)
        week_start = date.fromisoformat(data['semana'])
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'error': 'Falta parámetro semana'}, status=400)

    if SemanaCerrada.objects.filter(week_start=week_start).exists():
        return JsonResponse({'ok': False, 'error': 'La semana está cerrada'}, status=400)

    totales, error = leer_faltantes_f8_abiertos()
    if error:
        return JsonResponse({'ok': False, 'error': error})

    FaltanteEstacionSemanal.objects.filter(week_start=week_start).delete()
    FaltanteEstacionSemanal.objects.bulk_create([
        FaltanteEstacionSemanal(team_key=team_key, week_start=week_start, monto=monto)
        for team_key, monto in totales.items()
    ])

    return JsonResponse({'ok': True, 'total_estaciones': len(totales)})


@login_required
def sync_ecv_semana(request):
    """
    Calcula el score ECV (en puntos %) por estación combinando los 5 indicadores.
    Solo lectura — no crea ni modifica IncentivoRegistro.
    """
    from datetime import date

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

    resultado = _calcular_ecv_semana(week_start)
    return JsonResponse({'ok': True, 'estaciones': resultado})


def _calcular_ecv_semana(week_start):
    """Calcula el score ECV (en puntos %) por estación combinando los 5 indicadores.
    Compartido por sync_ecv_semana (JSON para el dashboard) y exportar_ecv_excel
    (descarga .xlsx con el resumen por estación)."""
    from datetime import timedelta
    from django.db import connections
    from apps.incentives.constants import DIESEL_TEAM_KEYS, SG12_COD_TO_TEAM_KEY, CATEGORIA_BONO_ESTACION

    # Indicadores ECV agrupados por categoría
    inds_cat = {}
    for ind in IndicadorECV.objects.select_related('categoria').all():
        inds_cat.setdefault(ind.categoria.nombre, {})[ind.nombre] = ind

    # Venta desde IndicadorVentaSemanal (ya calculado por sync_venta_semana)
    ventas_db = {v.team_key: v for v in IndicadorVentaSemanal.objects.filter(week_start=week_start)}

    # Mistery: qualification real desde TGV2
    date_mistery = week_start + timedelta(days=6)
    mistery_qual = {}
    try:
        with connections['default'].cursor() as cursor:
            cursor.execute(
                "SELECT codgas, qualification FROM TGV2.dbo.AuditoriaMystery WHERE date_mistery = %s",
                [date_mistery.isoformat()],
            )
            for codgas, qual in cursor.fetchall():
                tk = SG12_COD_TO_TEAM_KEY.get(codgas)
                if tk:
                    mistery_qual[tk] = float(qual or 0)
    except Exception:
        pass

    # Faltantes: siempre usar el snapshot guardado en BD.
    # Semanas sin snapshot muestran "sin dato" — el F8 abierto ya NO se lee
    # ni se persiste automáticamente, porque refleja "faltantes pendientes
    # ahora", no el histórico de la semana consultada. Pero si la semana SÍ
    # tiene snapshot (al menos una estación capturada), una estación que no
    # aparece en él es porque no tuvo faltantes ($0, verde) — no porque
    # falte el dato.
    faltantes = {
        r.team_key: float(r.monto)
        for r in FaltanteEstacionSemanal.objects.filter(week_start=week_start)
    }
    semana_faltantes_capturada = bool(faltantes)

    # Incidencias desde DB
    inc_data = _calcular_incidencias_semana(week_start)
    inc_estaciones = inc_data['estaciones']

    # Configuración de montos de bono ECV
    cfg = ConfiguracionIncentivos.objects.first()

    # Travel Center usa ponderaciones distintas al estándar Cat-B
    # (gas=30%, diesel=25%, mistery=20%, faltante=15%, incidencia=10%)
    from types import SimpleNamespace
    from decimal import Decimal as _D
    _TC_INDS = {
        'venta_gas':    SimpleNamespace(ponderacion=_D('30'), umbral_minimo=_D('97'),  umbral_objetivo=_D('100'), umbral_excelente=_D('103')),
        'venta_diesel': SimpleNamespace(ponderacion=_D('25'), umbral_minimo=_D('97'),  umbral_objetivo=_D('100'), umbral_excelente=_D('103')),
        'mistery':      SimpleNamespace(ponderacion=_D('20'), umbral_minimo=_D('92'),  umbral_objetivo=_D('100'), umbral_excelente=_D('103')),
        'faltante':     SimpleNamespace(ponderacion=_D('15'), umbral_minimo=_D('500'), umbral_objetivo=_D('100'), umbral_excelente=_D('0')),
        'incidencia':   SimpleNamespace(ponderacion=_D('10'), umbral_minimo=_D('3'),   umbral_objetivo=_D('2'),   umbral_excelente=_D('0')),
    }

    resultado = {}
    for team_key in STATION_TEAMS:
        es_travel = (team_key == 'Travel Center')
        cat = 'B' if (team_key in DIESEL_TEAM_KEYS or es_travel) else 'A'
        inds = _TC_INDS if es_travel else inds_cat.get(cat, {})
        total_puntos = 0.0
        detalle = {}

        # Venta Gasolina
        v = ventas_db.get(team_key)
        alcance_gas = (v.vs_gas / v.ps_gas * 100) if (v and v.vs_gas is not None and v.ps_gas) else None
        d = _calc_indicador('venta_gas', alcance_gas, _score_mayor, inds)
        d['alcance_raw'] = v.vs_gas if v else None
        d['objetivo_raw'] = v.ps_gas if v else None
        detalle['venta_gas'] = d
        if d['valor'] is not None:
            total_puntos += d['valor']

        # Venta Diésel (Cat B y Travel Center)
        if cat == 'B':
            alcance_die = (v.vs_diesel / v.ps_diesel * 100) if (v and v.vs_diesel is not None and v.ps_diesel) else None
            d = _calc_indicador('venta_diesel', alcance_die, _score_mayor, inds)
            d['alcance_raw'] = v.vs_diesel if v else None
            d['objetivo_raw'] = v.ps_diesel if v else None
            detalle['venta_diesel'] = d
            if d['valor'] is not None:
                total_puntos += d['valor']

        # Mistery Shopper (qualification %)
        d = _calc_indicador('mistery', mistery_qual.get(team_key), _score_mayor, inds)
        d['alcance_raw'] = mistery_qual.get(team_key)
        d['objetivo_raw'] = 100.0
        detalle['mistery'] = d
        if d['valor'] is not None:
            total_puntos += d['valor']

        # Faltante: sin snapshot guardado para la estación/semana = sin dato (no asumir Excelente).
        # Si la semana ya tiene snapshot en otras estaciones, no aparecer = $0 de faltante (verde).
        alcance_falt = faltantes.get(team_key, 0.0 if semana_faltantes_capturada else None)
        d = _calc_indicador('faltante', alcance_falt, _score_menor, inds)
        detalle['faltante'] = d
        if d['valor'] is not None:
            total_puntos += d['valor']

        # Incidencia en cortes
        ind_inc = inds.get('incidencia')
        umbrales_inc = {
            'ponderacion':      float(ind_inc.ponderacion)      if ind_inc else None,
            'umbral_minimo':    float(ind_inc.umbral_minimo)    if ind_inc else None,
            'umbral_objetivo':  float(ind_inc.umbral_objetivo)  if ind_inc else None,
            'umbral_excelente': float(ind_inc.umbral_excelente) if ind_inc else None,
        }
        inc_est = inc_estaciones.get(team_key)
        if inc_est and inc_est['logro'] is not None:
            if ind_inc:
                calculo_inc = float(inc_est['logro']) * 100  # 0.0–1.2 → 0–120
                valor_inc = round(calculo_inc * float(ind_inc.ponderacion) / 100, 4)
                detalle['incidencia'] = {
                    'alcance': inc_est['count'],
                    'calculo': round(calculo_inc, 2),
                    'valor': valor_inc,
                    **umbrales_inc,
                }
                total_puntos += valor_inc
            else:
                detalle['incidencia'] = {'alcance': inc_est['count'], 'calculo': None, 'valor': None, **umbrales_inc}
        else:
            detalle['incidencia'] = {'alcance': None, 'calculo': None, 'valor': None, **umbrales_inc}

        # Bono gerente/subgerente según categoría A/B/C (Travel Center usa montos especiales)
        cat_bono = CATEGORIA_BONO_ESTACION.get(team_key)
        bono_gerente = bono_subgerente = 0.0
        if es_travel:
            # Travel Center: 12 000 / 6 000 mensuales (distintos al estándar A/B/C)
            monto_g, monto_sg = 12000, 6000
        elif cat_bono:
            monto_g  = getattr(cfg, f'bono_gerente_cat_{cat_bono.lower()}', 0) if cfg else 0
            monto_sg = getattr(cfg, f'bono_subgerente_cat_{cat_bono.lower()}', 0) if cfg else 0
        else:
            monto_g = monto_sg = 0
        if total_puntos >= 80:
            bono_gerente    = round(monto_g  * 7 / 30.4 * total_puntos / 100, 2)
            bono_subgerente = round(monto_sg * 7 / 30.4 * total_puntos / 100, 2)

        resultado[team_key] = {
            'categoria': cat,
            'indicadores': detalle,
            'total_puntos': round(total_puntos, 2),
            'categoria_bono': cat_bono or ('Travel' if es_travel else None),
            'monto_base_gerente': monto_g,
            'monto_base_subgerente': monto_sg,
            'bono_gerente': bono_gerente,
            'bono_subgerente': bono_subgerente,
        }

    return resultado


@login_required
def exportar_ecv_excel(request):
    """Descarga un Excel con el resumen de Compensación Variable (ECV) de la
    semana: una hoja por estación, igual al bloque 'Cálculo de Compensación
    Variable' de los Excel ECV Zona que se entregan manualmente."""
    from datetime import date, timedelta
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.drawing.spreadsheet_drawing import OneCellAnchor, AnchorMarker
    from openpyxl.drawing.xdr import XDRPositiveSize2D
    from django.http import HttpResponse
    from django.contrib.staticfiles import finders
    from apps.incentives.constants import EXCEL_ORDER_LOOKUP

    logo_path = finders.find('template/img/logos/logo_sencillo.png')
    isologo_path = finders.find('template/img/logos/ISOLOGO.png')

    rol = _get_rol_incentivos(request.user)
    if rol not in ('admin', 'operaciones', 'zona', 'gerente'):
        return redirect('incentives_dashboard')

    # Límite de estaciones permitidas: None = sin límite (admin/operaciones);
    # un set = solo esas (jefe de zona: su zona; gerente/subgerente: su estación).
    teams_permitidos = None
    if rol == 'zona':
        try:
            jefe = Employee.objects.select_related('job_position').get(user=request.user)
            teams_permitidos = _teams_del_jefe_zona(jefe)
        except Employee.DoesNotExist:
            teams_permitidos = set()
    elif rol == 'gerente':
        try:
            gerente_emp = Employee.objects.get(user=request.user)
            team_key_propio = (gerente_emp.team or '').strip()
            teams_permitidos = {team_key_propio} if team_key_propio else set()
        except Employee.DoesNotExist:
            teams_permitidos = set()

    semana_str = request.GET.get('semana')
    today = date.today()
    if semana_str:
        try:
            week_start = date.fromisoformat(semana_str)
        except ValueError:
            week_start = today - timedelta(days=today.weekday())
    else:
        week_start = today - timedelta(days=today.weekday())

    resultado = _calcular_ecv_semana(week_start)
    semana_num = week_start.isocalendar()[1]

    INDICADORES = [
        ('venta_gas',    'Venta Gasolina',       'num'),
        ('venta_diesel', 'Venta Diésel',         'num'),
        ('mistery',      'Mistery Shopper',      'pct'),
        ('faltante',     'Faltante',             'money'),
        ('incidencia',   'Incidencia en cortes', 'count'),
    ]

    bold = Font(bold=True)
    title_font = Font(bold=True, size=14, color='FFFFFF')
    white_bold = Font(bold=True, color='FFFFFF')
    right = Alignment(horizontal='right', vertical='center')
    center = Alignment(horizontal='center', vertical='center')
    vcenter = Alignment(vertical='center')

    FILL_TITLE   = PatternFill('solid', fgColor='002060')
    FILL_HEADER1 = PatternFill('solid', fgColor='002060')
    FILL_HEADER2 = PatternFill('solid', fgColor='023874')
    FILL_LABEL   = PatternFill('solid', fgColor='ECF5D7')
    FILL_INFO    = PatternFill('solid', fgColor='E5FCFF')
    FILL_BONO    = PatternFill('solid', fgColor='034EA2')
    FILL_MIN     = PatternFill('solid', fgColor='FFEB9C')
    FILL_OBJ     = PatternFill('solid', fgColor='C6EFCE')
    FILL_EXC     = PatternFill('solid', fgColor='8EA9DB')
    FILL_BUENO   = PatternFill('solid', fgColor='C6EFCE')
    FILL_REGULAR = PatternFill('solid', fgColor='FFEB9C')
    FILL_MALO    = PatternFill('solid', fgColor='FFC7CE')
    FILL_AZUL    = PatternFill('solid', fgColor='B4C6E7')
    FONT_MIN  = Font(bold=True, color='9C5700')
    FONT_OBJ  = Font(bold=True, color='006100')
    FONT_EXC  = Font(bold=True, color='1F3864')
    FONT_BUENO   = Font(bold=True, color='006100')
    FONT_REGULAR = Font(bold=True, color='9C5700')
    FONT_MALO    = Font(bold=True, color='9C0006')
    FONT_AZUL    = Font(bold=True, color='1F3864')

    def _set(ws, row, col, value, number_format=None, font=None, align=None, fill=None):
        cell = ws.cell(row=row, column=col, value=value)
        if number_format:
            cell.number_format = number_format
        if font:
            cell.font = font
        cell.alignment = align if align else vcenter
        if fill:
            cell.fill = fill
        return cell

    SPACER_COLS = {3, 9, 13}  # C, I, M — columnas espaciadoras, nunca llevan color

    def _fill_row(ws, row, cols, fill):
        for col in cols:
            if col in SPACER_COLS:
                continue
            ws.cell(row=row, column=col).fill = fill

    thick_black = Side(style='medium', color='000000')
    border_black = Border(left=thick_black, right=thick_black, top=thick_black, bottom=thick_black)

    def _border_range(ws, row1, col1, row2, col2):
        """Cuadrícula: borde grueso en TODAS las celdas del rango."""
        for r in range(row1, row2 + 1):
            for c in range(col1, col2 + 1):
                ws.cell(row=r, column=c).border = border_black

    def _center_range(ws, row1, col1, row2, col2):
        for r in range(row1, row2 + 1):
            for c in range(col1, col2 + 1):
                ws.cell(row=r, column=c).alignment = center

    def _border_outline(ws, row1, col1, row2, col2):
        """Un solo cuadro alrededor del rango — sin líneas internas entre celdas."""
        for r in range(row1, row2 + 1):
            for c in range(col1, col2 + 1):
                ws.cell(row=r, column=c).border = Border(
                    top=thick_black if r == row1 else None,
                    bottom=thick_black if r == row2 else None,
                    left=thick_black if c == col1 else None,
                    right=thick_black if c == col2 else None,
                )

    def _semaforo_logro(alcance, umin, uobj, uexc, mayor_es_mejor):
        """Color de la columna % Logro (H): 4 tramos (Rojo/Amarillo/Verde/Azul)
        según la posición del Alcance real frente a los umbrales Mínimo/
        Objetivo/Excelente de ESE indicador (columnas J/K/L de la misma fila
        — 97/100/103 en venta, 92/100/103 en mistery, 500/100/0 en faltante,
        etc.), no un estándar fijo: cada indicador tiene su propia escala."""
        if alcance is None or umin is None or uobj is None or uexc is None:
            return None, None
        if mayor_es_mejor:
            if alcance < umin:
                return FILL_MALO, FONT_MALO
            if alcance < uobj:
                return FILL_REGULAR, FONT_REGULAR
            if alcance < uexc:
                return FILL_BUENO, FONT_BUENO
            return FILL_AZUL, FONT_AZUL
        else:
            if alcance <= uexc:
                return FILL_AZUL, FONT_AZUL
            if alcance <= uobj:
                return FILL_BUENO, FONT_BUENO
            if alcance <= umin:
                return FILL_REGULAR, FONT_REGULAR
            return FILL_MALO, FONT_MALO

    def _pct(ws, row, col, value, font=None, fill=None):
        if value is None:
            _set(ws, row, col, 'N/A', font=font, fill=fill)
        else:
            _set(ws, row, col, round(value / 100, 4), number_format='0.00%', font=font, align=right, fill=fill)

    def _num(ws, row, col, value, tipo, font=None, fill=None):
        if value is None:
            _set(ws, row, col, 'N/A', font=font, fill=fill)
        elif tipo == 'pct':
            _pct(ws, row, col, value, font=font, fill=fill)
        elif tipo == 'money':
            _set(ws, row, col, round(value, 2), number_format='"$"#,##0.00', font=font, align=right, fill=fill)
        elif tipo == 'count':
            _set(ws, row, col, round(value, 2), number_format='0', font=font, align=right, fill=fill)
        else:
            _set(ws, row, col, round(value, 2), number_format='#,##0', font=font, align=right, fill=fill)

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    team_keys = sorted(STATION_TEAMS.keys(), key=lambda tk: EXCEL_ORDER_LOOKUP.get(tk, (9999, tk))[0])

    # Jefe de zona / gerente / subgerente: nunca pueden ver estaciones fuera
    # de las suyas, sin importar lo que venga en el query param (no es un
    # filtro, es un límite).
    if teams_permitidos is not None:
        team_keys = [tk for tk in team_keys if tk in teams_permitidos]

    # Si la vista tenía un filtro de búsqueda activo, solo exportar las
    # estaciones que quedaron visibles (mismas que mandó el JS).
    estaciones_filtro = request.GET.get('estaciones')
    if estaciones_filtro:
        filtro_set = {tk for tk in estaciones_filtro.split(',') if tk}
        team_keys = [tk for tk in team_keys if tk in filtro_set]

    hojas_usadas = set()

    # Fill de columnas sin el "skip" de SPACER_COLS (ese skip es específico
    # del layout de la hoja por estación; aquí C/I/M sí llevan color).
    def _fill_cols(ws, row, cols, fill):
        for col in cols:
            ws.cell(row=row, column=col).fill = fill

    # Bandeado (zebra) de filas de datos — usado en "Ventas y Mistery",
    # "Incidencias" y "Faltantes" para distinguir renglones. No pisa celdas
    # que ya tengan un color con significado propio (ej. diferencias en
    # rojo/verde, estatus en amarillo).
    FILL_BANDA = PatternFill('solid', fgColor='D9E1F2')

    def _bandear_filas(ws, row1, row2, col1, col2):
        for i, r in enumerate(range(row1, row2 + 1)):
            if i % 2 == 1:
                for c in range(col1, col2 + 1):
                    cell = ws.cell(row=r, column=c)
                    if cell.fill is None or cell.fill.fill_type is None:
                        cell.fill = FILL_BANDA

    # Hoja "Ventas y Mistery" (primera del libro): réplica exacta (colores,
    # fuentes, formatos de número y layout de columnas) de la hoja "Ventas y
    # Mystery" del Excel ECV Zona que se entrega manualmente — presupuesto
    # mensual/semanal, venta real semanal (con diferencia contra presupuesto)
    # y mistery shopper, una fila por estación.
    import calendar
    MESES_ES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
                'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

    week_end = week_start + timedelta(days=6)
    if week_start.month == week_end.month:
        mes_principal = week_start.replace(day=1)
        dias_semana_mes = 7
    else:
        inicio_mes2 = (date(week_start.year + 1, 1, 1) if week_start.month == 12
                        else date(week_start.year, week_start.month + 1, 1))
        dias_mes1 = (inicio_mes2 - week_start).days
        dias_mes2 = 7 - dias_mes1
        if dias_mes1 >= dias_mes2:
            mes_principal, dias_semana_mes = week_start.replace(day=1), dias_mes1
        else:
            mes_principal, dias_semana_mes = week_end.replace(day=1), dias_mes2
    dias_del_mes = calendar.monthrange(mes_principal.year, mes_principal.month)[1]

    ppto_mes = {r.team_key: r for r in PresupuestoVenta.objects.filter(mes=mes_principal)}
    ventas_sem = {v.team_key: v for v in IndicadorVentaSemanal.objects.filter(week_start=week_start)}

    FILL_VYM_TITLE = PatternFill('solid', fgColor='9CD044')
    FILL_VYM_BLUE  = PatternFill('solid', fgColor='004E99')
    FILL_VYM_GREEN = PatternFill('solid', fgColor='009558')
    FILL_VYM_TOTAL = PatternFill('solid', fgColor='DCE6F1')
    FONT_VYM_TITLE = Font(bold=True, size=20, color='FFFFFF')
    font_arial      = Font(name='Arial', size=11)
    font_arial_bold = Font(name='Arial', size=11, bold=True)
    ACC_FMT = '_-* #,##0_-;\\-* #,##0_-;_-* "-"??_-;_-@_-'
    thin_black = Side(style='thin', color='000000')
    border_thin = Border(left=thin_black, right=thin_black, top=thin_black, bottom=thin_black)

    def _border_thin_range(ws, row1, col1, row2, col2):
        for r in range(row1, row2 + 1):
            for c in range(col1, col2 + 1):
                ws.cell(row=r, column=c).border = border_thin

    ws_v = wb.create_sheet('Ventas y Mistery')
    ws_v.sheet_view.showGridLines = False

    SPACER_COLS_VYM = {6, 11, 20}  # F, K, T
    for col, width in zip('ABCDEFGHIJKLMNOPQRSTUVWX',
                           [16, 18, 17, 16, 22, 3, 11, 16, 14, 16, 3, 18, 11, 16, 13, 14, 13, 14, 13, 3, 23, 20, 14, 11]):
        ws_v.column_dimensions[col].width = width
    ws_v.column_dimensions['X'].hidden = True
    for r, h in [(1, 30), (5, 30)]:
        ws_v.row_dimensions[r].height = h

    # Fila 1: título "Semana N" — barra verde-oliva.
    ws_v.merge_cells('A1:X1')
    _fill_cols(ws_v, 1, range(1, 25), FILL_VYM_TITLE)
    _set(ws_v, 1, 1, f'Semana {semana_num}', font=FONT_VYM_TITLE, align=center)

    # Filas 2-3: cuadro "Mes" / "Días del mes" (azul) + cuadro "Promedio" mistery (sin relleno).
    ws_v.merge_cells(start_row=2, start_column=1, end_row=2, end_column=2)
    ws_v.merge_cells(start_row=3, start_column=1, end_row=3, end_column=2)
    ws_v.merge_cells(start_row=2, start_column=4, end_row=3, end_column=4)
    _fill_cols(ws_v, 2, range(1, 6), FILL_VYM_BLUE)
    _fill_cols(ws_v, 3, range(1, 6), FILL_VYM_BLUE)
    _set(ws_v, 2, 1, 'Mes', font=white_bold, align=center)
    _set(ws_v, 2, 3, MESES_ES[mes_principal.month - 1], font=white_bold, align=center)
    _set(ws_v, 2, 4, 'Días de la semana', font=white_bold, align=center)
    _set(ws_v, 2, 5, dias_semana_mes, font=white_bold, align=center)
    _set(ws_v, 3, 1, 'Días del mes', font=white_bold, align=center)
    _set(ws_v, 3, 3, dias_del_mes, font=white_bold, align=center)
    _border_thin_range(ws_v, 2, 1, 3, 5)

    todas_calificaciones = [
        resultado[tk]['indicadores'].get('mistery', {}).get('alcance_raw')
        for tk in team_keys if resultado.get(tk) and resultado[tk]['indicadores'].get('mistery', {}).get('alcance_raw') is not None
    ]
    promedio_mistery = sum(todas_calificaciones) / len(todas_calificaciones) if todas_calificaciones else None

    _set(ws_v, 3, 21, 'Promedio', font=bold, align=center)
    _set(ws_v, 3, 23, round(promedio_mistery, 1) if promedio_mistery is not None else 'N/A',
         font=bold, align=center, number_format='0.0' if promedio_mistery is not None else 'General')
    _border_thin_range(ws_v, 3, 21, 3, 23)

    # Fila 4: encabezados de grupo (azul) — Indicadores / Presupuesto Mensual / Presupuesto Semanal / Venta Semanal / Mystery Shopper.
    header_r1, header_r2 = 4, 5
    _fill_cols(ws_v, header_r1, range(1, 25), FILL_VYM_BLUE)
    for col1, col2, label in [(1, 2, 'Indicadores'), (3, 5, 'Presupuesto Mensual'), (8, 10, 'Presupuesto Semanal'),
                               (12, 19, 'Venta Semanal'), (21, 24, 'Mystery Shopper')]:
        ws_v.merge_cells(start_row=header_r1, start_column=col1, end_row=header_r1, end_column=col2)
        _set(ws_v, header_r1, col1, label, font=white_bold, align=center)

    # Fila 5: sub-encabezados — N°/Estación en azul, columnas de métrica en verde.
    # Columnas: A=N°  B=Estación | C-E PM Gas/Diesel/Total | G=N° H-J PS Gas/Diesel/Total
    # | L=Estación M=N° N-S VS Gas/Dif/Diesel/Dif2/Total/Dif3 | U=N° V=Estación W=Calificación X=Columna1
    blue_cols  = {1: 'N°', 2: 'Estación', 7: 'N°', 12: 'Estación', 13: 'N°', 21: 'N°', 22: 'Estación'}
    green_cols = {
        3: 'Gasolinas (Máxima-Super)', 4: 'Diesel', 5: 'Total',
        8: 'Gasolinas (Máxima-Super)', 9: 'Diesel', 10: 'Total',
        14: 'Gasolinas (Máxima-Super)', 15: 'Dif / Ppto.', 16: 'Diesel', 17: 'Dif / Ppto.2',
        18: 'Total', 19: 'Dif / Ppto.3', 23: 'Calificación', 24: 'Columna1',
    }
    for col, label in blue_cols.items():
        _set(ws_v, header_r2, col, label, font=white_bold, align=center, fill=FILL_VYM_BLUE)
    for col, label in green_cols.items():
        _set(ws_v, header_r2, col, label, font=white_bold, align=center, fill=FILL_VYM_GREEN)
    _border_thin_range(ws_v, header_r1, 1, header_r2, 24)

    MONEY_COLS_VYM = [3, 4, 5, 8, 9, 10, 14, 15, 16, 17, 18, 19]

    row = header_r2 + 1
    first_data_row = row
    totales = dict.fromkeys(MONEY_COLS_VYM, 0.0)
    for team_key in team_keys:
        est = resultado.get(team_key)
        if not est:
            continue
        nombre = STATION_TEAMS[team_key]
        ppto = ppto_mes.get(team_key)
        v = ventas_sem.get(team_key)
        mistery = est['indicadores'].get('mistery') or {}

        pm_gas    = float((ppto.maxima or 0) + (ppto.gasolina_super or 0)) if ppto else 0.0
        pm_diesel = float(ppto.diesel or 0) if ppto else 0.0
        pm_total  = float(ppto.total or 0) if ppto else (pm_gas + pm_diesel)

        ps_gas    = float(v.ps_gas or 0) if v else 0.0
        ps_diesel = float(v.ps_diesel or 0) if v else 0.0
        ps_total  = ps_gas + ps_diesel

        vs_gas    = float(v.vs_gas or 0) if v else 0.0
        vs_diesel = float(v.vs_diesel or 0) if v else 0.0
        vs_total  = vs_gas + vs_diesel

        dif_gas, dif_diesel, dif_total = vs_gas - ps_gas, vs_diesel - ps_diesel, vs_total - ps_total

        def _acc(col, value, font=font_arial, fill=None):
            _set(ws_v, row, col, round(value, 2), number_format=ACC_FMT, font=font, align=center, fill=fill)

        def _dif(col, value):
            fill, font = (FILL_BUENO, FONT_BUENO) if value > 0 else (FILL_MALO, FONT_MALO) if value < 0 else (None, font_arial)
            _acc(col, value, font=font, fill=fill)

        _set(ws_v, row, 1, team_key, font=font_arial, align=center)
        _set(ws_v, row, 2, nombre, font=font_arial_bold)

        _acc(3, pm_gas); _acc(4, pm_diesel); _acc(5, pm_total)

        _set(ws_v, row, 7, team_key, font=font_arial, align=center)
        _acc(8, ps_gas); _acc(9, ps_diesel); _acc(10, ps_total)

        _set(ws_v, row, 12, nombre, font=font_arial, align=center)
        _set(ws_v, row, 13, team_key, font=font_arial, align=center)
        _acc(14, vs_gas); _dif(15, dif_gas)
        _acc(16, vs_diesel); _dif(17, dif_diesel)
        _acc(18, vs_total); _dif(19, dif_total)

        calificacion = mistery.get('alcance_raw')
        _set(ws_v, row, 21, team_key, font=font_arial, align=center)
        _set(ws_v, row, 22, nombre, font=font_arial, align=center)
        if calificacion is None:
            _set(ws_v, row, 23, 'N/A', font=font_arial, align=center)
            _set(ws_v, row, 24, 'N/A', font=font_arial, align=center)
        else:
            _set(ws_v, row, 23, round(calificacion), number_format='0', font=font_arial, align=center)
            _set(ws_v, row, 24, round(calificacion / 100, 2), font=font_arial, align=center)

        for c, val in zip(MONEY_COLS_VYM,
                           [pm_gas, pm_diesel, pm_total, ps_gas, ps_diesel, ps_total,
                            vs_gas, dif_gas, vs_diesel, dif_diesel, vs_total, dif_total]):
            totales[c] += val

        _border_range(ws_v, row, 1, row, 24)
        row += 1

    last_data_row = row - 1
    _bandear_filas(ws_v, first_data_row, last_data_row, 1, 24)
    total_row = row
    _set(ws_v, total_row, 2, 'Total', font=font_arial_bold)
    for c in MONEY_COLS_VYM:
        _set(ws_v, total_row, c, round(totales[c], 2), number_format=ACC_FMT, font=font_arial_bold,
             align=center, fill=FILL_VYM_TOTAL)
    _set(ws_v, total_row, 21, 'Promedio', font=font_arial_bold, align=center)
    _set(ws_v, total_row, 23, round(promedio_mistery, 1) if promedio_mistery is not None else 'N/A',
         font=font_arial_bold, align=center, number_format='0.0' if promedio_mistery is not None else 'General')
    _border_thin_range(ws_v, total_row, 1, total_row, 24)

    for col in SPACER_COLS_VYM:
        for r in range(header_r1, last_data_row + 1):
            ws_v.cell(row=r, column=col).fill = PatternFill(fill_type=None)
            ws_v.cell(row=r, column=col).border = Border()

    # Constante compartida por las hojas "Incidencias" y "Faltantes".
    FONT_FALT_TITLE = Font(bold=True, size=20, color='FFFFFF')

    # Hoja "Incidencias" (al final, entre "Ventas y Mistery" y "Faltantes"):
    # resumen por estación (mismo conteo que ya alimenta el indicador
    # Incidencia del ECV) y detalle fila por fila de los cortes de la
    # semana usada para ese ECV — a diferencia de Faltantes, esto SÍ está
    # guardado en BD (IncidenciaRegistro), no hay que leerlo en vivo.
    semana_domingo_inc = week_start - timedelta(days=1)
    incidencias_detalle = list(
        IncidenciaRegistro.objects
        .filter(semana=semana_domingo_inc, estacion_key__in=team_keys)
        .order_by('estacion_key', 'fecha')
    )

    # Resumen en A-C; columna D vacía como separador; detalle (desglose) a
    # la derecha a partir de la columna E, alineado con el mismo renglón.
    INC_DET_COL = 5  # E

    ws_i = wb.create_sheet('Incidencias')
    ws_i.sheet_view.showGridLines = False
    for col, width in zip('ABCDEFGHIJK', [14, 28, 14, 3, 28, 14, 10, 22, 26, 50, 22]):
        ws_i.column_dimensions[col].width = width

    # Resumen por estación — mismo conteo que ya usa el ECV.
    ws_i.merge_cells('A1:C1')
    _fill_cols(ws_i, 1, range(1, 4), FILL_HEADER1)
    _set(ws_i, 1, 1, 'Resumen por estación (incidencias en cortes)', font=FONT_FALT_TITLE, align=center)
    _set(ws_i, 2, 1, 'N° Estación', font=white_bold, align=center, fill=FILL_HEADER1)
    _set(ws_i, 2, 2, 'Estación', font=white_bold, align=center, fill=FILL_HEADER1)
    _set(ws_i, 2, 3, 'Incidencias', font=white_bold, align=center, fill=FILL_HEADER1)

    row_i = 3
    total_incidencias = 0
    for team_key in team_keys:
        est = resultado.get(team_key)
        if not est:
            continue
        count = (est['indicadores'].get('incidencia') or {}).get('alcance')
        if count is None:
            continue
        _set(ws_i, row_i, 1, team_key, font=font_arial, align=center)
        _set(ws_i, row_i, 2, STATION_TEAMS[team_key], font=font_arial)
        _set(ws_i, row_i, 3, count, font=font_arial, align=center)
        total_incidencias += count
        row_i += 1
    _bandear_filas(ws_i, 3, row_i - 1, 1, 3)
    _set(ws_i, row_i, 2, 'Total', font=font_arial_bold)
    _set(ws_i, row_i, 3, total_incidencias, font=font_arial_bold, align=center, fill=FILL_VYM_TOTAL)
    _border_thin_range(ws_i, 2, 1, row_i, 3)

    # Detalle — cortes individuales de la semana usada para este ECV, a la
    # derecha del resumen, empezando en el mismo renglón (fila 1).
    inc_title_row  = 1
    inc_header_row = 2
    inc_start_row  = 3

    _fill_cols(ws_i, inc_title_row, range(INC_DET_COL, INC_DET_COL + 7), FILL_HEADER1)
    ws_i.merge_cells(start_row=inc_title_row, start_column=INC_DET_COL, end_row=inc_title_row, end_column=INC_DET_COL + 3)
    _set(ws_i, inc_title_row, INC_DET_COL, 'INCIDENCIAS EN CORTES', font=FONT_FALT_TITLE, align=center)
    _set(ws_i, inc_title_row, INC_DET_COL + 4, 'Semana de corte:', font=white_bold, align=right)
    _set(ws_i, inc_title_row, INC_DET_COL + 5, semana_domingo_inc, number_format='dd/mm/yyyy', font=white_bold)

    inc_cols = ['Estación', 'Fecha', 'Turno', 'Tipo de incidencia', 'Sub-detalle', 'Detalle', 'Problema']
    for i, label in enumerate(inc_cols):
        _set(ws_i, inc_header_row, INC_DET_COL + i, label, font=white_bold, align=center, fill=FILL_HEADER1)

    if not incidencias_detalle:
        ws_i.merge_cells(start_row=inc_start_row, start_column=INC_DET_COL, end_row=inc_start_row, end_column=INC_DET_COL + 6)
        _set(ws_i, inc_start_row, INC_DET_COL, 'Sin incidencias registradas para esta semana.', font=font_arial)
        inc_last_row = inc_start_row
    else:
        row_id = inc_start_row
        for r in incidencias_detalle:
            _set(ws_i, row_id, INC_DET_COL, STATION_TEAMS.get(r.estacion_key, r.estacion_key), font=font_arial)
            _set(ws_i, row_id, INC_DET_COL + 1, r.fecha, number_format='dd/mm/yyyy', font=font_arial, align=center)
            _set(ws_i, row_id, INC_DET_COL + 2, r.turno, font=font_arial, align=center)
            _set(ws_i, row_id, INC_DET_COL + 3, r.tipo_incidencia, font=font_arial)
            _set(ws_i, row_id, INC_DET_COL + 4, r.sub_detalle, font=font_arial)
            _set(ws_i, row_id, INC_DET_COL + 5, r.detalle, font=font_arial)
            _set(ws_i, row_id, INC_DET_COL + 6, r.problema, font=font_arial)
            row_id += 1
        inc_last_row = row_id - 1
        _bandear_filas(ws_i, inc_start_row, inc_last_row, INC_DET_COL, INC_DET_COL + 6)
    _border_thin_range(ws_i, inc_header_row, INC_DET_COL, inc_last_row, INC_DET_COL + 6)

    # Hoja "Faltantes" (al final, junto a "Ventas y Mistery"): réplica del
    # Excel ECV Zona manual — resumen por estación (mismo monto que ya
    # alimenta el indicador Faltante del ECV) y detalle fila por fila de
    # los faltantes actualmente abiertos en el F8, igual que el reporte
    # oficial "F8 SEMANAL" (no filtra por fecha de la semana consultada).
    from apps.incentives.faltantes_service import leer_faltantes_f8_abiertos_detalle

    filas_falt, error_falt = leer_faltantes_f8_abiertos_detalle()

    FILL_FALT         = PatternFill('solid', fgColor='E64646')
    FILL_FALT_ABIERTO = PatternFill('solid', fgColor='FFFF00')

    # Resumen en A-C; columna D vacía como separador; detalle (desglose) a
    # la derecha a partir de la columna E, alineado con el mismo renglón.
    FALT_DET_COL = 5  # E

    ws_f = wb.create_sheet('Faltantes')
    ws_f.sheet_view.showGridLines = False
    for col, width in zip('ABCDEFGHIJKLMNOP', [14, 28, 14, 3, 26, 26, 14, 26, 30, 8, 16, 32, 12, 24, 10, 16]):
        ws_f.column_dimensions[col].width = width

    # Resumen por estación — mismo monto que ya usa el ECV (snapshot guardado).
    ws_f.merge_cells('A1:C1')
    _fill_cols(ws_f, 1, range(1, 4), FILL_FALT)
    _set(ws_f, 1, 1, 'Resumen por estación (snapshot ECV)', font=FONT_FALT_TITLE, align=center)
    _set(ws_f, 2, 1, 'N° Estación', font=white_bold, align=center, fill=FILL_FALT)
    _set(ws_f, 2, 2, 'Estación', font=white_bold, align=center, fill=FILL_FALT)
    _set(ws_f, 2, 3, 'Faltantes', font=white_bold, align=center, fill=FILL_FALT)

    row_f = 3
    total_snapshot = 0.0
    for team_key in team_keys:
        est = resultado.get(team_key)
        if not est:
            continue
        monto = (est['indicadores'].get('faltante') or {}).get('alcance')
        if monto is None:
            continue
        _set(ws_f, row_f, 1, team_key, font=font_arial, align=center)
        _set(ws_f, row_f, 2, STATION_TEAMS[team_key], font=font_arial)
        _set(ws_f, row_f, 3, round(monto, 2), number_format='"$"#,##0.00', font=font_arial, align=right)
        total_snapshot += monto
        row_f += 1
    _bandear_filas(ws_f, 3, row_f - 1, 1, 3)
    _set(ws_f, row_f, 2, 'Total', font=font_arial_bold)
    _set(ws_f, row_f, 3, round(total_snapshot, 2), number_format='"$"#,##0.00',
         font=font_arial_bold, align=right, fill=FILL_VYM_TOTAL)
    _border_thin_range(ws_f, 2, 1, row_f, 3)

    # Detalle crudo — faltantes abiertos en el F8 ahora mismo, a la derecha
    # del resumen, empezando en el mismo renglón (fila 1).
    detalle_title_row  = 1
    detalle_header_row = 2
    detalle_start_row  = 3

    _fill_cols(ws_f, detalle_title_row, range(FALT_DET_COL, FALT_DET_COL + 12), FILL_FALT)
    ws_f.merge_cells(start_row=detalle_title_row, start_column=FALT_DET_COL, end_row=detalle_title_row, end_column=FALT_DET_COL + 4)
    _set(ws_f, detalle_title_row, FALT_DET_COL, 'FALTANTES', font=FONT_FALT_TITLE, align=center)
    _set(ws_f, detalle_title_row, FALT_DET_COL + 8, 'Fuente:', font=white_bold, align=right)
    _set(ws_f, detalle_title_row, FALT_DET_COL + 9, 'F8 SEMANAL', font=white_bold)

    detalle_cols = ['Estación', 'Gerente', 'Importe', 'Responsable', 'Motivo', 'Turno',
                    'Fecha de faltante', 'Observaciones', 'Días vigentes', 'Razón social', 'Zona', 'Estatus']
    for i, label in enumerate(detalle_cols):
        _set(ws_f, detalle_header_row, FALT_DET_COL + i, label, font=white_bold, align=center, fill=FILL_FALT)

    if error_falt:
        ws_f.merge_cells(start_row=detalle_start_row, start_column=FALT_DET_COL, end_row=detalle_start_row, end_column=FALT_DET_COL + 11)
        _set(ws_f, detalle_start_row, FALT_DET_COL, f'No se pudo leer el detalle del F8: {error_falt}', font=FONT_MALO)
        detalle_last_row = detalle_start_row
    else:
        filas_falt = [f for f in filas_falt if f['team_key'] in team_keys]
        filas_falt.sort(key=lambda f: (f['team_key'], f['fecha'] or date.min))
        row_d = detalle_start_row
        total_detalle = 0.0
        for f in filas_falt:
            estatus_fill = FILL_FALT_ABIERTO if f['estatus'] == 'ABIERTO' else None
            _set(ws_f, row_d, FALT_DET_COL, STATION_TEAMS.get(f['team_key'], f['team_key']), font=font_arial)
            _set(ws_f, row_d, FALT_DET_COL + 1, f['gerente'], font=font_arial)
            _set(ws_f, row_d, FALT_DET_COL + 2, round(f['importe'], 2), number_format='"$"#,##0.00', font=font_arial, align=right)
            _set(ws_f, row_d, FALT_DET_COL + 3, f['responsable'], font=font_arial)
            _set(ws_f, row_d, FALT_DET_COL + 4, f['motivo'], font=font_arial)
            _set(ws_f, row_d, FALT_DET_COL + 5, f['turno'], font=font_arial, align=center)
            _set(ws_f, row_d, FALT_DET_COL + 6, f['fecha'], number_format='dd/mm/yyyy', font=font_arial, align=center)
            _set(ws_f, row_d, FALT_DET_COL + 7, f['observaciones'], font=font_arial)
            _set(ws_f, row_d, FALT_DET_COL + 8, f['dias_vigentes'], font=font_arial, align=center)
            _set(ws_f, row_d, FALT_DET_COL + 9, f['razon_social'], font=font_arial)
            _set(ws_f, row_d, FALT_DET_COL + 10, f['zona'], font=font_arial, align=center)
            _set(ws_f, row_d, FALT_DET_COL + 11, f['estatus'], font=font_arial_bold, align=center, fill=estatus_fill)
            total_detalle += f['importe']
            row_d += 1

        _bandear_filas(ws_f, detalle_start_row, row_d - 1, FALT_DET_COL, FALT_DET_COL + 11)
        total_row_f = row_d
        _set(ws_f, total_row_f, FALT_DET_COL + 1, 'Total', font=font_arial_bold)
        _set(ws_f, total_row_f, FALT_DET_COL + 2, round(total_detalle, 2), number_format='"$"#,##0.00',
             font=font_arial_bold, align=right, fill=FILL_VYM_TOTAL)
        detalle_last_row = total_row_f

    _border_thin_range(ws_f, detalle_header_row, FALT_DET_COL, detalle_last_row, FALT_DET_COL + 11)

    for team_key in team_keys:
        est = resultado.get(team_key)
        if not est:
            continue
        nombre = STATION_TEAMS[team_key]

        # Nombre de hoja único, máx 31 caracteres (límite de Excel)
        base_nombre = ''.join(c for c in nombre if c not in '[]:*?/\\')[:28]
        hoja_nombre = base_nombre
        n = 2
        while hoja_nombre in hojas_usadas:
            hoja_nombre = f"{base_nombre[:26]} {n}"
            n += 1
        hojas_usadas.add(hoja_nombre)

        ws = wb.create_sheet(hoja_nombre)
        ws.sheet_view.showGridLines = False

        # Logos: una sola celda fusionada B3:G7, con logo_sencillo e ISOLOGO
        # flotando dentro, del mismo alto, centrados como una sola unidad.
        ws.merge_cells(start_row=3, start_column=2, end_row=7, end_column=7)

        col_widths_px = [187, 19, 96, 68, 131, 75]  # B,C,D,E,F,G
        row_heights_px = [25, 8, 36, 36, 8]         # filas 3,4,5,6,7
        avail_w, avail_h = sum(col_widths_px), sum(row_heights_px)

        def _anchor_offset(offset_px, start_idx, sizes_px):
            idx, remaining = start_idx, offset_px
            for size in sizes_px:
                if remaining < size:
                    break
                remaining -= size
                idx += 1
            return idx, round(remaining * 9525)

        logo_h = iso_h = 90
        logo_w = 90
        iso_w = round(logo_h * 341 / 94)
        gap = 15
        total_w = logo_w + gap + iso_w
        offset_x = (avail_w - total_w) / 2
        offset_y = (avail_h - logo_h) / 2

        col0, colOff0 = _anchor_offset(offset_x, 1, col_widths_px)      # col B = índice 1
        row0, rowOff0 = _anchor_offset(offset_y, 2, row_heights_px)    # fila 3 = índice 2
        col1, colOff1 = _anchor_offset(offset_x + logo_w + gap, 1, col_widths_px)

        if logo_path:
            img_logo = XLImage(logo_path)
            marker = AnchorMarker(col=col0, colOff=colOff0, row=row0, rowOff=rowOff0)
            img_logo.anchor = OneCellAnchor(_from=marker, ext=XDRPositiveSize2D(cx=logo_w * 9525, cy=logo_h * 9525))
            ws.add_image(img_logo)
        if isologo_path:
            img_iso = XLImage(isologo_path)
            marker = AnchorMarker(col=col1, colOff=colOff1, row=row0, rowOff=rowOff0)
            img_iso.anchor = OneCellAnchor(_from=marker, ext=XDRPositiveSize2D(cx=iso_w * 9525, cy=iso_h * 9525))
            ws.add_image(img_iso)

        # Columnas: A margen, B etiqueta, C espaciador, D-E Ponderación, F-H Resultados,
        # I espaciador, J-L Mínimo/Objetivo/Excelente, M espaciador, N oculta (helper
        # heredado del Excel original), O-P Evaluación Final, Q monto base.
        for col, width in zip('ABCDEFGHIJKLMNOPQ',
                               [2, 26, 2, 13, 9, 18, 10, 18, 2, 18, 10, 10, 2, 10, 14, 16, 9]):
            ws.column_dimensions[col].width = width
        ws.column_dimensions['N'].hidden = True
        for r, h in [(2, 30), (3, 19), (4, 6), (5, 27), (6, 27), (7, 6), (8, 19),
                     (9, 37), (10, 26), (11, 30), (12, 30), (13, 30), (14, 30), (15, 30), (17, 24)]:
            ws.row_dimensions[r].height = h

        ws.merge_cells(start_row=2, start_column=2, end_row=2, end_column=16)
        _fill_row(ws, 2, range(2, 17), FILL_TITLE)
        _set(ws, 2, 2, 'Cálculo de Compensación Variable', font=title_font, align=center)

        _set(ws, 3, 10, 'Periodo Evaluado:', font=bold)
        ws.merge_cells(start_row=3, start_column=11, end_row=3, end_column=12)
        _set(ws, 3, 11, f'Semana: {semana_num}', font=bold, align=center)
        _border_outline(ws, 3, 10, 3, 10)
        _border_outline(ws, 3, 11, 3, 12)

        cat_bono = est['categoria_bono'] or est['categoria']

        ws.merge_cells(start_row=5, start_column=10, end_row=5, end_column=13)
        _set(ws, 5, 8, 'Departamento:', font=bold, align=right)
        _set(ws, 5, 10, team_key, fill=FILL_INFO)
        _set(ws, 5, 15, round(est['bono_gerente'], 2), number_format='"$"#,##0.00', font=white_bold, fill=FILL_BONO, align=center)
        _set(ws, 5, 16, 'Gerente', font=white_bold, fill=FILL_BONO, align=center)
        _border_outline(ws, 5, 10, 5, 13)

        ws.merge_cells(start_row=6, start_column=10, end_row=6, end_column=13)
        _set(ws, 6, 8, 'Estación:', font=bold, align=right)
        _set(ws, 6, 10, nombre, fill=FILL_INFO)
        _set(ws, 6, 15, round(est['bono_subgerente'], 2), number_format='"$"#,##0.00', font=white_bold, fill=FILL_BONO, align=center)
        _set(ws, 6, 16, 'Subgerente', font=white_bold, fill=FILL_BONO, align=center)
        _border_outline(ws, 6, 10, 6, 13)

        header_row = 9
        ws.merge_cells(start_row=header_row, start_column=4, end_row=header_row, end_column=5)
        ws.merge_cells(start_row=header_row, start_column=6, end_row=header_row, end_column=8)
        ws.merge_cells(start_row=header_row, start_column=15, end_row=header_row, end_column=16)
        _fill_row(ws, header_row, range(2, 17), FILL_HEADER1)
        _set(ws, header_row, 2, f'Categoría ({cat_bono})', font=white_bold)
        _set(ws, header_row, 4, 'Ponderación', font=white_bold, align=center)
        _set(ws, header_row, 6, 'Resultados', font=white_bold, align=center)
        _set(ws, header_row, 10, 'Mínimo', font=white_bold, align=center)
        _set(ws, header_row, 11, 'Objetivo', font=white_bold, align=center)
        _set(ws, header_row, 12, 'Excelente', font=white_bold, align=center)
        _set(ws, header_row, 15, 'Evaluación Final', font=white_bold, align=center)

        sub_row = header_row + 1
        _fill_row(ws, sub_row, range(2, 17), FILL_HEADER2)
        for col, label in [(2, 'Indicador (KPI)'), (4, 'Valor %'), (5, 'Valor %'), (6, 'Alcance'),
                            (7, 'Objetivo'), (8, '% Logro'), (10, '80%'), (11, '100%'), (12, '120%'),
                            (15, 'Cálculo'), (16, 'Valor (%)')]:
            _set(ws, sub_row, col, label, font=white_bold, align=center)

        row = sub_row + 1
        sum_ponderacion = 0.0
        indicadores = est['indicadores']
        for key, label, tipo in INDICADORES:
            d = indicadores.get(key)
            if d is None:
                continue

            ponderacion = d.get('ponderacion')
            if ponderacion is not None:
                sum_ponderacion += ponderacion

            mayor_es_mejor = key in ('venta_gas', 'venta_diesel', 'mistery')
            fill_sem, font_sem = _semaforo_logro(
                d.get('alcance'), d.get('umbral_minimo'), d.get('umbral_objetivo'), d.get('umbral_excelente'), mayor_es_mejor,
            )

            _fill_row(ws, row, [2, 4, 5, 15, 16], FILL_LABEL)
            _set(ws, row, 2, label, font=bold)
            _pct(ws, row, 4, ponderacion, font=bold)
            _pct(ws, row, 5, ponderacion * 1.2 if ponderacion is not None else None, font=bold)

            if key in ('venta_gas', 'venta_diesel'):
                _num(ws, row, 6, d.get('alcance_raw'), 'num')
                _num(ws, row, 7, d.get('objetivo_raw'), 'num')
                _pct(ws, row, 8, d.get('alcance'), fill=fill_sem, font=font_sem)
                _pct(ws, row, 10, d.get('umbral_minimo'), font=FONT_MIN, fill=FILL_MIN)
                _pct(ws, row, 11, d.get('umbral_objetivo'), font=FONT_OBJ, fill=FILL_OBJ)
                _pct(ws, row, 12, d.get('umbral_excelente'), font=FONT_EXC, fill=FILL_EXC)
            elif key == 'mistery':
                _pct(ws, row, 6, d.get('alcance_raw'))
                _pct(ws, row, 7, d.get('objetivo_raw'))
                _pct(ws, row, 8, d.get('alcance'), fill=fill_sem, font=font_sem)
                _pct(ws, row, 10, d.get('umbral_minimo'), font=FONT_MIN, fill=FILL_MIN)
                _pct(ws, row, 11, d.get('umbral_objetivo'), font=FONT_OBJ, fill=FILL_OBJ)
                _pct(ws, row, 12, d.get('umbral_excelente'), font=FONT_EXC, fill=FILL_EXC)
            elif key == 'faltante':
                _num(ws, row, 6, d.get('alcance'), 'money')
                _num(ws, row, 7, d.get('umbral_objetivo'), 'money')
                _pct(ws, row, 8, d.get('calculo'), fill=fill_sem, font=font_sem)
                _num(ws, row, 10, d.get('umbral_minimo'), 'money', font=FONT_MIN, fill=FILL_MIN)
                _num(ws, row, 11, d.get('umbral_objetivo'), 'money', font=FONT_OBJ, fill=FILL_OBJ)
                _num(ws, row, 12, d.get('umbral_excelente'), 'money', font=FONT_EXC, fill=FILL_EXC)
            else:  # incidencia
                _num(ws, row, 6, d.get('alcance'), 'count')
                _num(ws, row, 7, d.get('umbral_objetivo'), 'count')
                _pct(ws, row, 8, d.get('calculo'), fill=fill_sem, font=font_sem)
                _num(ws, row, 10, d.get('umbral_minimo'), 'count', font=FONT_MIN, fill=FILL_MIN)
                _num(ws, row, 11, d.get('umbral_objetivo'), 'count', font=FONT_OBJ, fill=FILL_OBJ)
                _num(ws, row, 12, d.get('umbral_excelente'), 'count', font=FONT_EXC, fill=FILL_EXC)

            _pct(ws, row, 15, d.get('calculo'))
            _pct(ws, row, 16, d.get('valor'))
            row += 1

        last_data_row = row - 1

        row += 1
        total_row = row
        _fill_row(ws, row, [4, 5, 15, 16], FILL_LABEL)
        _pct(ws, row, 4, sum_ponderacion, font=bold)
        _pct(ws, row, 5, sum_ponderacion * 1.2, font=bold)
        _set(ws, row, 15, 'Puntos', font=bold, align=center)
        _pct(ws, row, 16, est['total_puntos'], font=bold)
        ws.cell(row=row, column=16).alignment = center

        # Bordes: el número de filas de indicadores varía según si la estación
        # tiene venta de diésel (Categoría B) o no, así que las filas con/sin
        # borde se calculan a partir de last_data_row / total_row, no fijas.
        _border_range(ws, 9, 2, last_data_row, 2)
        _border_range(ws, 11, 4, last_data_row, 8)
        _border_range(ws, 11, 10, last_data_row, 12)
        _border_range(ws, 11, 15, last_data_row, 16)
        _border_range(ws, 5, 15, 6, 16)
        _border_outline(ws, total_row, 15, total_row, 16)
        _border_range(ws, total_row, 4, total_row, 5)

        # Fila de encabezados "Ponderación"/"Resultados" (9) y sub-encabezados (10):
        # un solo cuadro por grupo, sin separar internamente.
        _border_outline(ws, 9, 4, 9, 8)
        _border_outline(ws, 10, 4, 10, 5)
        _border_outline(ws, 10, 6, 10, 8)

        # Centrado horizontal (además del vertical ya aplicado) en las celdas
        # de datos — mismos rangos dinámicos que los bordes.
        _center_range(ws, 9, 2, 9, 2)
        _center_range(ws, 11, 4, last_data_row, 8)
        _center_range(ws, total_row, 4, total_row, 5)
        _center_range(ws, 11, 10, last_data_row, 12)
        _center_range(ws, 11, 15, last_data_row, 16)

    # "Ventas y Mistery", "Incidencias" y "Faltantes" van al final del libro,
    # después de todas las estaciones — igual que en el Excel ECV Zona manual.
    for ws_final in (ws_v, ws_i, ws_f):
        wb._sheets.remove(ws_final)
        wb._sheets.append(ws_final)

    filename = f"ECV Sem {semana_num} ({week_start.isoformat()}).xlsx"
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


@login_required
def exportar_layout_incentivos(request):
    """Descarga el layout plano para carga a nómina: una fila por empleado y
    concepto (ConceptoID, Monto, Observa, Referencia). Por ahora cubre
    Diesel (610), Encargado (609), Mistery (608) y Venta (607)."""
    from datetime import date, timedelta
    import openpyxl
    from django.db.models import Count, Sum, Q
    from django.http import HttpResponse

    rol = _get_rol_incentivos(request.user)
    if rol not in ('admin', 'operaciones'):
        return redirect('incentives_dashboard')

    CONCEPTOS = {
        'Diesel':    610,
        'Encargado': 609,
        'Mistery':   608,
        'Venta':     607,
    }

    semana_str = request.GET.get('semana')
    today = date.today()
    if semana_str:
        try:
            week_start = date.fromisoformat(semana_str)
        except ValueError:
            week_start = today - timedelta(days=today.weekday())
    else:
        week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    cfg = ConfiguracionIncentivos.get()

    # Si la vista tenía un filtro de búsqueda activo, solo exportar las
    # estaciones que quedaron visibles (mismas que mandó el JS) — igual
    # que exportar_ecv_excel.
    team_keys = set(STATION_TEAMS.keys())
    estaciones_filtro = request.GET.get('estaciones')
    if estaciones_filtro:
        filtro_set = {tk for tk in estaciones_filtro.split(',') if tk}
        team_keys = {tk for tk in team_keys if tk in filtro_set}

    # Mismo universo de empleados que el panel admin (dedup por TSA,
    # puestos excluidos, filtro por semana) para que el layout solo
    # incluya lo que se ve en esa vista.
    inactivos_con_registro = set(
        IncentivoRegistro.objects
        .filter(fecha__range=(week_start, week_end), employee__is_active=False,
                employee__team__in=team_keys)
        .values_list('employee_id', flat=True)
    )
    employees = _filtrar_empleados_por_semana(
        _deduplicar_por_tsa(list(
            Employee.objects
            .filter(team__in=team_keys)
            .exclude(job_position__title__in=PUESTOS_EXCLUIDOS_INCENTIVOS)
            .filter(Q(is_active=True) | Q(id__in=inactivos_con_registro))
            .only('id', 'team', 'curp', 'company', 'seniority_raw', 'is_active', 'employee_number')
        )),
        week_end,
        inactivos_con_registro,
    )
    emp_ids = [emp.id for emp in employees]
    emp_numero = {emp.id: emp.employee_number for emp in employees}

    registros = (
        IncentivoRegistro.objects
        .filter(tipo__in=CONCEPTOS.keys(), fecha__range=(week_start, week_end), employee_id__in=emp_ids)
        .values('employee_id', 'tipo')
        .annotate(count=Count('id'), suma_monto=Sum('monto'))
    )

    filas = []
    for r in registros:
        numero = emp_numero.get(r['employee_id'])
        if not numero:
            continue
        count = r['count'] or 0
        if r['tipo'] == 'Diesel':
            monto = count * cfg.diesel_por_dia
        elif r['tipo'] == 'Encargado':
            monto = (cfg.encargado_primer_dia + (count - 1) * cfg.encargado_incremento) if count > 0 else 0
        else:
            monto = int(r['suma_monto'] or 0)
        if monto <= 0:
            continue
        filas.append((CONCEPTOS[r['tipo']], monto, numero))

    filas.sort(key=lambda f: (f[0], f[2]))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Layout'

    headers = ['ConceptoID', 'Monto', 'Observa', 'Referencia', 'Empleado']
    for col, h in enumerate(headers, start=1):
        ws.cell(row=1, column=col, value=h)

    for row, (concepto_id, monto, numero) in enumerate(filas, start=2):
        ws.cell(row=row, column=1, value=concepto_id)
        ws.cell(row=row, column=2, value=monto)
        ws.cell(row=row, column=3, value='')
        ws.cell(row=row, column=4, value='')
        ws.cell(row=row, column=5, value=numero)

    filename = f"Layout Incentivos ({week_start.isoformat()}).xlsx"
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response
