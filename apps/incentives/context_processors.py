from apps.incentives.constants import STATION_TEAMS


def auto_incentivos_permission(request):
    if not request.user.is_authenticated or request.user.is_superuser:
        return {}

    try:
        emp = request.user.employee
        en_estacion = bool(emp.is_active and emp.team and emp.team.strip() in STATION_TEAMS)
    except Exception:
        return {}

    if en_estacion and not request.user.has_perm('incentives.Modulo_incentivos'):
        from django.contrib.auth.models import Group
        grupo = Group.objects.filter(name='Modulo de incentivos').first()
        if grupo:
            request.user.groups.add(grupo)
            request.user._perm_cache = None
            request.user._user_perm_cache = None

    return {}
