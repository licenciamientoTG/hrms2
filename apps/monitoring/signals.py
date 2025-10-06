from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from .models import SessionEvent

def _ip(request):
    if not request:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")

@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    SessionEvent.objects.create(
        user=user,
        event=SessionEvent.LOGIN,
        ip=_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:500] if request else ""),
    )

@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    SessionEvent.objects.create(
        user=user,
        event=SessionEvent.LOGOUT,
        ip=_ip(request) if request else None,
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:500] if request else ""),
    )
