# apps/monitoring/middleware.py
from datetime import datetime, time, timedelta
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import logout
from django.conf import settings
from django.db.models import F

from .models import UserDailyUse, SessionEvent, ModuleVisit

# -------------------------
# Config y helpers compartidos
# -------------------------
IGNORE_PREFIXES = (
    "/static/", "/media/", "/admin/jsi18n/",
    "/healthz", "/ping", "/heartbeat", "/ws/", "/api/heartbeat/",
)

# Mapeo prefijo URL → nombre legible del módulo
# Orden importa: el primero que coincida gana
MODULE_MAP = [
    ("/incentives/",    "Incentivos"),
    ("/courses/",       "Cursos"),
    ("/vacations/",     "Vacaciones"),
    ("/news/",          "Noticias"),
    ("/performance/",   "Evaluaciones"),
    ("/org_chart/",     "Organigrama"),
    ("/recognitions/",  "Comunicados"),
    ("/objectives/",    "Objetivos"),
    ("/archive/",       "Archivo"),
    ("/onboarding/",    "Onboarding"),
    ("/surveys/",       "Encuestas"),
    ("/documents/",     "Documentos"),
    ("/job_offers/",    "Ofertas de Empleo"),
    ("/policies/",      "Políticas"),
    ("/career_plan/",   "Plan de Carrera"),
    ("/tools/",         "Herramientas"),
    ("/forms_requests/","Solicitudes"),
    ("/departments/",   "Departamentos"),
    ("/requisiciones/", "Requisiciones de Personal"),
    ("/monitoring/",    "Monitoreo"),
    ("/users/",         "Usuarios"),
    ("/home/",          "Inicio"),
]

# URLs que son llamadas de fondo (API, badges, ajax) — no cuentan como visita al módulo
MODULE_IGNORE_PATHS = (
    "/courses/unread_count/",
    "/notifications/api/",
    "/recognitions/api/",
    "/endpoints/",
    "/api/",
)

def _detect_module(path):
    """Devuelve el nombre del módulo según el prefijo de la URL, o None."""
    for ignore in MODULE_IGNORE_PATHS:
        if path.startswith(ignore):
            return None
    for prefix, name in MODULE_MAP:
        if path.startswith(prefix):
            return name
    return None

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
                    SessionEvent.objects.create(
                        user=request.user,
                        event=SessionEvent.LOGOUT_IDLE,
                        ip=request.META.get("REMOTE_ADDR"),
                        user_agent=(request.META.get("HTTP_USER_AGENT","")[:500]),
                    )
                    # marca que este logout es por inactividad
                    setattr(request, "_logout_reason", "idle")
                    logout(request)
            request.session["last_activity_ts"] = now.timestamp()

        return self.get_response(request)

# -------------------------
# 2) Marcado de uso diario
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

# -------------------------
# 3) Tracking de visitas por módulo
# -------------------------
class ModuleVisitMiddleware:
    """
    Por cada request autenticado que corresponda a un módulo conocido,
    hace upsert en ModuleVisit (usuario, módulo, fecha, count+1).
    Usa caché para no escribir en BD en cada click: escribe una vez
    por minuto por combinación usuario/módulo.
    """
    CACHE_TTL = 60  # segundos entre escrituras a BD por usuario/módulo

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ""
        if request.user.is_authenticated and not path.startswith(IGNORE_PREFIXES):
            module = _detect_module(path)
            if module:
                today = timezone.localdate()
                cache_key = f"modvisit:{request.user.id}:{module}:{today}"
                if not cache.get(cache_key):
                    cache.set(cache_key, True, timeout=self.CACHE_TTL)
                    obj, created = ModuleVisit.objects.get_or_create(
                        user=request.user,
                        module=module,
                        date=today,
                        defaults={"count": 1},
                    )
                    if not created:
                        ModuleVisit.objects.filter(pk=obj.pk).update(count=F("count") + 1)
        return self.get_response(request)
