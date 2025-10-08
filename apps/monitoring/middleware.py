# apps/monitoring/middleware.py
from datetime import datetime, time, timedelta
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import logout
from django.conf import settings

from .models import UserDailyUse, SessionEvent  # SessionEvent ya lo usas

# -------------------------
# Config y helpers compartidos
# -------------------------
IGNORE_PREFIXES = (
    "/static/", "/media/", "/admin/jsi18n/",
    "/healthz", "/ping", "/heartbeat", "/ws/", "/api/heartbeat/",
)

IDLE_TIMEOUT_SECONDS = getattr(settings, "IDLE_TIMEOUT_SECONDS", 1800)  # 30 min

def _seconds_to_midnight_local():
    now = timezone.localtime()
    end = datetime.combine(now.date(), time.max).replace(tzinfo=now.tzinfo)
    return int((end - now).total_seconds())

# -------------------------
# 1) Timeout de inactividad + logging
# -------------------------
class IdleTimeoutMiddleware:
    """
    Si un usuario autenticado pasa más de IDLE_TIMEOUT_SECONDS sin actividad,
    al siguiente request:
      - Registra SessionEvent.LOGOUT_IDLE
      - Hace logout(request)
    Además, en cada request autenticado actualiza last_activity_ts en sesión.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not (request.path or "").startswith(IGNORE_PREFIXES):
            now = timezone.now()
            last_ts = request.session.get("last_activity_ts")
            if last_ts is not None:
                try:
                    elapsed = now.timestamp() - float(last_ts)
                except Exception:
                    elapsed = 0  # por si algo raro viene en la cookie
                if elapsed > IDLE_TIMEOUT_SECONDS:
                    # Registrar cierre por inactividad
                    SessionEvent.objects.create(
                        user=request.user,
                        event=SessionEvent.LOGOUT_IDLE,  # asegúrate de tener esta constante
                        ip=(request.META.get("REMOTE_ADDR")),
                        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:500]),
                    )
                    logout(request)
            request.session["last_activity_ts"] = now.timestamp()

        return self.get_response(request)

# -------------------------
# 2) Marcado de uso diario (lo de tu código actual)
# -------------------------
class DailyUsageMiddleware:
    """
    Marca 'uso del día' (UserDailyUse) solo una vez por día por usuario.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ""
        if request.user.is_authenticated and not path.startswith(IGNORE_PREFIXES):
            today = timezone.localdate()
            key = f"dailyuse:{request.user.id}:{today}"
            # cache.add retorna True solo la primera vez del día
            if cache.add(key, True, timeout=_seconds_to_midnight_local()):
                # Crea el registro (si otra petición ya lo creó, no pasa nada)
                UserDailyUse.objects.get_or_create(user=request.user, date=today)
        return self.get_response(request)
