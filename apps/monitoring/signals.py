from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from .models import SessionEvent
from .services import get_client_ip, geo_city_light

@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    ip = get_client_ip(request)
    country, region, city = geo_city_light(ip)
    SessionEvent.objects.create(
        user=user, event=SessionEvent.LOGIN, ip=ip,
        country=country, region=region, city=city,
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:500] if request else "")
    )

@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    ip = get_client_ip(request) if request else None
    # en logout no llamamos a geo para ahorrar; guarda lo que tengas
    SessionEvent.objects.create(
        user=user, event=SessionEvent.LOGOUT, ip=ip,
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:500] if request else "")
    )
