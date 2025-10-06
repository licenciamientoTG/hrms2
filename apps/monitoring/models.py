from django.db import models
from django.conf import settings

class SessionEvent(models.Model):
    LOGIN  = "login"
    LOGOUT = "logout"
    EVENT_CHOICES = [(LOGIN, "Login"), (LOGOUT, "Logout")]

    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event       = models.CharField(max_length=10, choices=EVENT_CHOICES)
    ts          = models.DateTimeField(auto_now_add=True)

    ip          = models.GenericIPAddressField(null=True, blank=True)
    user_agent  = models.TextField(blank=True, default="")

    # NUEVOS (ubicación del evento)
    country     = models.CharField(max_length=64, blank=True, default="")   # p.ej. "Mexico"
    region      = models.CharField(max_length=64, blank=True, default="")   # Estado/Provincia
    city        = models.CharField(max_length=64, blank=True, default="")   # Ciudad

    class Meta:
        indexes = [
            models.Index(fields=["user", "ts"]),
            models.Index(fields=["event", "ts"]),
        ]
