from django.utils import timezone
from django.core.cache import cache
from datetime import datetime, time
from .models import UserDailyUse

# Rutas a ignorar (ajústalas a tu app)
IGNORE_PREFIXES = (
    "/static/", "/media/", "/admin/jsi18n/",
    "/healthz", "/ping", "/heartbeat", "/ws/", "/api/heartbeat/",
)

def _seconds_to_midnight_local():
    now = timezone.localtime()
    end = datetime.combine(now.date(), time.max).replace(tzinfo=now.tzinfo)
    return int((end - now).total_seconds())

class DailyUsageMiddleware:
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
