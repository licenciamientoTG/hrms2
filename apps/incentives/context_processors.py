from apps.incentives.constants import STATION_TEAMS


def auto_incentivos_permission(request):
    if not request.user.is_authenticated or request.user.is_superuser:
        return {}

    try:
        emp = request.user.employee
        titulo = emp.job_position.title if emp.is_active and emp.job_position else ''
        titulo_lower = titulo.lower()
        dept_nombre = (emp.department.name if emp.department else '').lower()
        en_estacion = bool(emp.is_active and emp.team and emp.team.strip() in STATION_TEAMS)
        es_gerente_ops = (
            titulo == 'Gerente De Operaciones'
            and 'aqua car club' not in (emp.company or '').lower()
        )
    except Exception:
        return {}

    es_jefe_zona = 'jefe de zona' in titulo_lower
    es_nominas = (
        'supervisor de nóminas' in titulo_lower
        or 'supervisor de nominas' in titulo_lower
        or 'nomina' in dept_nombre
    )
    es_gerente_estacion = (
        'gerente de estaci' in titulo_lower
        or 'subgerente de estaci' in titulo_lower
    )

    if (en_estacion or es_gerente_ops or es_jefe_zona or es_nominas) and not request.user.has_perm('incentives.Modulo_incentivos'):
        from django.contrib.auth.models import Group
        grupo = Group.objects.filter(name='Modulo de incentivos').first()
        if grupo:
            request.user.groups.add(grupo)
            request.user._perm_cache = None
            request.user._user_perm_cache = None

    es_jefe_operaciones = es_gerente_ops or es_jefe_zona or es_gerente_estacion
    ocultar_vacaciones = en_estacion and not es_jefe_operaciones

    return {'ocultar_vacaciones': ocultar_vacaciones}
